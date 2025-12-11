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
from backend.app.services.intelligent_testing_service import (
    create_testing_session,
)
from backend.app.services.chat.history_service import (
    get_conversation_history,
    clear_conversation,
    truncate_conversation,
    generate_conversation_title,
    get_testing_history,
)
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger, trace_id_var


router = APIRouter(prefix="/llm", tags=["chat"])


# ============================================================
# Agent 分流处理函数
# ============================================================

async def _handle_intelligent_testing(
    db: Session, 
    request: StreamChatRequest, 
    websocket: WebSocket
) -> None:
    """处理需求分析测试助手 (intelligent_testing)
    
    特点：
    - 三阶段工作流（analysis → plan → generate）
    - 每个阶段有独立的 thread_id
    - 需要 testing_context 提供项目和需求信息
    """
    if not request.testing_context:
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": "需求分析测试助手需要提供测试上下文（项目、需求信息）",
        }, ensure_ascii=False))
        return
    
    ctx = request.testing_context
    phase = ctx.phase or "analysis"
    
    # session_id 用于关联三个阶段，thread_id 用于当前阶段的对话
    session_id = ctx.session_id or str(uuid.uuid4())
    phase_thread_id = f"{session_id}_{phase}"
    
    # 如果是新任务（没有 session_id），创建会话记录并生成标题
    if not ctx.session_id:
        await create_testing_session(
            db=db,
            project_name=ctx.project_name,
            requirement_id=ctx.requirement_id,
            requirement_name=ctx.requirement_name,
            session_id=session_id,
        )
        
        # 立即生成标题：迭代名 - 需求名
        title_parts = []
        if ctx.iteration_name:
            title_parts.append(ctx.iteration_name)
        if ctx.requirement_name:
            title_parts.append(ctx.requirement_name)
        title = " - ".join(title_parts) if title_parts else f"测试任务 {ctx.requirement_id}"
        title = title[:30]  # 截断
        
        # 更新数据库标题
        conv = db.query(Conversation).filter(Conversation.id == session_id).first()
        if conv:
            conv.title = title
            db.commit()
        
        # 发送标题生成消息给前端
        await websocket.send_text(json.dumps({
            "type": "title_generated",
            "title": title,
            "thread_id": session_id,
        }, ensure_ascii=False))
        logger.info(f"[IntelligentTesting] 生成标题: {title}")
    
    # 构造阶段上下文
    agent_context = {
        "session_id": session_id,
        "phase": phase,
        "requirement_id": ctx.requirement_id,
        "project_name": ctx.project_name,
        "requirement_name": ctx.requirement_name,
    }
    
    # 调用通用流式对话服务
    await streaming_chat(
        db=db,
        question=request.question,
        websocket=websocket,
        thread_id=phase_thread_id,
        agent_type="intelligent_testing",
        agent_context=agent_context,
        attachments=[att.model_dump() for att in (request.attachments or [])],
    )


async def _handle_log_troubleshoot(
    db: Session, 
    request: StreamChatRequest, 
    websocket: WebSocket
) -> None:
    """处理日志排查助手 (log_troubleshoot)
    
    特点：
    - 需要 log_query 配置（业务线、私有化集团等）
    - 配置信息注入到 agent_context 供工具使用
    """
    if not request.log_query:
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": "日志排查助手需要选择业务线配置",
        }, ensure_ascii=False))
        return
    
    # 构造日志查询上下文
    agent_context = {
        "log_query": request.log_query.model_dump()
    }
    
    # 调用通用流式对话服务
    await streaming_chat(
        db=db,
        question=request.question,
        websocket=websocket,
        thread_id=request.thread_id,
        agent_type="log_troubleshoot",
        agent_context=agent_context,
        attachments=[att.model_dump() for att in (request.attachments or [])],
    )


async def _handle_knowledge_qa(
    db: Session, 
    request: StreamChatRequest, 
    websocket: WebSocket
) -> None:
    """处理业务知识助手 (knowledge_qa) 及其他通用 Agent
    
    特点：
    - 基于知识图谱的问答
    - 支持多轮对话
    - 无需额外配置上下文
    """
    # 调用通用流式对话服务
    await streaming_chat(
        db=db,
        question=request.question,
        websocket=websocket,
        thread_id=request.thread_id,
        agent_type=request.agent_type,
        agent_context=None,
        attachments=[att.model_dump() for att in (request.attachments or [])],
    )


async def _handle_opdoc_qa(
    db: Session, 
    request: StreamChatRequest, 
    websocket: WebSocket
) -> None:
    """处理操作文档问答 (opdoc_qa)
    
    特点：
    - 基于 LightRAG 的操作文档检索
    - 混合检索模式（向量 + 知识图谱）
    - 支持多轮对话
    - 无需额外配置上下文
    """
    # 调用通用流式对话服务
    await streaming_chat(
        db=db,
        question=request.question,
        websocket=websocket,
        thread_id=request.thread_id,
        agent_type="opdoc_qa",
        agent_context=None,
        attachments=[att.model_dump() for att in (request.attachments or [])],
    )


