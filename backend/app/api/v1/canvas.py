from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.services.canvas_service import (
    get_process_canvas,
    save_process_canvas,
)
from backend.app.schemas.canvas import SaveProcessCanvasRequest
from backend.app.core.utils import success_response, error_response
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.logger import logger

router = APIRouter(prefix="/canvas", tags=["canvas"])


@router.get("/get_process_canvas")
def get_canvas(
    process_id: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """获取指定流程的画布信息。"""

    logger.info(f"获取流程画布 process_id={process_id}")
    try:
        data = get_process_canvas(db, process_id)
        logger.info(
            f"获取画布成功 process_id={process_id}, steps={len(data.get('steps', []))}, edges={len(data.get('edges', []))}"
        )
        return success_response(data=data)
    except ValueError:
        logger.warning(f"获取画布失败，流程不存在 process_id={process_id}")
        return error_response(message="Process not found")


@router.post("/save_process_canvas")
def save_canvas(
    payload: SaveProcessCanvasRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    """保存流程画布：包含步骤、连线、实现与数据资源关系。
    
    Returns:
        包含画布数据和同步状态的信息
    """

    process_id = payload.process_id
    payload_dict = payload.dict(exclude={"process_id"})

    logger.info(
        f"保存流程画布开始 process_id={process_id}, steps={len((payload_dict or {}).get('steps', []))}, edges={len((payload_dict or {}).get('edges', []))}"
    )
    try:
        # 1. 保存到 SQLite
        data = save_process_canvas(db, process_id, payload_dict)
        logger.info(f"保存到SQLite成功 process_id={process_id}")

        # 2. 同步到 Neo4j
        sync_result = None
        try:
            logger.info(f"同步流程到图数据库 process_id={process_id}")
            sync_result = sync_process(db, process_id)
            logger.info(f"同步到Neo4j成功 process_id={process_id}")
        except Exception as e:
            logger.warning(f"同步到 Neo4j 失败 process_id={process_id}, error={e}")
            from backend.app.services.graph_sync_service import SyncError
            if isinstance(e, SyncError):
                sync_result = {
                    "success": False,
                    "message": e.message,
                    "error_type": e.error_type,
                    "synced_at": None
                }
            else:
                sync_result = {
                    "success": False,
                    "message": str(e),
                    "error_type": "unknown_error",
                    "synced_at": None
                }

        logger.info(f"保存流程画布完成 process_id={process_id}")

        # 返回画布数据和同步状态
        result = {
            **data,
            "sync_result": sync_result,
        }
        return success_response(data=result, message="保存流程画布成功")
    except ValueError:
        logger.warning(f"保存画布失败，流程不存在 process_id={process_id}")
        return error_response(message="Process not found")
