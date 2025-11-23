from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from ...services.graph_query_service import get_process_context

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/get_process_context/{process_id}")
async def get_process_context_endpoint(
    process_id: str, db: Session = Depends(get_db)
) -> dict:
    """获取指定流程在图数据库中的上下文信息。

    包含流程节点、步骤、实现、数据资源及相关连线，用于图分析或可视化。
    """
    try:
        return get_process_context(db, process_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Process not found")
