"""LLM Chat 服务 - 基于 LangChain 的知识图谱问答

支持：
- 自然语言实体发现（业务流程、接口、数据资源）
- 图上下文获取和探索
- 多轮对话（通过 thread_id 管理会话历史）
- 流式输出
"""

import json
import uuid
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from datetime import datetime, timezone
from backend.app.models.conversation import Conversation
from backend.app.llm.langchain_chat_agent import (
    create_chat_agent,
    get_agent_config,
    get_thread_history,
    clear_thread_history,
)
from backend.app.core.logger import logger


async def streaming_chat(
    db: Session,
    question: str,
    websocket: WebSocket,
    thread_id: Optional[str] = None,
) -> str:
    """基于 LangChain 的流式问答
    
    使用 LangChain Agent + 8 个工具实现自然语言问答。
    支持多轮对话，通过 thread_id 管理会话历史。
    
    Args:
        db: 数据库会话
        question: 用户问题
        websocket: WebSocket 连接，用于流式输出
        thread_id: 会话 ID，用于多轮对话。如果为空则创建新会话。
        
    Returns:
        完整的回答文本
    """
    # 生成请求 ID 和会话 ID
    request_id = str(uuid.uuid4())
    if not thread_id:
        thread_id = str(uuid.uuid4())
        
    # 维护 Conversation 元数据
    try:
        conv = db.query(Conversation).filter(Conversation.id == thread_id).first()
        if not conv:
            conv = Conversation(id=thread_id, title="新对话")
            db.add(conv)
        else:
            conv.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"保存会话元数据失败: {e}")
        # 不阻断主流程
    
    logger.info(f"[Chat] 开始处理问题: {question[:100]}..., request_id={request_id}, thread_id={thread_id}")
    
    try:
        # 发送开始消息
        await websocket.send_text(json.dumps({
            "type": "start",
            "request_id": request_id,
            "thread_id": thread_id,
        }, ensure_ascii=False))
        
        # 打开 AsyncSqliteSaver 作为检查点存储
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as checkpointer:
            # 创建 Agent
            agent = create_chat_agent(db, checkpointer=checkpointer)
            config = get_agent_config(thread_id)
            
            # 构造输入
            inputs = {
                "messages": [HumanMessage(content=question)]
            }
            
            # 流式执行
            full_response = ""
            tool_calls_info: List[Dict[str, Any]] = []
            
            logger.debug(f"[Chat] 开始流式执行, inputs={inputs}, config={config}")
            
            async for event in agent.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                
                # 检查是否有错误
                if "error" in event:
                    error_info = event.get("error")
                    logger.error(f"[Chat] 事件包含错误: {error_info}")
                    raise Exception(f"Agent 执行错误: {error_info}")
                
                # 处理不同类型的事件
                if event_type == "on_chat_model_stream":
                    # LLM 流式输出
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        full_response += content
                        await websocket.send_text(json.dumps({
                            "type": "stream",
                            "content": content,
                        }, ensure_ascii=False))
                        
                elif event_type == "on_tool_start":
                    # 工具开始调用
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    logger.debug(f"[Chat] 工具调用: {tool_name}, 输入: {tool_input}")
                    await websocket.send_text(json.dumps({
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                    }, ensure_ascii=False))
                    
                elif event_type == "on_tool_end":
                    # 工具调用结束
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    # tool_output 可能是 ToolMessage 对象，需要转换为字符串
                    output_str = str(tool_output.content) if hasattr(tool_output, "content") else str(tool_output)
                    # 截断过长的输出用于日志
                    output_preview = output_str[:200] + "..." if len(output_str) > 200 else output_str
                    logger.debug(f"[Chat] 工具返回: {tool_name}, 输出: {output_preview}")
                    tool_calls_info.append({
                        "name": tool_name,
                        "output_length": len(str(tool_output)),
                    })
                    await websocket.send_text(json.dumps({
                        "type": "tool_end",
                        "tool_name": tool_name,
                    }, ensure_ascii=False))
                    
                elif event_type == "on_chain_error":
                    # 链式错误
                    error_data = event.get("data", {})
                    logger.error(f"[Chat] Chain 错误: {error_data}")
                    raise Exception(f"Chain 执行错误: {error_data}")
        
        # 发送最终结果消息
        await websocket.send_text(json.dumps({
            "type": "result",
            "request_id": request_id,
            "thread_id": thread_id,
            "content": full_response,
            "tool_calls": tool_calls_info,
        }, ensure_ascii=False))
        
        logger.info(f"[Chat] 问答完成, request_id={request_id}, 输出长度: {len(full_response)}, 工具调用: {len(tool_calls_info)}")
        return full_response
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error("[Chat] 问答失败: " + str(e) + "\n" + error_traceback)
        await websocket.send_text(json.dumps({
            "type": "error",
            "request_id": request_id,
            "thread_id": thread_id,
            "error": str(e),
            "traceback": error_traceback,
        }, ensure_ascii=False))
        raise


async def get_conversation_history(thread_id: str) -> List[Dict[str, str]]:
    """获取会话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        消息列表 [{"role": "user"|"assistant", "content": "..."}]
    """
    return await get_thread_history(thread_id)


async def clear_conversation(thread_id: str) -> bool:
    """清除会话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        是否成功
    """
    return await clear_thread_history(thread_id)
