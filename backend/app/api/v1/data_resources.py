from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.data_resources import (
    BusinessSimple,
    DataResourceCreate,
    DataResourceOut,
    DataResourceUpdate,
    PaginatedDataResources,
    ResourceWithAccessors,
    StepSimple,
    AccessChainItem,
    ImplementationDataLinkCreate,
    ImplementationDataLinkUpdate,
    ImplementationDataLinkOut,
)
from backend.app.services import data_resource_service

router = APIRouter(prefix="/data-resources", tags=["data-resources"])


@router.get("", response_model=PaginatedDataResources)
def list_data_resources(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    type: Optional[str] = None,  # noqa: A002 - 与查询参数同名
    system: Optional[str] = None,
    process_id: Optional[str] = None,
    step_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedDataResources:
    items, total = data_resource_service.list_data_resources(
        db,
        page=page,
        page_size=page_size,
        keyword=q,
        type_=type,
        system=system,
        process_id=process_id,
        step_id=step_id,
    )
    return PaginatedDataResources(
        page=page,
        page_size=page_size,
        total=total,
        items=[DataResourceOut.from_orm(item) for item in items],
    )


@router.post("", response_model=DataResourceOut, status_code=status.HTTP_201_CREATED)
def create_data_resource(
    payload: DataResourceCreate, db: Session = Depends(get_db)
) -> DataResourceOut:
    try:
        obj = data_resource_service.create_data_resource(db, payload)
    except ValueError as exc:  # 资源已存在
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return DataResourceOut.from_orm(obj)


@router.get("/access-chains", response_model=List[AccessChainItem])
def list_access_chains(
    resource_id: Optional[str] = None,
    impl_id: Optional[str] = None,
    step_id: Optional[str] = None,
    process_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[AccessChainItem]:
    # 必须且只能传入一个过滤条件，避免产生歧义
    filters = [
        bool(resource_id),
        bool(impl_id),
        bool(step_id),
        bool(process_id),
    ]
    if sum(filters) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of resource_id, impl_id, step_id, process_id must be provided",
        )

    return data_resource_service.list_access_chains(
        db,
        resource_id=resource_id,
        impl_id=impl_id,
        step_id=step_id,
        process_id=process_id,
    )


@router.get("/{resource_id}", response_model=DataResourceOut)
def get_data_resource(resource_id: str, db: Session = Depends(get_db)) -> DataResourceOut:
    obj = data_resource_service.get_data_resource(db, resource_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataResourceOut.from_orm(obj)


@router.put("/{resource_id}", response_model=DataResourceOut)
def update_data_resource(
    resource_id: str, payload: DataResourceUpdate, db: Session = Depends(get_db)
) -> DataResourceOut:
    obj = data_resource_service.update_data_resource(db, resource_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataResourceOut.from_orm(obj)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_resource(resource_id: str, db: Session = Depends(get_db)) -> None:
    ok = data_resource_service.delete_data_resource(db, resource_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post(
    "/implementation-links",
    response_model=ImplementationDataLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_implementation_link(
    payload: ImplementationDataLinkCreate, db: Session = Depends(get_db)
) -> ImplementationDataLinkOut:
    obj = data_resource_service.create_implementation_data_link(
        db,
        impl_id=payload.impl_id,
        resource_id=payload.resource_id,
        access_type=payload.access_type,
        access_pattern=payload.access_pattern,
    )
    return ImplementationDataLinkOut.from_orm(obj)


@router.put(
    "/implementation-links/{link_id}",
    response_model=ImplementationDataLinkOut,
)
def update_implementation_link(
    link_id: int, payload: ImplementationDataLinkUpdate, db: Session = Depends(get_db)
) -> ImplementationDataLinkOut:
    obj = data_resource_service.update_implementation_data_link(
        db,
        link_id,
        access_type=payload.access_type,
        access_pattern=payload.access_pattern,
    )
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationDataLinkOut.from_orm(obj)


@router.delete("/implementation-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_implementation_link(link_id: int, db: Session = Depends(get_db)) -> None:
    ok = data_resource_service.delete_implementation_data_link(db, link_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/{resource_id}/accessors", response_model=ResourceWithAccessors)
def get_resource_accessors(
    resource_id: str, db: Session = Depends(get_db)
) -> ResourceWithAccessors:
    result = data_resource_service.get_resource_with_accessors(db, resource_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    resource, accessors = result
    return ResourceWithAccessors(
        resource=DataResourceOut.from_orm(resource),
        accessors=accessors,
    )


@router.get("/meta/businesses", response_model=List[BusinessSimple])
def list_businesses(db: Session = Depends(get_db)) -> List[BusinessSimple]:
    items = data_resource_service.list_businesses_simple(db)
    return [BusinessSimple(process_id=b.process_id, name=b.name) for b in items]


@router.get("/meta/steps", response_model=List[StepSimple])
def list_steps(
    process_id: Optional[str] = None, db: Session = Depends(get_db)
) -> List[StepSimple]:
    items = data_resource_service.list_steps_simple(db, process_id=process_id)
    result: List[StepSimple] = []

    # 为了附带流程名称，需要额外查一次 Business（避免复杂 join）
    # 这里复用 list_businesses_simple 的结果构建一个 map
    businesses = {b.process_id: b.name for b in data_resource_service.list_businesses_simple(db)}

    for s in items:
        result.append(
            StepSimple(
                step_id=s.step_id,
                name=s.name,
                process_id=None,
                process_name=None,
            )
        )

    return result
