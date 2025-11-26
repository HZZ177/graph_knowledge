"""流式 LLM 响应基础设施（CrewAI 1.6.0 版）

核心组件：
- run_agent_stream: 执行单个 Agent 并自动发送流式响应到 WebSocket
- iter_crew_text_stream: 底层异步迭代器（内部使用）

使用方式：
    # Service 层只需调用，不处理 chunk
    output = await run_agent_stream(crew, websocket, agent_meta)
"""

import asyncio
import json
import queue
import threading
import time
from typing import Any, AsyncGenerator, Optional
from dataclasses import dataclass, field

from crewai import Crew
from starlette.websockets import WebSocket

from backend.app.core.logger import logger


@dataclass
class StreamMessage:
    """通用流式消息格式（用于 Chat 等场景）"""
    type: str  # 'start' | 'chunk' | 'done' | 'error'
    content: Optional[str] = None
    request_id: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "request_id": self.request_id,
            "error": self.error,
            "metadata": self.metadata,
        }


async def run_agent_stream(
    crew: Crew,
    websocket: WebSocket,
    agent_meta: dict,
) -> str:
    """执行单个 Agent 任务，自动发送流式响应到 WebSocket
    
    封装了完整的流式发送逻辑：agent_start -> stream chunks -> agent_end
    Service 层无需关心 chunk 处理。
    
    Args:
        crew: 已配置的 Crew 实例（需要 stream=True）
        websocket: WebSocket 连接
        agent_meta: Agent 元信息 {"name": str, "index": int, "description": str}
        
    Returns:
        完整的 Agent 输出文本
    """
    agent_name = agent_meta["name"]
    agent_index = agent_meta["index"]
    agent_description = agent_meta.get("description", "")
    
    # 发送 agent_start
    await websocket.send_text(json.dumps({
        "type": "agent_start",
        "agent_name": agent_name,
        "agent_index": agent_index,
        "agent_description": agent_description,
    }))
    
    start_time = time.time()
    output = ""
    
    try:
        # 流式执行，自动发送每个 chunk
        async for chunk in iter_crew_text_stream(crew):
            output += chunk
            await websocket.send_text(json.dumps({
                "type": "stream",
                "agent_name": agent_name,
                "agent_index": agent_index,
                "content": chunk,
            }))
        
        # 发送 agent_end
        await websocket.send_text(json.dumps({
            "type": "agent_end",
            "agent_name": agent_name,
            "agent_index": agent_index,
            "agent_output": output,
            "duration_ms": int((time.time() - start_time) * 1000),
        }))
        
        logger.info(f"[{agent_name}] 执行完成，输出长度: {len(output)} 字符")
        return output
        
    except Exception as e:
        logger.error(f"[{agent_name}] 执行失败: {e}", exc_info=True)
        await websocket.send_text(json.dumps({
            "type": "error",
            "agent_name": agent_name,
            "agent_index": agent_index,
            "error": str(e),
        }))
        raise


async def iter_crew_text_stream(
    crew: Crew,
    **kickoff_kwargs: Any,
) -> AsyncGenerator[str, None]:
    """将 CrewAI 1.6.0 的同步 streaming 接口封装为异步文本迭代器。

    Crew(stream=True) 时，``crew.kickoff(...)`` 会返回一个可迭代的 streaming 对象，
    我们在后台线程中迭代该对象，并通过线程安全队列把文本 chunk 送入 asyncio 协程世界。

    Args:
        crew: 已配置好的 Crew 实例（需要在创建时设置 ``stream=True``）。
        **kickoff_kwargs: 传递给 ``crew.kickoff()`` 的可选参数（如 inputs 等）。

    Yields:
        str: 每个文本 chunk（通常来自 ``chunk.content``）。
    """

    loop = asyncio.get_event_loop()
    q: "queue.Queue[Optional[str]]" = queue.Queue()

    def _run_streaming() -> None:
        try:
            streaming = crew.kickoff(**kickoff_kwargs)

            for chunk in streaming:
                # 官方文档：chunk 通常具有 .content 属性
                text = getattr(chunk, "content", None)
                if not text:
                    continue
                q.put(text)

        except Exception as exc:  # noqa: BLE001
            logger.error("[iter_crew_text_stream] 执行 crew.kickoff() 失败: {}", exc, exc_info=True)
        finally:
            # 使用 None 作为结束信号
            q.put(None)

    # 在后台线程中执行同步的 streaming 迭代
    thread = threading.Thread(target=_run_streaming, daemon=True)
    thread.start()

    # 在异步环境中逐个读取文本 chunk
    while True:
        text = await asyncio.to_thread(q.get)
        if text is None:
            break
        yield text
