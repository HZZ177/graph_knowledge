"""Chat API - 知识图谱问答

基于 LangChain Agent 的自然语言问答接口。
支持多轮对话、流式输出、会话管理。
"""

import json
import uuid
from typing import List
from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db, SessionLocal
from backend.app.schemas.chat import StreamChatRequest, ConversationHistoryResponse, ConversationOut, AgentTypeOut
from backend.app.llm.langchain.configs import list_agent_configs
from backend.app.models.chat import Conversation
from backend.app.services.chat.chat_service import (
    streaming_chat,
    streaming_regenerate,
)
from backend.app.services import testing_service
from backend.app.services.chat.history_service import (
    get_conversation_history,
    clear_conversation,
    truncate_conversation,
    generate_conversation_title,
)
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger, trace_id_var


router = APIRouter(prefix="/llm", tags=["chat"])


@router.websocket("/chat/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 知识图谱问答接口（基于 LangChain）
    
    基于 LangChain Agent 的自然语言问答，支持：
    - 实体发现（业务流程、接口、数据资源）
    - 图上下文获取
    - 多轮对话（通过 thread_id 管理会话）
    - 流式输出
    
    协议：
    1. 客户端连接后发送 StreamChatRequest JSON: {"question": "...", "thread_id": "..."}
       - thread_id 可选，为空则创建新会话
    2. 服务端流式推送消息：
       - {"type": "start", "request_id": "...", "thread_id": "..."}
       - {"type": "stream", "content": "..."}
       - {"type": "tool_start", "tool_name": "...", "tool_input": {...}}
       - {"type": "tool_end", "tool_name": "..."}
       - {"type": "result", "thread_id": "...", "content": "...", "tool_calls": [...]}
       - {"type": "error", "error": "..."}
    """
    await websocket.accept()
    
    # 设置traceid到ContextVar，以便在agent和tools中传播
    trace_id = websocket.query_params.get("trace_id") or \
               websocket.headers.get("X-Trace-Id") or \
               uuid.uuid4().hex
    token = trace_id_var.set(trace_id)
    
    logger.info("WebSocket 连接已建立 - 知识图谱问答")
    
    db: Session = SessionLocal()
    
    try:
        # 接收请求数据
        data = await websocket.receive_text()
        logger.info(f"收到问答请求: {data[:200]}...")
        
        try:
            request = StreamChatRequest.model_validate_json(data)
        except Exception as e:
            logger.error(f"解析请求失败: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": f"请求格式错误: {str(e)}",
            }, ensure_ascii=False))
            return
        
        # ===== 根据 agent_type 分流处理 =====
        
        # 1. 智能测试助手 - 使用专用的三阶段状态机
        if request.agent_type == "intelligent_testing":
            if not request.testing_context:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "智能测试助手需要提供测试上下文（项目、需求信息）",
                }, ensure_ascii=False))
                return
            
            # 创建或获取会话 ID
            session_id = request.thread_id or str(uuid.uuid4())
            
            # 如果是新会话，先创建会话记录
            if not request.thread_id:
                await testing_service.create_testing_session(
                    db=db,
                    project_name=request.testing_context.project_name,
                    requirement_id=request.testing_context.requirement_id,
                    requirement_name=request.testing_context.requirement_name,
                    session_id=session_id,
                )
            
            # 执行测试工作流
            await testing_service.run_testing_workflow(
                db=db,
                session_id=session_id,
                requirement_id=request.testing_context.requirement_id,
                project_name=request.testing_context.project_name,
                requirement_name=request.testing_context.requirement_name,
                websocket=websocket,
            )
            return
        
        # 2. 日志排查助手 - 需要 log_query 上下文
        agent_context = None
        if request.agent_type == "log_troubleshoot":
            if not request.log_query:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "日志排查 Agent 需要选择业务线配置",
                }, ensure_ascii=False))
                return
            agent_context = {"log_query": request.log_query.model_dump()}
        
        # 3. 业务知识助手 (knowledge_qa) 和其他 Agent - 走通用流程
        await streaming_chat(
            db=db,
            question=request.question,
            websocket=websocket,
            thread_id=request.thread_id,
            agent_type=request.agent_type,
            agent_context=agent_context,
            attachments=[att.model_dump() for att in (request.attachments or [])],
        )
        
    except WebSocketDisconnect:
        logger.info("WebSocket 连接断开 - 知识图谱问答")
    except Exception as e:
        # 使用 lazy 格式化或直接传参，避免 str(e) 中包含大括号导致格式化错误
        logger.error("问答异常: {}", e)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": str(e),
            }, ensure_ascii=False))
        except:
            pass
    finally:
        trace_id_var.reset(token)
        db.close()
        try:
            await websocket.close()
        except:
            pass


@router.get("/agents", response_model=List[AgentTypeOut])
async def get_agent_types():
    """获取可用的 Agent 类型列表
    
    返回所有已注册的 Agent 类型，包括名称、描述、图标等信息。
    前端可用于展示 Agent 选择器。
    """
    return list_agent_configs()


@router.get("/conversations", response_model=List[ConversationOut])
async def list_conversations(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """获取会话列表（按更新时间倒序）"""
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()
    return convs


@router.delete("/conversation/{thread_id}")
async def delete_conversation(thread_id: str, db: Session = Depends(get_db)):
    """删除会话（同时清除元数据和历史记录）"""
    # 1. 删除元数据
    conv = db.query(Conversation).filter(Conversation.id == thread_id).first()
    if conv:
        db.delete(conv)
        db.commit()
    
    # 2. 清除 Checkpoint 历史
    await clear_conversation(thread_id)
    
    return success_response(message="会话已删除")


@router.get("/conversation/{thread_id}", response_model=ConversationHistoryResponse)
async def get_conversation(thread_id: str):
    messages = await get_conversation_history(thread_id)
    return ConversationHistoryResponse(thread_id=thread_id, messages=messages)


@router.post("/conversation/{thread_id}/title")
async def generate_title(thread_id: str, db: Session = Depends(get_db)):
    """生成会话标题"""
    title = await generate_conversation_title(db, thread_id)
    return {"thread_id": thread_id, "title": title}


@router.post("/conversation/{thread_id}/truncate")
async def truncate_history(thread_id: str, keep_pairs: int = Body(..., embed=True)):
    """截断会话历史，只保留前 N 对对话
    
    Args:
        thread_id: 会话 ID
        keep_pairs: 保留的对话对数（一对 = 一个 user + 对应的 assistant 回复）
    """
    success = await truncate_conversation(thread_id, keep_pairs)
    if success:
        return success_response(message=f"已截断到前 {keep_pairs} 对对话")
    else:
        return error_response(message="截断失败")


@router.websocket("/chat/regenerate/ws")
async def websocket_regenerate(websocket: WebSocket):
    """精准重新生成指定 AI 回复的 WebSocket 接口
    
    协议：
    1. 客户端发送: {"thread_id": "...", "user_msg_index": N}
       - user_msg_index: 第几个用户消息（从0开始）
    2. 服务端流式推送与 chat/ws 相同格式的消息
    """
    await websocket.accept()
    
    # 设置traceid到ContextVar，以便在agent和tools中传播
    trace_id = websocket.query_params.get("trace_id") or \
               websocket.headers.get("X-Trace-Id") or \
               uuid.uuid4().hex
    token = trace_id_var.set(trace_id)
    
    logger.info("WebSocket 连接已建立 - 重新生成")
    
    db: Session = SessionLocal()
    
    try:
        data = await websocket.receive_text()
        logger.info(f"收到重新生成请求: {data}")
        
        import json
        request = json.loads(data)
        thread_id = request.get("thread_id")
        user_msg_index = request.get("user_msg_index", 0)
        agent_type = request.get("agent_type", "knowledge_qa")
        
        if not thread_id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": "thread_id 是必需的",
            }, ensure_ascii=False))
            return
        
        await streaming_regenerate(
            db=db,
            thread_id=thread_id,
            user_msg_index=user_msg_index,
            websocket=websocket,
            agent_type=agent_type,
        )
        
    except WebSocketDisconnect:
        logger.info("WebSocket 连接断开 - 重新生成")
    except Exception as e:
        logger.error(f"重新生成异常: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": str(e),
            }, ensure_ascii=False))
        except:
            pass
    finally:
        trace_id_var.reset(token)
        db.close()
        try:
            await websocket.close()
        except:
            pass


@router.get("/log-query/options")
async def get_log_query_options():
    """获取日志查询的可选配置
    
    返回业务线列表和私有化集团列表，用于前端下拉选择。
    """
    from backend.app.llm.langchain.tools.log import BusinessLine, PrivateServer
    
    return success_response(data={
        "businessLines": [{"value": bl.value, "label": bl.value} for bl in BusinessLine],
        "privateServers": [{"value": ps.value, "label": ps.value} for ps in PrivateServer],
    })
