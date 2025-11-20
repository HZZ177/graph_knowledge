from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.services.canvas_service import (
    get_process_canvas,
    save_process_canvas,
)
from backend.app.core.logger import logger


router = APIRouter(prefix="/canvas", tags=["canvas"])


@router.get("/{process_id}")
def get_canvas(process_id: str, db: Session = Depends(get_db)) -> dict:
    """获取指定流程的画布信息。"""

    logger.info("[CanvasAPI] 获取流程画布 process_id=%s", process_id)
    try:
        data = get_process_canvas(db, process_id)
        logger.info(
            "[CanvasAPI] 获取画布成功 process_id=%s, steps=%d, edges=%d",
            process_id,
            len(data.get("steps", [])),
            len(data.get("edges", [])),
        )
        return data
    except ValueError:
        logger.warning("[CanvasAPI] 获取画布失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(status_code=404, detail="Process not found")


@router.put("/{process_id}")
def save_canvas(process_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
    """保存流程画布：包含步骤、连线、实现与数据资源关系。"""

    logger.info(
        "[CanvasAPI] 保存流程画布开始 process_id=%s, steps=%d, edges=%d",
        process_id,
        len((payload or {}).get("steps", [])),
        len((payload or {}).get("edges", [])),
    )
    try:
        data = save_process_canvas(db, process_id, payload)
        logger.info("[CanvasAPI] 保存流程画布成功 process_id=%s", process_id)
        return data
    except ValueError:
        logger.warning("[CanvasAPI] 保存画布失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(status_code=404, detail="Process not found")
