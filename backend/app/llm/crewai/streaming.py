"""流式 LLM 响应基础设施（CrewAI）

核心组件：
- run_agent_stream: 执行单个 Agent 并自动发送流式响应到 WebSocket
- iter_crew_text_stream: 底层异步迭代器（内部使用）
"""

import asyncio
import json
import queue
import re
import threading
import time
from typing import Any, AsyncGenerator, Optional
from dataclasses import dataclass, field

from crewai import Crew
from starlette.websockets import WebSocket

from backend.app.core.logger import logger


class StreamSectionTracker:
    """流式输出区域追踪器
    
    在流式输出过程中，追踪当前处于哪个区域（thought / answer），
    并在区域切换时发出通知。
    """
    
    SECTION_THOUGHT = "thought"
    SECTION_ANSWER = "answer"
    SECTION_UNKNOWN = "unknown"
    
    def __init__(self):
        self.buffer = ""  # 累积的完整输出
        self.current_section = self.SECTION_UNKNOWN
        self._thought_started = False
        self._answer_started = False
    
    def process_chunk(self, chunk: str) -> dict:
        """处理新的 chunk，返回该 chunk 所属的区域信息"""
        self.buffer += chunk
        
        result = {
            "section": self.current_section,
            "content": chunk,
            "section_changed": False,
        }
        
        # 检测是否进入 Thought 区域
        if not self._thought_started:
            thought_marker = "Thought:"
            if thought_marker.lower() in self.buffer.lower():
                self._thought_started = True
                self.current_section = self.SECTION_THOUGHT
                result["section"] = self.SECTION_THOUGHT
                result["section_changed"] = True
                # 过滤掉 "Thought:" 标记本身
                marker_pos = chunk.lower().find(thought_marker.lower())
                if marker_pos >= 0:
                    result["content"] = chunk[marker_pos + len(thought_marker):].lstrip()
        
        # 检测是否进入 Final Answer 区域
        if not self._answer_started:
            answer_marker = "Final Answer:"
            if answer_marker.lower() in self.buffer.lower():
                self._answer_started = True
                self.current_section = self.SECTION_ANSWER
                result["section"] = self.SECTION_ANSWER
                result["section_changed"] = True
                # 过滤掉 "Final Answer:" 标记本身
                marker_pos = chunk.lower().find(answer_marker.lower())
                if marker_pos >= 0:
                    result["content"] = chunk[marker_pos + len(answer_marker):].lstrip()
        
        return result
    
    def get_final_sections(self) -> dict:
        """获取最终的分区内容（用于 agent_end 消息）"""
        thought = ""
        final_answer = ""
        
        # 提取 Thought 部分
        thought_match = re.search(
            r"Thought:\s*(.*?)(?=Final Answer:|$)",
            self.buffer,
            re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # 提取 Final Answer 部分
        answer_match = re.search(
            r"Final Answer:\s*(.*)",
            self.buffer,
            re.DOTALL | re.IGNORECASE
        )
        if answer_match:
            final_answer = answer_match.group(1).strip()
        
        return {
            "thought": thought,
            "final_answer": final_answer,
            "raw": self.buffer,
        }


@dataclass
class StreamMessage:
    """通用流式消息格式"""
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
    tracker = StreamSectionTracker()
    
    try:
        # 流式执行，实时追踪区域并发送
        async for chunk in iter_crew_text_stream(crew):
            section_info = tracker.process_chunk(chunk)
            
            # 发送带区域标识的 stream 消息
            await websocket.send_text(json.dumps({
                "type": "stream",
                "agent_name": agent_name,
                "agent_index": agent_index,
                "content": section_info["content"],
                "section": section_info["section"],
                "section_changed": section_info["section_changed"],
            }))
        
        # 获取最终分区内容
        parsed = tracker.get_final_sections()
        
        # 发送 agent_end，包含结构化的思考过程和最终结果
        await websocket.send_text(json.dumps({
            "type": "agent_end",
            "agent_name": agent_name,
            "agent_index": agent_index,
            "agent_output": parsed["raw"],
            "thought": parsed["thought"],
            "final_answer": parsed["final_answer"],
            "duration_ms": int((time.time() - start_time) * 1000),
        }))
        
        logger.debug(f"[{agent_name}] 完整输出内容:\n{parsed['raw']}")
        logger.info(f"[{agent_name}] 执行完成，输出长度: {len(parsed['raw'])} 字符, thought: {len(parsed['thought'])} 字符, answer: {len(parsed['final_answer'])} 字符")
        return parsed["raw"]
        
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
    """将 CrewAI 的同步 streaming 接口封装为异步文本迭代器"""

    loop = asyncio.get_event_loop()
    q: "queue.Queue[Optional[str]]" = queue.Queue()

    def _run_streaming() -> None:
        try:
            streaming = crew.kickoff(**kickoff_kwargs)
            
            chunk_count = 0
            
            # 方式1: 迭代 chunks 属性
            chunks = getattr(streaming, "chunks", None)
            if chunks:
                for chunk in chunks:
                    chunk_count += 1
                    text = getattr(chunk, "content", None) or getattr(chunk, "text", None) or str(chunk)
                    if text:
                        q.put(text)
            
            # 方式2: 直接迭代 streaming 对象
            if chunk_count == 0:
                try:
                    for chunk in streaming:
                        chunk_count += 1
                        text = getattr(chunk, "content", None) or getattr(chunk, "text", None) or str(chunk)
                        if text:
                            q.put(text)
                except TypeError:
                    pass
            
            # 方式3: 使用 get_full_text() 方法
            if chunk_count == 0:
                get_full_text = getattr(streaming, "get_full_text", None)
                if callable(get_full_text):
                    full_text = get_full_text()
                    if full_text:
                        q.put(full_text)
                        chunk_count = 1
            
            # 方式4: 使用 result 属性
            if chunk_count == 0:
                result = getattr(streaming, "result", None)
                if result:
                    result_raw = getattr(result, "raw", None) or str(result)
                    if result_raw:
                        q.put(result_raw)
                        chunk_count = 1
            
            logger.info(f"[iter_crew_text_stream] 完成, 共 {chunk_count} 个输出")

        except Exception as exc:
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
