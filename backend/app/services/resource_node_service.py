from typing import List, Optional, Tuple

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    ProcessStepEdge,
    Implementation,
    ImplementationDataResource,
    Step,
    StepImplementation,
    DataResource,
)
from backend.app.schemas.resource_nodes import (
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
    ImplementationCreate,
    ImplementationOut,
    ImplementationUpdate,
    StepCreate,
    StepOut,
    StepUpdate,
)
from backend.app.schemas.data_resources import (
    DataResourceCreate,
    DataResourceOut,
    DataResourceUpdate,
    ResourceAccessor,
    AccessChainItem,
)
from backend.app.core.logger import logger


# ---- Business ----


def list_businesses(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    channel: Optional[str] = None,
) -> Tuple[List[Business], int]:
    query = db.query(Business)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Business.name.ilike(pattern),
                Business.process_id.ilike(pattern),
                Business.description.ilike(pattern),
            )
        )

    # 按渠道过滤
    if channel is not None:
        if channel == "":
            # 空字符串表示"其他"（未分类）
            query = query.filter(or_(Business.channel == None, Business.channel == ""))
        else:
            query = query.filter(Business.channel == channel)

    total = query.count()
    items = (
        query.order_by(Business.process_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_business_group_stats(db: Session) -> dict:
    """获取业务流程按渠道分组的统计信息"""
    # 按 channel 分组统计
    rows = (
        db.query(Business.channel, func.count(Business.process_id))
        .group_by(Business.channel)
        .all()
    )

    by_channel = []
    total = 0
    for channel, count in rows:
        by_channel.append({
            "value": channel if channel else None,
            "count": count,
        })
        total += count

    return {
        "by_channel": by_channel,
        "total": total,
    }


def get_business(db: Session, process_id: str) -> Optional[Business]:
    return db.query(Business).filter(Business.process_id == process_id).first()


def create_business(db: Session, data: BusinessCreate) -> Business:
    obj = Business(
        name=data.name,
        channel=data.channel,
        description=data.description,
        entrypoints=data.entrypoints,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_business(
    db: Session, process_id: str, data: BusinessUpdate
) -> Optional[Business]:
    obj = get_business(db, process_id)
    if not obj:
        return None

    for field, value in data.dict(exclude_unset=True).items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return obj


def delete_business(db: Session, process_id: str) -> bool:
    obj = get_business(db, process_id)
    if not obj:
        return False

    # 删除与业务相关的流程边记录
    db.query(ProcessStepEdge).filter(
        ProcessStepEdge.process_id == process_id
    ).delete(synchronize_session=False)

    db.delete(obj)
    db.commit()
    return True


# ---- DataResource ----


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
    """分页查询数据资源列表，支持按关键字、类型、系统、流程或步骤过滤。"""

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


def get_data_resource_group_stats(db: Session) -> dict:
    """获取数据资源按系统和类型分组的统计信息"""
    # 按 system 分组
    system_rows = (
        db.query(DataResource.system, func.count(DataResource.resource_id))
        .group_by(DataResource.system)
        .all()
    )

    by_system = []
    total = 0
    for system, count in system_rows:
        by_system.append({
            "value": system if system else None,
            "count": count,
        })
        total += count

    # 按 type 分组
    type_rows = (
        db.query(DataResource.type, func.count(DataResource.resource_id))
        .group_by(DataResource.type)
        .all()
    )

    by_type = []
    for type_, count in type_rows:
        by_type.append({
            "value": type_ if type_ else None,
            "count": count,
        })

    # 按 system + type 联合分组（用于二级节点正确显示数量）
    system_type_rows = (
        db.query(DataResource.system, DataResource.type, func.count(DataResource.resource_id))
        .group_by(DataResource.system, DataResource.type)
        .all()
    )

    by_system_type = []
    for system, type_, count in system_type_rows:
        by_system_type.append({
            "system": system if system else None,
            "type": type_ if type_ else None,
            "count": count,
        })

    return {
        "by_system": by_system,
        "by_type": by_type,
        "by_system_type": by_system_type,
        "total": total,
    }


def create_data_resource(db: Session, data: DataResourceCreate) -> DataResource:
    logger.info("创建数据资源")
    obj = DataResource(
        name=data.name,
        type=data.type,
        system=data.system,
        location=data.location,
        description=data.description,
        ddl=data.ddl,
    )
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
    """根据不同的节点 ID（资源/实现/步骤/流程）列出访问链路。

    每条返回记录代表一条逻辑访问链：
    业务流程(Business) -> 步骤(Step) -> 实现(Implementation) -> 数据资源(DataResource)。
    某些环节可能不存在（例如实现未绑定到具体流程或步骤）。
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


# ---- Step-Implementation Links ----


def create_step_implementation_link(db: Session, step_id: str, impl_id: str) -> StepImplementation:
    """创建 Step 与 Implementation 之间的关联，如果已存在则直接返回现有记录。"""

    existing = (
        db.query(StepImplementation)
        .filter(
            StepImplementation.step_id == step_id,
            StepImplementation.impl_id == impl_id,
        )
        .first()
    )
    if existing:
        return existing

    obj = StepImplementation(step_id=step_id, impl_id=impl_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_step_implementation_link(db: Session, link_id: int) -> bool:
    obj = db.query(StepImplementation).filter(StepImplementation.id == link_id).first()
    if not obj:
        return False

    db.delete(obj)
    db.commit()
    return True


# ---- Step ----


def list_steps(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    step_type: Optional[str] = None,
) -> Tuple[List[Step], int]:
    query = db.query(Step)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Step.name.ilike(pattern),
                Step.step_id.ilike(pattern),
                Step.description.ilike(pattern),
            )
        )

    # 按步骤类型过滤
    if step_type is not None:
        if step_type == "":
            # 空字符串表示"其他"（未分类）
            query = query.filter(or_(Step.step_type == None, Step.step_type == ""))
        else:
            query = query.filter(Step.step_type == step_type)

    total = query.count()
    items = (
        query.order_by(Step.step_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_step_group_stats(db: Session) -> dict:
    """获取步骤按类型分组的统计信息"""
    rows = (
        db.query(Step.step_type, func.count(Step.step_id))
        .group_by(Step.step_type)
        .all()
    )

    by_step_type = []
    total = 0
    for step_type, count in rows:
        by_step_type.append({
            "value": step_type if step_type else None,
            "count": count,
        })
        total += count

    return {
        "by_step_type": by_step_type,
        "total": total,
    }


def get_step(db: Session, step_id: str) -> Optional[Step]:
    return db.query(Step).filter(Step.step_id == step_id).first()


def create_step(db: Session, data: StepCreate) -> Step:
    obj = Step(
        name=data.name,
        description=data.description,
        step_type=data.step_type,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_step(db: Session, step_id: str, data: StepUpdate) -> Optional[Step]:
    obj = get_step(db, step_id)
    if not obj:
        return None

    for field, value in data.dict(exclude_unset=True).items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return obj


def delete_step(db: Session, step_id: str) -> bool:
    obj = get_step(db, step_id)
    if not obj:
        return False

    # 删除与步骤相关的流程边关系
    db.query(ProcessStepEdge).filter(
        or_(
            ProcessStepEdge.from_step_id == step_id,
            ProcessStepEdge.to_step_id == step_id,
        )
    ).delete(synchronize_session=False)
    db.query(StepImplementation).filter(StepImplementation.step_id == step_id).delete(
        synchronize_session=False
    )

    db.delete(obj)
    db.commit()
    return True


# ---- Implementation ----


def list_implementations(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    system: Optional[str] = None,
    type_: Optional[str] = None,
) -> Tuple[List[Implementation], int]:
    query = db.query(Implementation)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Implementation.name.ilike(pattern),
                Implementation.impl_id.ilike(pattern),
                Implementation.system.ilike(pattern),
            )
        )

    # 按系统过滤
    if system is not None:
        if system == "":
            query = query.filter(or_(Implementation.system == None, Implementation.system == ""))
        else:
            query = query.filter(Implementation.system == system)

    # 按类型过滤
    if type_ is not None:
        if type_ == "":
            query = query.filter(or_(Implementation.type == None, Implementation.type == ""))
        else:
            query = query.filter(Implementation.type == type_)

    total = query.count()
    items = (
        query.order_by(Implementation.impl_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_implementation_group_stats(db: Session) -> dict:
    """获取实现按系统和类型分组的统计信息"""
    # 按 system 分组
    system_rows = (
        db.query(Implementation.system, func.count(Implementation.impl_id))
        .group_by(Implementation.system)
        .all()
    )

    by_system = []
    total = 0
    for system, count in system_rows:
        by_system.append({
            "value": system if system else None,
            "count": count,
        })
        total += count

    # 按 type 分组
    type_rows = (
        db.query(Implementation.type, func.count(Implementation.impl_id))
        .group_by(Implementation.type)
        .all()
    )

    by_type = []
    for type_, count in type_rows:
        by_type.append({
            "value": type_ if type_ else None,
            "count": count,
        })

    # 按 system + type 联合分组（用于二级节点正确显示数量）
    system_type_rows = (
        db.query(Implementation.system, Implementation.type, func.count(Implementation.impl_id))
        .group_by(Implementation.system, Implementation.type)
        .all()
    )

    by_system_type = []
    for system, type_, count in system_type_rows:
        by_system_type.append({
            "system": system if system else None,
            "type": type_ if type_ else None,
            "count": count,
        })

    return {
        "by_system": by_system,
        "by_type": by_type,
        "by_system_type": by_system_type,
        "total": total,
    }


def get_implementation(db: Session, impl_id: str) -> Optional[Implementation]:
    return (
        db.query(Implementation)
        .filter(Implementation.impl_id == impl_id)
        .first()
    )


def create_implementation(db: Session, data: ImplementationCreate) -> Implementation:
    obj = Implementation(
        name=data.name,
        type=data.type,
        system=data.system,
        description=data.description,
        code_ref=data.code_ref,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_implementation(
    db: Session, impl_id: str, data: ImplementationUpdate
) -> Optional[Implementation]:
    obj = get_implementation(db, impl_id)
    if not obj:
        return None

    for field, value in data.dict(exclude_unset=True).items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return obj


def delete_implementation(db: Session, impl_id: str) -> bool:
    obj = get_implementation(db, impl_id)
    if not obj:
        return False

    # 删除与实现相关的关系
    db.query(StepImplementation).filter(
        StepImplementation.impl_id == impl_id
    ).delete(synchronize_session=False)
    db.query(ImplementationDataResource).filter(
        ImplementationDataResource.impl_id == impl_id
    ).delete(synchronize_session=False)

    db.delete(obj)
    db.commit()
    return True


def batch_create_implementations(
    db: Session, items: List[ImplementationCreate]
) -> dict:
    """批量创建实现单元
    
    Args:
        db: 数据库会话
        items: 要创建的实现单元列表
        
    Returns:
        包含成功、跳过、失败统计的字典
    """
    created_items = []
    skipped_names = []
    failed_items = []
    
    # 获取已存在的名称集合
    existing_names = set(
        name for (name,) in db.query(Implementation.name).all()
    )
    
    # 调试日志
    logger.debug(f"[BatchImport] 数据库中已有 {len(existing_names)} 个实现单元")
    logger.debug(f"[BatchImport] 本次导入 {len(items)} 个")
    if existing_names:
        logger.debug(f"[BatchImport] 已存在示例: {list(existing_names)[:5]}")
    if items:
        logger.debug(f"[BatchImport] 导入示例: {[item.name for item in items[:5]]}")
    
    for item in items:
        try:
            # 检查是否已存在
            if item.name in existing_names:
                logger.debug(f"[BatchImport] 跳过(已存在): {item.name}")
                skipped_names.append(item.name)
                continue
            
            # 创建新记录
            obj = Implementation(
                name=item.name,
                type=item.type,
                system=item.system,
                description=item.description,
                code_ref=item.code_ref,
            )
            db.add(obj)
            db.flush()  # 获取生成的 ID
            created_items.append(obj)
            existing_names.add(item.name)  # 添加到已存在集合，防止同批次重复
            
        except Exception as e:
            failed_items.append({
                "name": item.name,
                "error": str(e)
            })
    
    db.commit()
    
    # 刷新所有创建的对象
    for obj in created_items:
        db.refresh(obj)
    
    return {
        "success_count": len(created_items),
        "skip_count": len(skipped_names),
        "failed_count": len(failed_items),
        "created_items": created_items,
        "skipped_names": skipped_names,
        "failed_items": failed_items,
    }
