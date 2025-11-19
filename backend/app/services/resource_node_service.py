from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    ProcessStepEdge,
    Implementation,
    ImplementationDataResource,
    Step,
    StepImplementation,
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


# ---- Business ----


def list_businesses(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
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

    total = query.count()
    items = (
        query.order_by(Business.process_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_business(db: Session, process_id: str) -> Optional[Business]:
    return db.query(Business).filter(Business.process_id == process_id).first()


def create_business(db: Session, data: BusinessCreate) -> Business:
    existing = get_business(db, data.process_id)
    if existing:
        raise ValueError(f"Business {data.process_id} already exists")

    obj = Business(
        process_id=data.process_id,
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

    total = query.count()
    items = (
        query.order_by(Step.step_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_step(db: Session, step_id: str) -> Optional[Step]:
    return db.query(Step).filter(Step.step_id == step_id).first()


def create_step(db: Session, data: StepCreate) -> Step:
    existing = get_step(db, data.step_id)
    if existing:
        raise ValueError(f"Step {data.step_id} already exists")

    obj = Step(
        step_id=data.step_id,
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

    total = query.count()
    items = (
        query.order_by(Implementation.impl_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_implementation(db: Session, impl_id: str) -> Optional[Implementation]:
    return (
        db.query(Implementation)
        .filter(Implementation.impl_id == impl_id)
        .first()
    )


def create_implementation(db: Session, data: ImplementationCreate) -> Implementation:
    existing = get_implementation(db, data.impl_id)
    if existing:
        raise ValueError(f"Implementation {data.impl_id} already exists")

    obj = Implementation(
        impl_id=data.impl_id,
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
