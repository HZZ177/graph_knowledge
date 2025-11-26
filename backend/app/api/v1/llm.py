import json
from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db, SessionLocal
from backend.app.schemas.llm import ChatRequest, ChatResponse, StreamChatRequest
from backend.app.schemas.skeleton import SkeletonGenerateRequest
from backend.app.schemas.canvas import SaveProcessCanvasRequest
from backend.app.services.llm_chat_service import (
    answer_question_with_process_context,
    streaming_chat_with_context,
)
from backend.app.services.llm_skeleton_service import generate_skeleton
from backend.app.services.canvas_service import save_process_canvas
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/chat/ask", response_model=ChatResponse, summary="基于流程上下文的 LLM 问答接口")
async def chat(
    req: ChatRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = answer_question_with_process_context(
            db=db,
            question=req.question,
            process_id=req.process_id,
        )
        data = ChatResponse(
            answer=result["answer"],
            process_id=result.get("process_id"),
        )
        return success_response(data=data)
    except Exception as exc:
        return error_response(message=str(exc))


@router.websocket("/chat/ws/stream")
async def websocket_chat_stream(websocket: WebSocket):
    """WebSocket流式问答接口
    
    协议：
    1. 客户端连接后发送 StreamChatRequest JSON
    2. 服务端流式推送消息：
       - {"type": "start", "request_id": "..."}
       - {"type": "chunk", "content": "...", "request_id": "..."}
       - {"type": "done", "request_id": "...", "metadata": {...}}
       - {"type": "error", "error": "...", "request_id": "..."}
    """
    await websocket.accept()
    logger.info("WebSocket连接已建立 - 流式问答")
    
    db: Session = SessionLocal()
    
    try:
        # 接收请求数据
        data = await websocket.receive_text()
        logger.info(f"收到流式问答请求: {data[:200]}...")
        
        try:
            request = StreamChatRequest.parse_raw(data)
        except Exception as e:
            logger.error(f"解析请求失败: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": f"请求格式错误: {str(e)}",
            }, ensure_ascii=False))
            return
        
        # 流式生成响应
        async for message in streaming_chat_with_context(
            db=db,
            question=request.question,
            process_id=request.process_id,
        ):
            await websocket.send_text(json.dumps(
                message.to_dict(),
                ensure_ascii=False,
            ))
        
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开 - 流式问答")
    except Exception as e:
        logger.error(f"流式问答异常: {e}", exc_info=True)
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
        logger.info(f"骨架已保存到SQLite: {payload.process_id}")
        
        # 2. 同步到Neo4j
        sync_result = None
        try:
            sync_result = sync_process(db, payload.process_id)
            logger.info(f"骨架已同步到Neo4j: {payload.process_id}")
        except Exception as e:
            logger.warning(f"骨架同步Neo4j失败: {payload.process_id}, error={e}")
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


@router.post("/skeleton/preview")
async def preview_skeleton(
    payload: SkeletonGenerateRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    """非流式骨架预览（备用接口）
    
    如果前端不支持WebSocket，可以使用此接口
    注意：此接口不会返回中间进度，只返回最终结果
    """
    logger.info(f"非流式骨架预览: {payload.business_name}")
    
    collected_chunks = []
    
    async def collect_chunk(chunk: AgentStreamChunk):
        collected_chunks.append(chunk)
    
    try:
        canvas_data = await generate_skeleton_with_stream(db, payload, collect_chunk)
        
        return success_response(
            data=canvas_data.dict(),
            message="骨架生成成功",
        )
        
    except Exception as e:
        logger.error(f"骨架预览失败: {e}", exc_info=True)
        return error_response(message=f"骨架生成失败: {str(e)}")
