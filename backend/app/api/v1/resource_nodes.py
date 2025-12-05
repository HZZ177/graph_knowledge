from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.resource_nodes import (
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
    ImplementationCreate,
    ImplementationOut,
    ImplementationUpdate,
    ImplementationBatchCreate,
    ImplementationBatchCreateResult,
    PaginatedBusinesses,
    PaginatedImplementations,
    PaginatedSteps,
    StepCreate,
    StepOut,
    StepUpdate,
    StepImplementationLinkCreate,
    StepImplementationLinkOut,
    BusinessIdRequest,
    BusinessUpdatePayload,
    StepIdRequest,
    StepUpdatePayload,
    ImplementationIdRequest,
    ImplementationUpdatePayload,
    StepImplementationLinkIdRequest,
    BusinessGroupStats,
    StepGroupStats,
    ImplementationGroupStats,
    DataResourceGroupStats,
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
    DataResourceIdRequest,
    DataResourceUpdatePayload,
    ImplementationDataLinkIdRequest,
    ImplementationDataLinkUpdatePayload,
    DataResourceBatchCreate,
    DataResourceBatchCreateResult,
)
from backend.app.services import resource_node_service
from backend.app.core.utils import success_response, error_response

router = APIRouter(prefix="/resource-nodes", tags=["resource-nodes"])


# ---- Data Resources ----


@router.get("/data_resource_group_stats", response_model=DataResourceGroupStats)
def get_data_resource_group_stats(
    db: Session = Depends(get_db),
) -> DataResourceGroupStats:
    """获取数据资源按系统和类型分组的统计信息。"""
    stats = resource_node_service.get_data_resource_group_stats(db)
    return success_response(data=stats)


@router.get("/list_data_resources", response_model=PaginatedDataResources)
def list_data_resources(
    page: int = Query(1),
    page_size: int = Query(20),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),  # noqa: A002 - 与查询参数同名
    system: Optional[str] = Query(None),
    process_id: Optional[str] = Query(None),
    step_id: Optional[str] = Query(None),
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
    result = PaginatedDataResources(
        page=page,
        page_size=page_size,
        total=total,
        items=[DataResourceOut.from_orm(item) for item in items],
    )
    return success_response(data=result)


@router.post("/create_data_resource", response_model=DataResourceOut)
def create_data_resource(
    payload: DataResourceCreate = Body(...),
    db: Session = Depends(get_db),
) -> DataResourceOut:
    """创建一条新的数据资源记录，如果已存在则返回 400。"""
    try:
        obj = resource_node_service.create_data_resource(db, payload)
    except ValueError as exc:  # 资源已存在
        return error_response(message=str(exc))
    return success_response(data=DataResourceOut.from_orm(obj), message="创建数据资源成功")


@router.post("/batch_create_data_resources", response_model=DataResourceBatchCreateResult)
def batch_create_data_resources(
    payload: DataResourceBatchCreate = Body(...),
    db: Session = Depends(get_db),
) -> DataResourceBatchCreateResult:
    """批量创建数据资源，已存在的会跳过。"""
    result = resource_node_service.batch_create_data_resources(db, payload.items)
    data = DataResourceBatchCreateResult(
        success_count=result["success_count"],
        skip_count=result["skip_count"],
        failed_count=result["failed_count"],
        created_items=[DataResourceOut.from_orm(obj) for obj in result["created_items"]],
        skipped_names=result["skipped_names"],
        failed_items=result["failed_items"],
    )
    return success_response(
        data=data,
        message=f"批量导入完成：成功 {result['success_count']} 条，跳过 {result['skip_count']} 条"
    )


@router.get("/get_access_chains", response_model=List[AccessChainItem])
def list_access_chains(
    resource_id: Optional[str] = Query(None),
    impl_id: Optional[str] = Query(None),
    step_id: Optional[str] = Query(None),
    process_id: Optional[str] = Query(None),
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
        return error_response(
            message="Exactly one of resource_id, impl_id, step_id, process_id must be provided",
        )

    chains = resource_node_service.list_access_chains(
        db,
        resource_id=resource_id,
        impl_id=impl_id,
        step_id=step_id,
        process_id=process_id,
    )
    return success_response(data=chains)


@router.get("/get_data_resource", response_model=DataResourceOut)
def get_data_resource(
    resource_id: str = Query(...),
    db: Session = Depends(get_db),
) -> DataResourceOut:
    """根据资源 ID 获取单个数据资源详情。"""
    obj = resource_node_service.get_data_resource(db, resource_id)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=DataResourceOut.from_orm(obj))


