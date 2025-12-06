"""Skeleton API - 业务骨架生成

基于 CrewAI 多Agent协作的业务骨架自动生成接口。
"""

import json
import uuid
from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db, SessionLocal
from backend.app.schemas.skeleton import SkeletonGenerateRequest
from backend.app.schemas.canvas import SaveProcessCanvasRequest
from backend.app.services.skeleton.skeleton_service import generate_skeleton
from backend.app.services.canvas_service import save_process_canvas
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger, trace_id_var


router = APIRouter(prefix="/llm", tags=["skeleton"])


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
    
    # 设置traceid到ContextVar，以便在agent和tools中传播
    trace_id = websocket.query_params.get("trace_id") or \
               websocket.headers.get("X-Trace-Id") or \
               uuid.uuid4().hex
    token = trace_id_var.set(trace_id)
    
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
        trace_id_var.reset(token)
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