# ============================================================
# WebSocket 路由
# ============================================================

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
        # 每个 Agent 有独立的处理分支，便于维护和扩展
        
        # ----- 分支 1: 需求分析测试助手 (intelligent_testing) -----
        if request.agent_type == "intelligent_testing":
            await _handle_intelligent_testing(db, request, websocket)
            return
        
        # ----- 分支 2: 日志排查助手 (log_troubleshoot) -----
        elif request.agent_type == "log_troubleshoot":
            await _handle_log_troubleshoot(db, request, websocket)
            return
        
        # ----- 分支 3: 业务知识助手 (knowledge_qa) -----
        elif request.agent_type == "knowledge_qa":
            await _handle_knowledge_qa(db, request, websocket)
            return
        
        # ----- 分支 4: 操作文档问答 (opdoc_qa) -----
        elif request.agent_type == "opdoc_qa":
            await _handle_opdoc_qa(db, request, websocket)
            return

        # ----- 暂不支持的agent类型 -----
        else:
            logger.error(f"暂不支持的agent类型：{request.agent_type}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": f"暂不支持的agent类型：{request.agent_type}",
            }, ensure_ascii=False))

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


@router.get("/conversation/{session_id}/testing")
async def get_testing_conversation(session_id: str, db: Session = Depends(get_db)):
    """获取智能测试会话的完整历史
    
    合并三个阶段的消息，并返回任务面板状态数据。
    专门用于 intelligent_testing agent 的历史恢复。
    
    Returns:
        {
            "thread_id": session_id,
            "messages": [...],
            "phases": {...},
            "current_phase": "...",
            "status": "..."
        }
    """
    result = await get_testing_history(session_id, db)
    return {
        "thread_id": session_id,
        **result
    }


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


# ============================================================
# 测试助手阶段管理 API
# ============================================================

@router.get("/testing/{session_id}/status")
async def get_testing_session_status(session_id: str, db: Session = Depends(get_db)):
    """获取测试任务状态
    
    返回各阶段的解锁状态和摘要信息。
    """
    from backend.app.models.chat import TestSessionAnalysis
    
    # 获取会话信息
    conv = db.query(Conversation).filter(Conversation.id == session_id).first()
    if not conv:
        return error_response(message="会话不存在")
    
    # 获取各阶段摘要
    summaries = db.query(TestSessionAnalysis).filter(
        TestSessionAnalysis.session_id == session_id
    ).all()
    
    summary_map = {s.analysis_type: s.content for s in summaries}
    
    # 判断阶段解锁状态
    analysis_unlocked = True  # 阶段1永远解锁
    plan_unlocked = "requirement_summary" in summary_map
    generate_unlocked = "test_plan" in summary_map
    
    return success_response(data={
        "session_id": session_id,
        "status": conv.status,
        "current_phase": conv.current_phase,
        "phases": {
            "analysis": {
                "unlocked": analysis_unlocked,
                "has_summary": "requirement_summary" in summary_map,
                "thread_id": f"{session_id}_analysis",
            },
            "plan": {
                "unlocked": plan_unlocked,
                "has_summary": "test_plan" in summary_map,
                "thread_id": f"{session_id}_plan",
            },
            "generate": {
                "unlocked": generate_unlocked,
                "has_summary": "test_cases" in summary_map,
                "thread_id": f"{session_id}_generate",
            },
        },
        # 需求信息（用于前端锁定选择器显示）
        "requirement_id": conv.requirement_id,
        "requirement_name": conv.requirement_name,
        "project_name": conv.project_name,
    })


@router.post("/testing/{session_id}/clear-subsequent")
async def clear_subsequent_phases(
    session_id: str, 
    from_phase: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """清空指定阶段之后的所有内容
    
    当用户修改前序阶段时调用，清空后续阶段的摘要和对话。
    
    Args:
        session_id: 任务 ID
        from_phase: 从哪个阶段开始清空（不包括该阶段）
    """
    from backend.app.models.chat import TestSessionAnalysis
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    
    phase_order = ["analysis", "plan", "generate"]
    try:
        start_index = phase_order.index(from_phase) + 1
    except ValueError:
        return error_response(message=f"无效的阶段: {from_phase}")
    
    phases_to_clear = phase_order[start_index:]
    
    if not phases_to_clear:
        return success_response(message="没有需要清空的阶段")
    
    # 清空摘要
    analysis_types_to_clear = []
    if "plan" in phases_to_clear:
        analysis_types_to_clear.append("test_plan")
    if "generate" in phases_to_clear:
        analysis_types_to_clear.append("test_cases")
    
    if analysis_types_to_clear:
        db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type.in_(analysis_types_to_clear)
        ).delete(synchronize_session=False)
        db.commit()
    
    # TODO: 清空对话历史（需要操作 llm_checkpoints.db）
    # 这部分可以后续实现，目前只清空摘要
    
    return success_response(
        message=f"已清空阶段: {', '.join(phases_to_clear)}",
        data={"cleared_phases": phases_to_clear}
    )
