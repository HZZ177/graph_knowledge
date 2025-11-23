from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.models.resource_graph import ProcessStepEdge
from backend.app.schemas.processes import (
    ProcessCreate,
    ProcessUpdate,
    ProcessStep,
    ProcessEdgeCreate,
    ProcessEdgeUpdate,
    ProcessEdgeOut,
)
from ...services import process_service
from ...services.graph_sync_service import sync_process
from backend.app.core.logger import logger


router = APIRouter(prefix="/processes", tags=["processes"])


@router.get("/list_processes", summary="列出流程")
async def list_processes(db: Session = Depends(get_db)) -> list[dict]:
    """返回流程列表，数据来自 sqlite 数据库。"""

    items = process_service.list_processes(db)
    logger.info(f"列出业务流程列表，共返回 {len(items)} 条记录")
    return items


@router.post("/create_process", status_code=status.HTTP_201_CREATED)
async def create_process(payload: ProcessCreate, db: Session = Depends(get_db)) -> dict:
    """创建业务流程。

    根据请求体中的流程基础信息在 sqlite 中创建一条新的流程记录。
    """
    logger.info(f"创建流程 process_id={payload.process_id}")
    try:
        data = process_service.create_process(db, payload.dict())
        logger.info(f"创建流程成功 process_id={payload.process_id}")
        return data
    except ValueError as exc:
        logger.warning(f"创建流程失败 process_id={payload.process_id}, error={exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/get_process/{process_id}")
async def get_process(process_id: str, db: Session = Depends(get_db)) -> dict:
    """获取单个业务流程详情。

    如果指定的流程不存在，则返回 404。
    """
    logger.info(f"获取流程详情 process_id={process_id}")
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning(f"流程不存在 process_id={process_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    return record


@router.post("/update_process/{process_id}")
async def update_process(
    process_id: str, payload: ProcessUpdate, db: Session = Depends(get_db)
) -> dict:
    """更新业务流程的基础信息。

    仅更新请求体中提供的字段，如果流程不存在则返回 404。
    """
    logger.info(f"更新流程 process_id={process_id}")
    try:
        data = process_service.update_process(
            db,
            process_id,
            payload.dict(exclude_unset=True),
        )
        logger.info(f"更新流程成功 process_id={process_id}")
        return data
    except ValueError:
        logger.warning(f"更新流程失败，流程不存在 process_id={process_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )


@router.post("/delete_process/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(process_id: str, db: Session = Depends(get_db)) -> None:
    """删除指定的业务流程。

    如果流程不存在则返回 404，成功时返回 204 无内容。
    """
    logger.info(f"删除流程 process_id={process_id}")
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning(f"删除流程失败，流程不存在 process_id={process_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    process_service.delete_process(db, process_id)
    logger.info(f"删除流程成功 process_id={process_id}")


@router.get("/get_process_steps/{process_id}")
async def get_process_steps(process_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """获取指定流程下的全部步骤列表。"""
    logger.info(f"获取流程步骤 process_id={process_id}")
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning(f"获取流程步骤失败，流程不存在 process_id={process_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    return process_service.get_process_steps(db, process_id)


@router.post("/save_process_steps/{process_id}")
async def save_process_steps(
    process_id: str, items: List[ProcessStep], db: Session = Depends(get_db)
) -> list[dict]:
    """保存指定流程的步骤列表。

    用请求体中的步骤列表整体替换原有的步骤配置。
    """
    record = process_service.get_process(db, process_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )
    plain_items = [item.dict() for item in items]
    return process_service.save_process_steps(db, process_id, plain_items)


@router.post("/delete_process_step/{process_id}/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process_step(
    process_id: str, step_id: int, db: Session = Depends(get_db)
) -> None:
    """删除指定流程中的单个步骤。"""
    logger.info(f"删除流程步骤 process_id={process_id}, step_id={step_id}")
    record = process_service.get_process(db, process_id)
    if record is None:
        logger.warning(f"删除流程步骤失败，流程不存在 process_id={process_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程不存在",
        )
    process_service.delete_process_step(db, process_id, step_id)


@router.get("/list_process_edges/{process_id}", response_model=List[ProcessEdgeOut])
async def list_process_edges(
    process_id: str, db: Session = Depends(get_db)
) -> List[ProcessEdgeOut]:
    """列出指定流程中所有步骤之间的边。"""
    # 直接基于 sqlite 中的 ProcessStepEdge 表返回边列表
    edges = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .order_by(ProcessStepEdge.id)
        .all()
    )
    return [ProcessEdgeOut.from_orm(e) for e in edges]


@router.post(
    "/create_process_edge/{process_id}",
    response_model=ProcessEdgeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_process_edge(
    process_id: str, payload: ProcessEdgeCreate, db: Session = Depends(get_db)
) -> ProcessEdgeOut:
    """在指定流程中创建一条步骤之间的边。"""
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
    logger.info(f"创建流程边成功 process_id={process_id}")
    return ProcessEdgeOut.from_orm(edge)


@router.post("/update_process_edge/{process_id}/{edge_id}", response_model=ProcessEdgeOut)
async def update_process_edge(
    process_id: str,
    edge_id: int,
    payload: ProcessEdgeUpdate,
    db: Session = Depends(get_db),
) -> ProcessEdgeOut:
    """更新指定流程中某条边的属性。"""
    edge = (
        db.query(ProcessStepEdge)
        .filter(
            ProcessStepEdge.id == edge_id,
            ProcessStepEdge.process_id == process_id,
        )
        .first()
    )
    if not edge:
        logger.warning(f"更新流程边失败，未找到边 process_id={process_id}, edge_id={edge_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程边不存在",
        )

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(edge, field, value)

    db.commit()
    db.refresh(edge)
    return ProcessEdgeOut.from_orm(edge)


@router.post("/delete_process_edge/{process_id}/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process_edge(
    process_id: str, edge_id: int, db: Session = Depends(get_db)
) -> None:
    """删除指定流程中的一条边。"""
    edge = (
        db.query(ProcessStepEdge)
        .filter(
            ProcessStepEdge.id == edge_id,
            ProcessStepEdge.process_id == process_id,
        )
        .first()
    )
    if not edge:
        logger.warning(f"删除流程边失败，未找到边 process_id={process_id}, edge_id={edge_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="流程边不存在",
        )

    db.delete(edge)
    db.commit()
    logger.info(f"删除流程边成功 process_id={process_id}, edge_id={edge_id}")


@router.post("/publish_process/{process_id}")
async def publish_process(process_id: str, db: Session = Depends(get_db)) -> dict:
    """发布流程到Neo4j图数据库
    
    Returns:
        包含同步结果的详细信息：success, message, synced_at, stats, error等
    """
    record = process_service.get_process(db, process_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )

    try:
        result = sync_process(db, process_id)
        logger.info(f"发布流程成功 process_id={process_id}")
        return result
    except ValueError as e:
        logger.error(f"发布流程失败 process_id={process_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"发布流程失败 process_id={process_id}, error={e}")
        # 返回错误信息而不是抛出异常，让前端能看到详细错误
        from backend.app.services.graph_sync_service import SyncError
        if isinstance(e, SyncError):
            return {
                "success": False,
                "message": e.message,
                "error_type": e.error_type,
                "synced_at": None
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}",
        )
