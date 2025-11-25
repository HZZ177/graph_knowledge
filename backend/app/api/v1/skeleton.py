"""骨架生成API - WebSocket流式接口"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Body
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db, SessionLocal
from backend.app.schemas.skeleton import (
    SkeletonGenerateRequest,
    AgentStreamChunk,
)
from backend.app.schemas.canvas import SaveProcessCanvasRequest
from backend.app.services.skeleton_service import generate_skeleton_with_stream
from backend.app.services.canvas_service import save_process_canvas
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/skeleton", tags=["skeleton"])


@router.websocket("/ws/generate")
async def websocket_generate_skeleton(websocket: WebSocket):
    """WebSocket骨架生成接口
    
    流程：
    1. 客户端连接后发送 SkeletonGenerateRequest JSON
    2. 服务端依次执行3个Agent，实时推送进度和流式内容
    3. 最终推送完整的画布数据
    
    消息类型（AgentStreamChunk.type）：
    - agent_start: Agent开始执行
    - stream: Agent流式输出片段
    - agent_end: Agent执行完成
    - result: 最终画布数据
    - error: 错误信息
    """
    await websocket.accept()
    logger.info("WebSocket连接已建立 - 骨架生成")
    
    db: Session = SessionLocal()
    
    try:
        # 1. 接收请求数据
        data = await websocket.receive_text()
        logger.info(f"收到骨架生成请求: {data[:200]}...")
        
        try:
            request = SkeletonGenerateRequest.parse_raw(data)
        except Exception as e:
            logger.error(f"解析请求失败: {e}")
            await websocket.send_text(AgentStreamChunk(
                type="error",
                agent_name="系统",
                agent_index=-1,
                error=f"请求格式错误: {str(e)}",
            ).json())
            return
        
        # 2. 定义流式回调
        async def send_chunk(chunk: AgentStreamChunk):
            try:
                await websocket.send_text(chunk.json())
            except Exception as e:
                logger.warning(f"发送WebSocket消息失败: {e}")
        
        # 3. 执行骨架生成（带流式回调）
        logger.info(f"开始生成骨架: {request.business_name}")
        canvas_data = await generate_skeleton_with_stream(db, request, send_chunk)
        logger.info(f"骨架生成完成: {request.business_name}")
        
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开 - 骨架生成")
    except Exception as e:
        logger.error(f"骨架生成异常: {e}", exc_info=True)
        try:
            await websocket.send_text(AgentStreamChunk(
                type="error",
                agent_name="系统",
                agent_index=-1,
                error=str(e),
            ).json())
        except:
            pass
    finally:
        db.close()
        try:
            await websocket.close()
        except:
            pass


@router.post("/confirm")
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


@router.post("/preview")
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
