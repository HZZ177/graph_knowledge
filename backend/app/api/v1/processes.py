from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.models.resource_graph import ProcessStepEdge
from ...services import process_service
from ...services.graph_sync_service import sync_process
from backend.app.core.logger import logger


router = APIRouter(prefix="/processes", tags=["processes"])


class ProcessBase(BaseModel):
    name: str
    channel: str | None = None
    description: str | None = None
    entrypoints: List[str] | None = None


class ProcessCreate(ProcessBase):
    process_id: str


class ProcessUpdate(ProcessBase):
    pass


class ProcessStep(BaseModel):
    step_id: int
    process_id: str
    order_no: int
    name: str | None = None
    capability_id: str | None = None


class ProcessEdgeBase(BaseModel):
    from_step_id: str
    to_step_id: str
    edge_type: str | None = None
    condition: str | None = None
    label: str | None = None


class ProcessEdgeCreate(ProcessEdgeBase):
    pass


class ProcessEdgeUpdate(BaseModel):
    from_step_id: str | None = None
    to_step_id: str | None = None
    edge_type: str | None = None
    condition: str | None = None
    label: str | None = None


class ProcessEdgeOut(ProcessEdgeBase):
    id: int

    class Config:
        from_attributes = True


@router.get("", summary="列出流程")
async def list_processes(db: Session = Depends(get_db)) -> list[dict]:
    """返回流程列表，数据来自 sqlite 数据库。"""

    logger.info("[ProcessAPI] 列出业务流程列表")
    items = process_service.list_processes(db)
    logger.info("[ProcessAPI] 共返回 %d 条流程记录", len(items))
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_process(payload: ProcessCreate, db: Session = Depends(get_db)) -> dict:
    logger.info("[ProcessAPI] 创建流程 process_id=%s", payload.process_id)
    try:
        data = process_service.create_process(db, payload.dict())
        logger.info("[ProcessAPI] 创建流程成功 process_id=%s", payload.process_id)
        return data
    except ValueError as exc:
        logger.warning(
            "[ProcessAPI] 创建流程失败 process_id=%s, error=%s",
            payload.process_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/{process_id}")
async def get_process(process_id: str, db: Session = Depends(get_db)) -> dict:
    logger.info("[ProcessAPI] 获取流程详情 process_id=%s", process_id)
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning("[ProcessAPI] 流程不存在 process_id=%s", process_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    return record


@router.put("/{process_id}")
async def update_process(
    process_id: str, payload: ProcessUpdate, db: Session = Depends(get_db)
) -> dict:
    logger.info("[ProcessAPI] 更新流程 process_id=%s", process_id)
    try:
        data = process_service.update_process(
            db,
            process_id,
            payload.dict(exclude_unset=True),
        )
        logger.info("[ProcessAPI] 更新流程成功 process_id=%s", process_id)
        return data
    except ValueError:
        logger.warning("[ProcessAPI] 更新流程失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )


@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(process_id: str, db: Session = Depends(get_db)) -> None:
    logger.info("[ProcessAPI] 删除流程 process_id=%s", process_id)
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning("[ProcessAPI] 删除流程失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    process_service.delete_process(db, process_id)
    logger.info("[ProcessAPI] 删除流程成功 process_id=%s", process_id)


@router.get("/{process_id}/steps")
async def get_process_steps(process_id: str, db: Session = Depends(get_db)) -> list[dict]:
    logger.info("[ProcessAPI] 获取流程步骤 process_id=%s", process_id)
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning("[ProcessAPI] 获取流程步骤失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    return process_service.get_process_steps(db, process_id)


@router.put("/{process_id}/steps")
async def save_process_steps(
    process_id: str, items: List[ProcessStep], db: Session = Depends(get_db)
) -> list[dict]:
    record = process_service.get_process(db, process_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )
    plain_items = [item.dict() for item in items]
    return process_service.save_process_steps(db, process_id, plain_items)


@router.delete("/{process_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process_step(
    process_id: str, step_id: int, db: Session = Depends(get_db)
) -> None:
    logger.info("[ProcessAPI] 删除流程步骤 process_id=%s, step_id=%s", process_id, step_id)
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning("[ProcessAPI] 删除流程步骤失败，流程不存在 process_id=%s", process_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    process_service.delete_process_step(db, process_id, step_id)


@router.get("/{process_id}/edges", response_model=List[ProcessEdgeOut])
async def list_process_edges(
    process_id: str, db: Session = Depends(get_db)
) -> List[ProcessEdgeOut]:
    # 直接基于 sqlite 中的 ProcessStepEdge 表返回边列表
    edges = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .order_by(ProcessStepEdge.id)
        .all()
    )
    return [ProcessEdgeOut.from_orm(e) for e in edges]


@router.post(
    "/{process_id}/edges",
    response_model=ProcessEdgeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_process_edge(
    process_id: str, payload: ProcessEdgeCreate, db: Session = Depends(get_db)
) -> ProcessEdgeOut:
    # 保持与 SAMPLE_DATA 的流程 ID 一致性
    record = process_service.get_process(db, process_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )

    edge = ProcessStepEdge(
        process_id=process_id,
        from_step_id=payload.from_step_id,
        to_step_id=payload.to_step_id,
        edge_type=payload.edge_type,
        condition=payload.condition,
        label=payload.label,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    logger.info(
        "[ProcessAPI] 更新流程边成功 process_id=%s, edge_id=%s",
        process_id,
        edge_id,
    )
    return ProcessEdgeOut.from_orm(edge)


@router.put("/{process_id}/edges/{edge_id}", response_model=ProcessEdgeOut)
async def update_process_edge(
    process_id: str,
    edge_id: int,
    payload: ProcessEdgeUpdate,
    db: Session = Depends(get_db),
) -> ProcessEdgeOut:
    edge = (
        db.query(ProcessStepEdge)
        .filter(
            ProcessStepEdge.id == edge_id,
            ProcessStepEdge.process_id == process_id,
        )
        .first()
    )
    if not edge:
        logger.warning(
            "[ProcessAPI] 更新流程边失败，未找到边 process_id=%s, edge_id=%s",
            process_id,
            edge_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程边不存在",
        )

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(edge, field, value)

    db.commit()
    db.refresh(edge)
    return ProcessEdgeOut.from_orm(edge)


@router.delete("/{process_id}/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process_edge(
    process_id: str, edge_id: int, db: Session = Depends(get_db)
) -> None:
    edge = (
        db.query(ProcessStepEdge)
        .filter(
            ProcessStepEdge.id == edge_id,
            ProcessStepEdge.process_id == process_id,
        )
        .first()
    )
    if not edge:
        logger.warning(
            "[ProcessAPI] 删除流程边失败，未找到边 process_id=%s, edge_id=%s",
            process_id,
            edge_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程边不存在",
        )

    db.delete(edge)
    db.commit()
    logger.info(
        "[ProcessAPI] 删除流程边成功 process_id=%s, edge_id=%s",
        process_id,
        edge_id,
    )


@router.post("/{process_id}/publish")
async def publish_process(process_id: str, db: Session = Depends(get_db)) -> dict:
    record = process_service.get_process(db, process_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )

    try:
        sync_process(db, process_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )

    return {"status": "ok"}
