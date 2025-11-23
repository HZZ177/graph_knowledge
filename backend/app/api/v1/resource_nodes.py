from typing import Optional, List

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
from backend.app.services import resource_node_service

router = APIRouter(prefix="/resource-nodes", tags=["resource-nodes"])


# ---- Data Resources ----


@router.get("/list_data_resources", response_model=PaginatedDataResources)
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
    """分页查询数据资源列表，支持按关键字、类型、系统、流程或步骤过滤。"""
    items, total = resource_node_service.list_data_resources(
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


@router.post("/create_data_resource", response_model=DataResourceOut, status_code=status.HTTP_201_CREATED)
def create_data_resource(
    payload: DataResourceCreate, db: Session = Depends(get_db)
) -> DataResourceOut:
    """创建一条新的数据资源记录，如果已存在则返回 400。"""
    try:
        obj = resource_node_service.create_data_resource(db, payload)
    except ValueError as exc:  # 资源已存在
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return DataResourceOut.from_orm(obj)


@router.get("/get_access_chains", response_model=List[AccessChainItem])
def list_access_chains(
    resource_id: Optional[str] = None,
    impl_id: Optional[str] = None,
    step_id: Optional[str] = None,
    process_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[AccessChainItem]:
    """按资源、实现、步骤或流程维度查询访问链路。

    必须且只能传入一个过滤条件，避免产生歧义。
    """
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

    return resource_node_service.list_access_chains(
        db,
        resource_id=resource_id,
        impl_id=impl_id,
        step_id=step_id,
        process_id=process_id,
    )


@router.get("/get_data_resource/{resource_id}", response_model=DataResourceOut)
def get_data_resource(resource_id: str, db: Session = Depends(get_db)) -> DataResourceOut:
    """根据资源 ID 获取单个数据资源详情。"""
    obj = resource_node_service.get_data_resource(db, resource_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataResourceOut.from_orm(obj)


@router.post("/update_data_resource/{resource_id}", response_model=DataResourceOut)
def update_data_resource(
    resource_id: str, payload: DataResourceUpdate, db: Session = Depends(get_db)
) -> DataResourceOut:
    """更新指定数据资源的属性，如果资源不存在则返回 404。"""
    obj = resource_node_service.update_data_resource(db, resource_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataResourceOut.from_orm(obj)


@router.post("/delete_data_resource/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_resource(resource_id: str, db: Session = Depends(get_db)) -> None:
    """删除指定的数据资源，如果不存在则返回 404。"""
    ok = resource_node_service.delete_data_resource(db, resource_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post(
    "/create_implementation_data_link",
    response_model=ImplementationDataLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_implementation_link(
    payload: ImplementationDataLinkCreate, db: Session = Depends(get_db)
) -> ImplementationDataLinkOut:
    """为实现节点创建访问数据资源的关联关系。"""
    obj = resource_node_service.create_implementation_data_link(
        db,
        impl_id=payload.impl_id,
        resource_id=payload.resource_id,
        access_type=payload.access_type,
        access_pattern=payload.access_pattern,
    )
    return ImplementationDataLinkOut.from_orm(obj)


@router.post(
    "/update_implementation_data_link/{link_id}",
    response_model=ImplementationDataLinkOut,
)
def update_implementation_link(
    link_id: int, payload: ImplementationDataLinkUpdate, db: Session = Depends(get_db)
) -> ImplementationDataLinkOut:
    """更新实现与数据资源关联的访问类型或访问模式。"""
    obj = resource_node_service.update_implementation_data_link(
        db,
        link_id,
        access_type=payload.access_type,
        access_pattern=payload.access_pattern,
    )
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationDataLinkOut.from_orm(obj)


@router.post("/delete_implementation_data_link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_implementation_link(link_id: int, db: Session = Depends(get_db)) -> None:
    """删除实现与数据资源之间的一条关联关系。"""
    ok = resource_node_service.delete_implementation_data_link(db, link_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/get_resource_accessors/{resource_id}", response_model=ResourceWithAccessors)
def get_resource_accessors(
    resource_id: str, db: Session = Depends(get_db)
) -> ResourceWithAccessors:
    """查询某个数据资源的所有访问方（实现/步骤/流程等）。"""
    result = resource_node_service.get_resource_with_accessors(db, resource_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    resource, accessors = result
    return ResourceWithAccessors(
        resource=DataResourceOut.from_orm(resource),
        accessors=accessors,
    )


@router.get("/list_data_resource_businesses", response_model=List[BusinessSimple])
def list_data_resource_businesses(db: Session = Depends(get_db)) -> List[BusinessSimple]:
    """列出所有可用于筛选数据资源的业务流程简要信息。"""
    items = resource_node_service.list_businesses_simple(db)
    return [BusinessSimple(process_id=b.process_id, name=b.name) for b in items]


@router.get("/list_data_resource_steps", response_model=List[StepSimple])
def list_data_resource_steps(
    process_id: Optional[str] = None, db: Session = Depends(get_db)
) -> List[StepSimple]:
    """列出数据资源可关联的步骤列表，可按流程进行过滤。"""
    items = resource_node_service.list_steps_simple(db, process_id=process_id)
    result: List[StepSimple] = []

    # 为了附带流程名称，需要额外查一次 Business（避免复杂 join）
    # 这里复用 list_businesses_simple 的结果构建一个 map
    businesses = {b.process_id: b.name for b in resource_node_service.list_businesses_simple(db)}

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


# ---- Business ----


@router.get("/list_businesses", response_model=PaginatedBusinesses)
def list_businesses(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedBusinesses:
    """分页查询业务节点（Business），支持按关键字过滤。"""
    items, total = resource_node_service.list_businesses(
        db, page=page, page_size=page_size, keyword=q
    )
    return PaginatedBusinesses(
        page=page,
        page_size=page_size,
        total=total,
        items=[BusinessOut.from_orm(item) for item in items],
    )
@router.post("/create_business", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate, db: Session = Depends(get_db)
) -> BusinessOut:
    """创建新的业务节点，如果名称重复则返回 400。"""
    try:
        obj = resource_node_service.create_business(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return BusinessOut.from_orm(obj)
@router.get("/get_business/{process_id}", response_model=BusinessOut)
def get_business(process_id: str, db: Session = Depends(get_db)) -> BusinessOut:
    """根据流程 ID 获取单个业务节点详情。"""
    obj = resource_node_service.get_business(db, process_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return BusinessOut.from_orm(obj)
@router.post("/update_business/{process_id}", response_model=BusinessOut)
def update_business(
    process_id: str, payload: BusinessUpdate, db: Session = Depends(get_db)
) -> BusinessOut:
    """更新业务节点的基础信息，如果不存在则返回 404。"""
    obj = resource_node_service.update_business(db, process_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return BusinessOut.from_orm(obj)
@router.post("/delete_business/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business(process_id: str, db: Session = Depends(get_db)) -> None:
    """删除指定业务节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_business(db, process_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Step-Implementation Links ----


@router.post(
    "/create_step_implementation_link",
    response_model=StepImplementationLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_step_implementation_link(
    payload: StepImplementationLinkCreate, db: Session = Depends(get_db)
) -> StepImplementationLinkOut:
    """为步骤节点和实现节点创建关联关系。"""
    obj = resource_node_service.create_step_implementation_link(
        db, payload.step_id, payload.impl_id
    )
    return StepImplementationLinkOut.from_orm(obj)


@router.post("/delete_step_implementation_link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step_implementation_link(link_id: int, db: Session = Depends(get_db)) -> None:
    """删除步骤与实现之间的一条关联关系。"""
    ok = resource_node_service.delete_step_implementation_link(db, link_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Step ----


@router.get("/list_steps", response_model=PaginatedSteps)
def list_steps(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedSteps:
    """分页查询步骤节点（Step），支持按关键字过滤。"""
    items, total = resource_node_service.list_steps(
        db, page=page, page_size=page_size, keyword=q
    )
    return PaginatedSteps(
        page=page,
        page_size=page_size,
        total=total,
        items=[StepOut.from_orm(item) for item in items],
    )
@router.post("/create_step", response_model=StepOut, status_code=status.HTTP_201_CREATED)
def create_step(payload: StepCreate, db: Session = Depends(get_db)) -> StepOut:
    """创建新的步骤节点，如果名称冲突则返回 400。"""
    try:
        obj = resource_node_service.create_step(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StepOut.from_orm(obj)
@router.get("/get_step/{step_id}", response_model=StepOut)
def get_step(step_id: str, db: Session = Depends(get_db)) -> StepOut:
    """根据步骤 ID 获取单个步骤节点详情。"""
    obj = resource_node_service.get_step(db, step_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return StepOut.from_orm(obj)
@router.post("/update_step/{step_id}", response_model=StepOut)
def update_step(
    step_id: str, payload: StepUpdate, db: Session = Depends(get_db)
) -> StepOut:
    """更新指定步骤节点的属性，如果不存在则返回 404。"""
    obj = resource_node_service.update_step(db, step_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return StepOut.from_orm(obj)


@router.post("/delete_step/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(step_id: str, db: Session = Depends(get_db)) -> None:
    """删除指定步骤节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_step(db, step_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---- Implementation ----


@router.get("/list_implementations", response_model=PaginatedImplementations)
def list_implementations(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedImplementations:
    """分页查询实现节点（Implementation），支持按关键字过滤。"""
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
    "/create_implementation",
    response_model=ImplementationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_implementation(
    payload: ImplementationCreate, db: Session = Depends(get_db)
) -> ImplementationOut:
    """创建新的实现节点，如果名称冲突则返回 400。"""
    try:
        obj = resource_node_service.create_implementation(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ImplementationOut.from_orm(obj)
@router.get("/get_implementation/{impl_id}", response_model=ImplementationOut)
def get_implementation(impl_id: str, db: Session = Depends(get_db)) -> ImplementationOut:
    """根据实现 ID 获取单个实现节点详情。"""
    obj = resource_node_service.get_implementation(db, impl_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationOut.from_orm(obj)
@router.post("/update_implementation/{impl_id}", response_model=ImplementationOut)
def update_implementation(
    impl_id: str, payload: ImplementationUpdate, db: Session = Depends(get_db)
) -> ImplementationOut:
    """更新指定实现节点的属性，如果不存在则返回 404。"""
    obj = resource_node_service.update_implementation(db, impl_id, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ImplementationOut.from_orm(obj)


@router.post("/delete_implementation/{impl_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_implementation(impl_id: str, db: Session = Depends(get_db)) -> None:
    """删除指定实现节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_implementation(db, impl_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
