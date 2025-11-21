from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.services.canvas_service import (
    get_process_canvas,
    save_process_canvas,
)
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.logger import logger


router = APIRouter(prefix="/canvas", tags=["canvas"])


@router.get("/{process_id}")
def get_canvas(process_id: str, db: Session = Depends(get_db)) -> dict:
    """获取指定流程的画布信息。"""

    logger.info(f"获取流程画布 process_id={process_id}")
    try:
        data = get_process_canvas(db, process_id)
        logger.info(
            f"获取画布成功 process_id={process_id}, steps={len(data.get('steps', []))}, edges={len(data.get('edges', []))}"
        )
        return data
    except ValueError:
        logger.warning(f"获取画布失败，流程不存在 process_id={process_id}")
        raise HTTPException(status_code=404, detail="Process not found")


@router.put("/{process_id}")
def save_canvas(process_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
    """保存流程画布：包含步骤、连线、实现与数据资源关系。"""

    logger.info(
        f"保存流程画布开始 process_id={process_id}, steps={len((payload or {}).get('steps', []))}, edges={len((payload or {}).get('edges', []))}"
    )
    try:
        # 1. 保存到 SQLite
        data = save_process_canvas(db, process_id, payload)
        
        # 2. 同步到 Neo4j
        try:
            logger.info(f"同步流程到图数据库 process_id={process_id}")
            sync_process(db, process_id)
        except Exception as e:
            logger.warning(f"同步到 Neo4j 失败 process_id={process_id}, error={e}")
            # 继续返回结果，不影响 SQLite 保存
        
        logger.info(f"保存流程画布成功 process_id={process_id}")
        return data
    except ValueError:
        logger.warning(f"保存画布失败，流程不存在 process_id={process_id}")
        raise HTTPException(status_code=404, detail="Process not found")
