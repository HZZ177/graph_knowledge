from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from ...services.graph_query_service import get_process_context

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/processes/{process_id}/context")
async def get_process_context_endpoint(
    process_id: str, db: Session = Depends(get_db)
) -> dict:
    try:
        return get_process_context(db, process_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Process not found")
