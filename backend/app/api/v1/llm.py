from typing import List
from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db, SessionLocal
from backend.app.schemas.llm import StreamChatRequest, ConversationHistoryResponse, ConversationOut
from backend.app.schemas.skeleton import SkeletonGenerateRequest
from backend.app.schemas.canvas import SaveProcessCanvasRequest
from backend.app.models.conversation import Conversation
from backend.app.services.llm_chat_service import (
    streaming_chat,
    get_conversation_history,
    clear_conversation,
)
from backend.app.llm.langchain_chat_agent import generate_conversation_title
from backend.app.services.llm_skeleton_service import generate_skeleton
from backend.app.services.canvas_service import save_process_canvas
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/llm", tags=["llm"])


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
        
        # 调用流式问答服务（支持多轮对话）
        await streaming_chat(
            db=db,
            question=request.question,
            websocket=websocket,
            thread_id=request.thread_id,
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
        db.close()
        try:
            await websocket.close()
        except:
            pass


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


@router.websocket("/skeleton/ws/generate")
async def websocket_generate_skeleton(websocket: WebSocket):
    """WebSocket 骨架生成接口
    
    流程：
    1. 客户端连接后发送 SkeletonGenerateRequest JSON
    2. 服务端依次执行 3 个 Agent，实时推送进度和流式内容
    3. 最终推送完整的画布数据
    
    消息类型：
    - agent_start: Agent 开始执行
    - stream: Agent 流式输出片段
    - agent_end: Agent 执行完成
    - result: 最终画布数据
    - error: 错误信息
    """
    await websocket.accept()
    logger.info("WebSocket 连接已建立 - 骨架生成")
    
    db: Session = SessionLocal()
    
    try:
        # 1. 接收请求数据
        data = await websocket.receive_text()
        logger.info(f"收到骨架生成请求: {data[:200]}...")
        
        try:
            request = SkeletonGenerateRequest.parse_raw(data)
        except Exception as e:
            logger.error(f"解析请求失败: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "agent_name": "系统",
                "agent_index": -1,
                "error": f"请求格式错误: {str(e)}",
            }))
            return
        
        # 2. 直接调用 service，传入 websocket，无需回调
        logger.info(f"开始生成骨架: {request.business_name}")
        await generate_skeleton(db, request, websocket)
        logger.info(f"骨架生成完成: {request.business_name}")
        
    except WebSocketDisconnect:
        logger.info("WebSocket 连接断开 - 骨架生成")
    except Exception as e:
        logger.error(f"骨架生成异常: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "agent_name": "系统",
                "agent_index": -1,
                "error": str(e),
            }))
        except Exception:
            pass
    finally:
        db.close()
        try:
            await websocket.close()
        except:
            pass


@router.post("/skeleton/confirm")
async def confirm_skeleton(
    payload: SaveProcessCanvasRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    """确认骨架，创建节点和关系
    
    接收前端预览后确认的画布数据，写入数据库并同步到Neo4j
    """
    logger.info(f"确认骨架: process_id={payload.process_id}, name={payload.process.name}")
    
    try:
        # 1. 保存到SQLite
        data = save_process_canvas(db, payload.process_id, payload.dict())
        # 获取实际保存的 process_id（可能因名称去重而变化）
        actual_process_id = data.get("process", {}).get("process_id") or payload.process_id
        logger.info(f"骨架已保存到SQLite: {actual_process_id}")
        
        # 2. 同步到Neo4j（使用实际的 process_id）
        sync_result = None
        try:
            sync_result = sync_process(db, actual_process_id)
            logger.info(f"骨架已同步到Neo4j: {actual_process_id}")
        except Exception as e:
            logger.warning(f"骨架同步Neo4j失败: {actual_process_id}, error={e}")
            sync_result = {
                "success": False,
                "message": str(e),
            }
        
        result = {
            **data,
            "sync_result": sync_result,
        }
        
        return success_response(data=result, message="骨架已确认并创建")
        
    except Exception as e:
        logger.error(f"确认骨架失败: {e}", exc_info=True)
        return error_response(message=f"确认骨架失败: {str(e)}")
