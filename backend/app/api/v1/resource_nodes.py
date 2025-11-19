from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.resource_nodes import (
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
    ImplementationCreate,
    ImplementationOut,
    ImplementationUpdate,
    PaginatedBusinesses,
    PaginatedImplementations,
    PaginatedSteps,
    StepCreate,
    StepOut,
    StepUpdate,
    StepImplementationLinkCreate,
    StepImplementationLinkOut,
)
from backend.app.services import resource_node_service

router = APIRouter(prefix="/resource-nodes", tags=["resource-nodes"])


# ---- Business ----


@router.get("/businesses", response_model=PaginatedBusinesses)
def list_businesses(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedBusinesses:
    items, total = resource_node_service.list_businesses(
        db, page=page, page_size=page_size, keyword=q
    )
    return PaginatedBusinesses(
        page=page,
        page_size=page_size,
        total=total,
        items=[BusinessOut.from_orm(item) for item in items],
    )


@router.post("/businesses", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate, db: Session = Depends(get_db)
) -> BusinessOut:
    try:
        obj = resource_node_service.create_business(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return BusinessOut.from_orm(obj)


@router.get("/businesses/{process_id}", response_model=BusinessOut)
def get_business(process_id: str, db: Session = Depends(get_db)) -> BusinessOut:
    obj = resource_node_service.get_business(db, process_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return BusinessOut.from_orm(obj)


@router.put("/businesses/{process_id}", response_model=BusinessOut)
def update_business(
    process_id: str, payload: BusinessUpdate, db: Session = Depends(get_db)
) -> BusinessOut:
    obj = resource_node_service.update_business(db, process_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return BusinessOut.from_orm(obj)


@router.delete("/businesses/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business(process_id: str, db: Session = Depends(get_db)) -> None:
    ok = resource_node_service.delete_business(db, process_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Step-Implementation Links ----


@router.post(
    "/step-implementations",
    response_model=StepImplementationLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_step_implementation_link(
    payload: StepImplementationLinkCreate, db: Session = Depends(get_db)
) -> StepImplementationLinkOut:
    obj = resource_node_service.create_step_implementation_link(
        db, payload.step_id, payload.impl_id
    )
    return StepImplementationLinkOut.from_orm(obj)


@router.delete("/step-implementations/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step_implementation_link(link_id: int, db: Session = Depends(get_db)) -> None:
    ok = resource_node_service.delete_step_implementation_link(db, link_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Step ----


@router.get("/steps", response_model=PaginatedSteps)
def list_steps(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedSteps:
    items, total = resource_node_service.list_steps(
        db, page=page, page_size=page_size, keyword=q
    )
    return PaginatedSteps(
        page=page,
        page_size=page_size,
        total=total,
        items=[StepOut.from_orm(item) for item in items],
    )


@router.post("/steps", response_model=StepOut, status_code=status.HTTP_201_CREATED)
def create_step(payload: StepCreate, db: Session = Depends(get_db)) -> StepOut:
    try:
        obj = resource_node_service.create_step(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StepOut.from_orm(obj)


@router.get("/steps/{step_id}", response_model=StepOut)
def get_step(step_id: str, db: Session = Depends(get_db)) -> StepOut:
    obj = resource_node_service.get_step(db, step_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return StepOut.from_orm(obj)


@router.put("/steps/{step_id}", response_model=StepOut)
def update_step(
    step_id: str, payload: StepUpdate, db: Session = Depends(get_db)
) -> StepOut:
    obj = resource_node_service.update_step(db, step_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return StepOut.from_orm(obj)


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(step_id: str, db: Session = Depends(get_db)) -> None:
    ok = resource_node_service.delete_step(db, step_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Implementation ----


@router.get("/implementations", response_model=PaginatedImplementations)
def list_implementations(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedImplementations:
    items, total = resource_node_service.list_implementations(
        db, page=page, page_size=page_size, keyword=q
    )
    return PaginatedImplementations(
        page=page,
        page_size=page_size,
        total=total,
        items=[ImplementationOut.from_orm(item) for item in items],
    )


@router.post(
    "/implementations",
    response_model=ImplementationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_implementation(
    payload: ImplementationCreate, db: Session = Depends(get_db)
) -> ImplementationOut:
    try:
        obj = resource_node_service.create_implementation(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ImplementationOut.from_orm(obj)


@router.get("/implementations/{impl_id}", response_model=ImplementationOut)
def get_implementation(impl_id: str, db: Session = Depends(get_db)) -> ImplementationOut:
    obj = resource_node_service.get_implementation(db, impl_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationOut.from_orm(obj)


@router.put("/implementations/{impl_id}", response_model=ImplementationOut)
def update_implementation(
    impl_id: str, payload: ImplementationUpdate, db: Session = Depends(get_db)
) -> ImplementationOut:
    obj = resource_node_service.update_implementation(db, impl_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationOut.from_orm(obj)


@router.delete("/implementations/{impl_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_implementation(impl_id: str, db: Session = Depends(get_db)) -> None:
    ok = resource_node_service.delete_implementation(db, impl_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
