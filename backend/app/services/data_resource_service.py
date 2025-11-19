from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    ProcessStepEdge,
    DataResource,
    Implementation,
    ImplementationDataResource,
    Step,
    StepImplementation,
)
from backend.app.schemas.data_resources import (
    DataResourceCreate,
    DataResourceOut,
    DataResourceUpdate,
    ResourceAccessor,
    AccessChainItem,
)


def list_data_resources(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    type_: Optional[str] = None,
    system: Optional[str] = None,
    process_id: Optional[str] = None,
    step_id: Optional[str] = None,
) -> Tuple[List[DataResource], int]:
    query = db.query(DataResource)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                DataResource.name.ilike(pattern),
                DataResource.resource_id.ilike(pattern),
                DataResource.description.ilike(pattern),
            )
        )

    if type_:
        query = query.filter(DataResource.type == type_)

    if system:
        query = query.filter(DataResource.system == system)

    # 通过流程过滤：Business → ProcessStepEdge → StepImplementation → ImplementationDataResource → DataResource
    if process_id:
        query = (
            query.join(ImplementationDataResource, DataResource.implementations)
            .join(Implementation, ImplementationDataResource.impl_id == Implementation.impl_id)
            .join(StepImplementation, StepImplementation.impl_id == Implementation.impl_id)
            .join(
                ProcessStepEdge,
                or_(
                    ProcessStepEdge.from_step_id == StepImplementation.step_id,
                    ProcessStepEdge.to_step_id == StepImplementation.step_id,
                ),
            )
            .filter(ProcessStepEdge.process_id == process_id)
        ).distinct()

    # 通过步骤过滤
    if step_id:
        query = (
            query.join(ImplementationDataResource, DataResource.implementations)
            .join(Implementation, ImplementationDataResource.impl_id == Implementation.impl_id)
            .join(StepImplementation, StepImplementation.impl_id == Implementation.impl_id)
            .filter(StepImplementation.step_id == step_id)
        ).distinct()

    total = query.count()

    items = (
        query.order_by(DataResource.resource_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return items, total


def get_data_resource(db: Session, resource_id: str) -> Optional[DataResource]:
    return (
        db.query(DataResource)
        .filter(DataResource.resource_id == resource_id)
        .first()
    )


def create_data_resource(db: Session, data: DataResourceCreate) -> DataResource:
    existing = get_data_resource(db, data.resource_id)
    if existing:
        raise ValueError(f"DataResource {data.resource_id} already exists")

    obj = DataResource(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_data_resource(
    db: Session, resource_id: str, data: DataResourceUpdate
) -> Optional[DataResource]:
    obj = get_data_resource(db, resource_id)
    if not obj:
        return None

    for field, value in data.dict(exclude_unset=True).items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return obj


def delete_data_resource(db: Session, resource_id: str) -> bool:
    obj = get_data_resource(db, resource_id)
    if not obj:
        return False

    # 先删除关联关系
    db.query(ImplementationDataResource).filter(
        ImplementationDataResource.resource_id == resource_id
    ).delete(synchronize_session=False)

    db.delete(obj)
    db.commit()
    return True


def get_resource_with_accessors(
    db: Session, resource_id: str
) -> Optional[Tuple[DataResource, List[ResourceAccessor]]]:
    resource = get_data_resource(db, resource_id)
    if not resource:
        return None

    rows = (
        db.query(
            ImplementationDataResource,
            Implementation,
            Step,
            Business,
        )
        .join(Implementation, ImplementationDataResource.impl_id == Implementation.impl_id)
        .outerjoin(
            StepImplementation,
            StepImplementation.impl_id == Implementation.impl_id,
        )
        .outerjoin(Step, Step.step_id == StepImplementation.step_id)
        .outerjoin(
            ProcessStepEdge,
            or_(
                ProcessStepEdge.from_step_id == Step.step_id,
                ProcessStepEdge.to_step_id == Step.step_id,
            ),
        )
        .outerjoin(Business, Business.process_id == ProcessStepEdge.process_id)
        .filter(ImplementationDataResource.resource_id == resource_id)
        .all()
    )

    accessors: List[ResourceAccessor] = []
    for link, impl, step, biz in rows:
        accessors.append(
            ResourceAccessor(
                impl_id=impl.impl_id,
                impl_name=impl.name,
                impl_system=impl.system,
                access_type=link.access_type,
                access_pattern=link.access_pattern,
                step_id=step.step_id if step else None,
                step_name=step.name if step else None,
                process_id=biz.process_id if biz else None,
                process_name=biz.name if biz else None,
            )
        )

    return resource, accessors


def list_access_chains(
    db: Session,
    *,
    resource_id: Optional[str] = None,
    impl_id: Optional[str] = None,
    step_id: Optional[str] = None,
    process_id: Optional[str] = None,
) -> List[AccessChainItem]:
    """Generic access relationship chains filtered by different node ids.

    Each returned item represents one logical chain:
    Business (process) -> Step -> Implementation -> DataResource.
    Some parts may be missing (e.g. no business/step binding).
    """

    query = (
        db.query(
            DataResource,
            ImplementationDataResource,
            Implementation,
            Step,
            Business,
        )
        .join(
            ImplementationDataResource,
            ImplementationDataResource.resource_id == DataResource.resource_id,
        )
        .join(Implementation, ImplementationDataResource.impl_id == Implementation.impl_id)
        .outerjoin(
            StepImplementation,
            StepImplementation.impl_id == Implementation.impl_id,
        )
        .outerjoin(Step, Step.step_id == StepImplementation.step_id)
        .outerjoin(
            ProcessStepEdge,
            or_(
                ProcessStepEdge.from_step_id == Step.step_id,
                ProcessStepEdge.to_step_id == Step.step_id,
            ),
        )
        .outerjoin(Business, Business.process_id == ProcessStepEdge.process_id)
    )

    if resource_id:
        query = query.filter(DataResource.resource_id == resource_id)
    if impl_id:
        query = query.filter(Implementation.impl_id == impl_id)
    if step_id:
        query = query.filter(Step.step_id == step_id)
    if process_id:
        query = query.filter(Business.process_id == process_id)

    rows = query.all()

    chains: List[AccessChainItem] = []
    for res, link, impl, step, biz in rows:
        chains.append(
            AccessChainItem(
                resource_id=res.resource_id,
                resource_name=res.name,
                impl_id=impl.impl_id if impl else None,
                impl_name=impl.name if impl else None,
                impl_system=impl.system if impl else None,
                access_type=link.access_type if link else None,
                access_pattern=link.access_pattern if link else None,
                step_id=step.step_id if step else None,
                step_name=step.name if step else None,
                process_id=biz.process_id if biz else None,
                process_name=biz.name if biz else None,
            )
        )

    return chains


def list_businesses_simple(db: Session) -> List[Business]:
    return db.query(Business).order_by(Business.process_id).all()


def list_steps_simple(db: Session, process_id: Optional[str] = None) -> List[Step]:
    query = db.query(Step)
    if process_id:
        query = (
            query.join(
                ProcessStepEdge,
                or_(
                    ProcessStepEdge.from_step_id == Step.step_id,
                    ProcessStepEdge.to_step_id == Step.step_id,
                ),
            )
            .filter(ProcessStepEdge.process_id == process_id)
            .distinct()
        )
    return query.order_by(Step.step_id).all()


# ---- Implementation-DataResource Links ----


def create_implementation_data_link(
    db: Session,
    *,
    impl_id: str,
    resource_id: str,
    access_type: Optional[str] = None,
    access_pattern: Optional[str] = None,
) -> ImplementationDataResource:
    """创建实现与数据资源之间的访问关系。

    如果同一 impl_id + resource_id 已存在，则更新其 access_type / access_pattern 并返回。
    """

    existing = (
        db.query(ImplementationDataResource)
        .filter(
            ImplementationDataResource.impl_id == impl_id,
            ImplementationDataResource.resource_id == resource_id,
        )
        .first()
    )
    if existing:
        if access_type is not None:
            existing.access_type = access_type
        if access_pattern is not None:
            existing.access_pattern = access_pattern
        db.commit()
        db.refresh(existing)
        return existing

    obj = ImplementationDataResource(
        impl_id=impl_id,
        resource_id=resource_id,
        access_type=access_type,
        access_pattern=access_pattern,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_implementation_data_link(
    db: Session,
    link_id: int,
    *,
    access_type: Optional[str] = None,
    access_pattern: Optional[str] = None,
) -> Optional[ImplementationDataResource]:
    obj = (
        db.query(ImplementationDataResource)
        .filter(ImplementationDataResource.id == link_id)
        .first()
    )
    if not obj:
        return None

    if access_type is not None:
        obj.access_type = access_type
    if access_pattern is not None:
        obj.access_pattern = access_pattern

    db.commit()
    db.refresh(obj)
    return obj


def delete_implementation_data_link(db: Session, link_id: int) -> bool:
    obj = (
        db.query(ImplementationDataResource)
        .filter(ImplementationDataResource.id == link_id)
        .first()
    )
    if not obj:
        return False

    db.delete(obj)
    db.commit()
    return True