@router.post("/update_data_resource", response_model=DataResourceOut)
def update_data_resource(
    payload: DataResourceUpdatePayload = Body(...),
    db: Session = Depends(get_db),
) -> DataResourceOut:
    """更新指定数据资源的属性，如果资源不存在则返回 404。"""
    obj = resource_node_service.update_data_resource(db, payload.resource_id, payload)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=DataResourceOut.from_orm(obj), message="更新数据资源成功")


@router.post("/delete_data_resource")
def delete_data_resource(
    payload: DataResourceIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除指定的数据资源，如果不存在则返回 404。"""
    ok = resource_node_service.delete_data_resource(db, payload.resource_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除数据资源成功")


@router.post("/create_implementation_data_link",response_model=ImplementationDataLinkOut)
def create_implementation_link(
    payload: ImplementationDataLinkCreate = Body(...),
    db: Session = Depends(get_db),
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


@router.post("/update_implementation_data_link",response_model=ImplementationDataLinkOut)
def update_implementation_link(
    payload: ImplementationDataLinkUpdatePayload = Body(...),
    db: Session = Depends(get_db),
) -> ImplementationDataLinkOut:
    """更新实现与数据资源关联的访问类型或访问模式。"""
    obj = resource_node_service.update_implementation_data_link(
        db,
        payload.link_id,
        access_type=payload.access_type,
        access_pattern=payload.access_pattern,
    )
    if not obj:
        return error_response(message="Not found")
    return success_response(
        data=ImplementationDataLinkOut.from_orm(obj),
        message="更新实现数据资源关联成功",
    )


@router.post("/delete_implementation_data_link")
def delete_implementation_link(
    payload: ImplementationDataLinkIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除实现与数据资源之间的一条关联关系。"""
    ok = resource_node_service.delete_implementation_data_link(db, payload.link_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除实现数据资源关联成功")


@router.get("/get_resource_accessors", response_model=ResourceWithAccessors)
def get_resource_accessors(
    resource_id: str = Query(...),
    db: Session = Depends(get_db),
) -> ResourceWithAccessors:
    """查询某个数据资源的所有访问方（实现/步骤/流程等）。"""
    result = resource_node_service.get_resource_with_accessors(db, resource_id)
    if not result:
        return error_response(message="Not found")

    resource, accessors = result
    data = ResourceWithAccessors(
        resource=DataResourceOut.from_orm(resource),
        accessors=accessors,
    )
    return success_response(data=data)


@router.get("/list_data_resource_businesses", response_model=List[BusinessSimple])
def list_data_resource_businesses(db: Session = Depends(get_db)) -> List[BusinessSimple]:
    """列出所有可用于筛选数据资源的业务流程简要信息。"""
    items = resource_node_service.list_businesses_simple(db)
    data = [BusinessSimple(process_id=b.process_id, name=b.name) for b in items]
    return success_response(data=data)


@router.get("/list_data_resource_steps", response_model=List[StepSimple])
def list_data_resource_steps(
    process_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
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

    return success_response(data=result)


# ---- Business ----


@router.get("/business_group_stats", response_model=BusinessGroupStats)
def get_business_group_stats(
    db: Session = Depends(get_db),
) -> BusinessGroupStats:
    """获取业务流程按渠道分组的统计信息。"""
    stats = resource_node_service.get_business_group_stats(db)
    return success_response(data=stats)


@router.get("/list_businesses", response_model=PaginatedBusinesses)
def list_businesses(
    page: int = Query(1),
    page_size: int = Query(20),
    q: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedBusinesses:
    """分页查询业务节点（Business），支持按关键字和渠道过滤。"""
    items, total = resource_node_service.list_businesses(
        db, page=page, page_size=page_size, keyword=q, channel=channel
    )
    result = PaginatedBusinesses(
        page=page,
        page_size=page_size,
        total=total,
        items=[BusinessOut.from_orm(item) for item in items],
    )
    return success_response(data=result)


@router.post("/create_business", response_model=BusinessOut)
def create_business(
    payload: BusinessCreate = Body(...),
    db: Session = Depends(get_db),
) -> BusinessOut:
    """创建新的业务节点，如果名称重复则返回 400。"""
    try:
        obj = resource_node_service.create_business(db, payload)
    except ValueError as exc:
        return error_response(message=str(exc))
    return success_response(data=BusinessOut.from_orm(obj), message="创建业务节点成功")


@router.get("/get_business", response_model=BusinessOut)
def get_business(
    process_id: str = Query(...),
    db: Session = Depends(get_db),
) -> BusinessOut:
    """根据流程 ID 获取单个业务节点详情。"""
    obj = resource_node_service.get_business(db, process_id)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=BusinessOut.from_orm(obj))


@router.post("/update_business", response_model=BusinessOut)
def update_business(
    payload: BusinessUpdatePayload = Body(...),
    db: Session = Depends(get_db),
) -> BusinessOut:
    """更新业务节点的基础信息，如果不存在则返回 404。"""
    obj = resource_node_service.update_business(db, payload.process_id, payload)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=BusinessOut.from_orm(obj), message="更新业务节点成功")


@router.post("/delete_business")
def delete_business(
    payload: BusinessIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除指定业务节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_business(db, payload.process_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除业务节点成功")


# ---- Step-Implementation Links ----


@router.post("/create_step_implementation_link",response_model=StepImplementationLinkOut)
def create_step_implementation_link(
    payload: StepImplementationLinkCreate = Body(...),
    db: Session = Depends(get_db),
) -> StepImplementationLinkOut:
    """为步骤节点和实现节点创建关联关系。"""
    obj = resource_node_service.create_step_implementation_link(
        db, payload.step_id, payload.impl_id
    )
    return success_response(data=StepImplementationLinkOut.from_orm(obj), message="创建步骤实现关联成功")


@router.post("/delete_step_implementation_link")
def delete_step_implementation_link(
    payload: StepImplementationLinkIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除步骤与实现之间的一条关联关系。"""
    ok = resource_node_service.delete_step_implementation_link(db, payload.link_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除步骤实现关联成功")


# ---- Step ----


@router.get("/step_group_stats", response_model=StepGroupStats)
def get_step_group_stats(
    db: Session = Depends(get_db),
) -> StepGroupStats:
    """获取步骤按类型分组的统计信息。"""
    stats = resource_node_service.get_step_group_stats(db)
    return success_response(data=stats)


@router.get("/list_steps", response_model=PaginatedSteps)
def list_steps(
    page: int = Query(1),
    page_size: int = Query(20),
    q: Optional[str] = Query(None),
    step_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedSteps:
    """分页查询步骤节点（Step），支持按关键字和步骤类型过滤。"""
    items, total = resource_node_service.list_steps(
        db, page=page, page_size=page_size, keyword=q, step_type=step_type
    )
    result = PaginatedSteps(
        page=page,
        page_size=page_size,
        total=total,
        items=[StepOut.from_orm(item) for item in items],
    )
    return success_response(data=result)


@router.post("/create_step", response_model=StepOut)
def create_step(
    payload: StepCreate = Body(...),
    db: Session = Depends(get_db),
) -> StepOut:
    """创建新的步骤节点，如果名称冲突则返回 400。"""
    try:
        obj = resource_node_service.create_step(db, payload)
    except ValueError as exc:
        return error_response(message=str(exc))
    return success_response(data=StepOut.from_orm(obj), message="创建步骤成功")


@router.get("/get_step", response_model=StepOut)
def get_step(
    step_id: str = Query(...),
    db: Session = Depends(get_db),
) -> StepOut:
    """根据步骤 ID 获取单个步骤节点详情。"""
    obj = resource_node_service.get_step(db, step_id)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=StepOut.from_orm(obj))


@router.post("/update_step", response_model=StepOut)
def update_step(
    payload: StepUpdatePayload = Body(...),
    db: Session = Depends(get_db),
) -> StepOut:
    """更新指定步骤节点的属性，如果不存在则返回 404。"""
    obj = resource_node_service.update_step(db, payload.step_id, payload)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=StepOut.from_orm(obj), message="更新步骤成功")


@router.post("/delete_step")
def delete_step(
    payload: StepIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除指定步骤节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_step(db, payload.step_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除步骤成功")


# ---- Implementation ----


@router.get("/implementation_group_stats", response_model=ImplementationGroupStats)
def get_implementation_group_stats(
    db: Session = Depends(get_db),
) -> ImplementationGroupStats:
    """获取实现按系统和类型分组的统计信息。"""
    stats = resource_node_service.get_implementation_group_stats(db)
    return success_response(data=stats)


@router.get("/list_implementations", response_model=PaginatedImplementations)
def list_implementations(
    page: int = Query(1),
    page_size: int = Query(20),
    q: Optional[str] = Query(None),
    system: Optional[str] = Query(None),
    type: Optional[str] = Query(None),  # noqa: A002
    db: Session = Depends(get_db),
) -> PaginatedImplementations:
    """分页查询实现节点（Implementation），支持按关键字、系统和类型过滤。"""
    items, total = resource_node_service.list_implementations(
        db, page=page, page_size=page_size, keyword=q, system=system, type_=type
    )
    result = PaginatedImplementations(
        page=page,
        page_size=page_size,
        total=total,
        items=[ImplementationOut.from_orm(item) for item in items],
    )
    return success_response(data=result)


@router.post("/create_implementation",response_model=ImplementationOut)
def create_implementation(
    payload: ImplementationCreate = Body(...),
    db: Session = Depends(get_db),
) -> ImplementationOut:
    """创建新的实现节点，如果名称冲突则返回 400。"""
    try:
        obj = resource_node_service.create_implementation(db, payload)
    except ValueError as exc:
        return error_response(message=str(exc))
    return success_response(data=ImplementationOut.from_orm(obj), message="创建实现成功")


@router.post("/batch_create_implementations", response_model=ImplementationBatchCreateResult)
def batch_create_implementations(
    payload: ImplementationBatchCreate = Body(...),
    db: Session = Depends(get_db),
) -> ImplementationBatchCreateResult:
    """批量创建实现单元，已存在的会跳过。"""
    result = resource_node_service.batch_create_implementations(db, payload.items)
    data = ImplementationBatchCreateResult(
        success_count=result["success_count"],
        skip_count=result["skip_count"],
        failed_count=result["failed_count"],
        created_items=[ImplementationOut.from_orm(obj) for obj in result["created_items"]],
        skipped_names=result["skipped_names"],
        failed_items=result["failed_items"],
    )
    return success_response(
        data=data,
        message=f"批量导入完成：成功 {result['success_count']} 条，跳过 {result['skip_count']} 条"
    )


@router.get("/get_implementation", response_model=ImplementationOut)
def get_implementation(
    impl_id: str = Query(...),
    db: Session = Depends(get_db),
) -> ImplementationOut:
    """根据实现 ID 获取单个实现节点详情。"""
    obj = resource_node_service.get_implementation(db, impl_id)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=ImplementationOut.from_orm(obj))


@router.post("/update_implementation", response_model=ImplementationOut)
def update_implementation(
    payload: ImplementationUpdatePayload = Body(...),
    db: Session = Depends(get_db),
) -> ImplementationOut:
    """更新指定实现节点的属性，如果不存在则返回 404。"""
    obj = resource_node_service.update_implementation(db, payload.impl_id, payload)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=ImplementationOut.from_orm(obj), message="更新实现成功")


@router.post("/delete_implementation")
def delete_implementation(
    payload: ImplementationIdRequest = Body(...),
    db: Session = Depends(get_db),
) -> None:
    """删除指定实现节点，如果不存在则返回 404。"""
    ok = resource_node_service.delete_implementation(db, payload.impl_id)
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除实现成功")
