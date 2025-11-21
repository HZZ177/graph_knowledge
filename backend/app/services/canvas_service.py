from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    DataResource,
    Implementation,
    ImplementationDataResource,
    ProcessStepEdge,
    Step,
    StepImplementation,
)
from backend.app.services.graph_sync_service import sync_process
from backend.app.core.logger import logger


def _business_to_dict(obj: Business) -> Dict[str, Any]:
    """将 Business 模型转换为画布中使用的字典结构。"""

    entrypoints: List[str] = []
    if obj.entrypoints:
        entrypoints = [item for item in obj.entrypoints.split(",") if item]

    return {
        "process_id": obj.process_id,
        "name": obj.name,
        "channel": obj.channel,
        "description": obj.description,
        "entrypoints": entrypoints,
    }


def get_process_canvas(db: Session, process_id: str) -> Dict[str, Any]:
    """从 sqlite 中加载指定流程的画布结构。"""

    logger.info(f"加载流程画布 process_id={process_id}")

    process = (
        db.query(Business)
        .filter(Business.process_id == process_id)
        .first()
    )
    if not process:
        logger.warning(f"流程不存在，无法加载画布 process_id={process_id}")
        raise ValueError("Process not found")

    edges: List[ProcessStepEdge] = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .order_by(ProcessStepEdge.id)
        .all()
    )

    step_ids: Set[str] = set()
    for edge in edges:
        step_ids.add(edge.from_step_id)
        step_ids.add(edge.to_step_id)

    steps: List[Step] = []
    if step_ids:
        steps = (
            db.query(Step)
            .filter(Step.step_id.in_(step_ids))
            .order_by(Step.step_id)
            .all()
        )

    step_impl_rows: Sequence[StepImplementation] = []
    if step_ids:
        step_impl_rows = (
            db.query(StepImplementation)
            .filter(StepImplementation.step_id.in_(step_ids))
            .order_by(StepImplementation.id)
            .all()
        )

    impl_ids: Set[str] = set(link.impl_id for link in step_impl_rows)

    implementations: List[Implementation] = []
    if impl_ids:
        implementations = (
            db.query(Implementation)
            .filter(Implementation.impl_id.in_(impl_ids))
            .order_by(Implementation.impl_id)
            .all()
        )

    impl_data_rows: Sequence[ImplementationDataResource] = []
    if impl_ids:
        impl_data_rows = (
            db.query(ImplementationDataResource)
            .filter(ImplementationDataResource.impl_id.in_(impl_ids))
            .order_by(ImplementationDataResource.id)
            .all()
        )

    resource_ids: Set[str] = set(link.resource_id for link in impl_data_rows)

    data_resources: List[DataResource] = []
    if resource_ids:
        data_resources = (
            db.query(DataResource)
            .filter(DataResource.resource_id.in_(resource_ids))
            .order_by(DataResource.resource_id)
            .all()
        )

    result: Dict[str, Any] = {
        "process": _business_to_dict(process),
        "steps": [
            {
                "step_id": step.step_id,
                "name": step.name,
                "description": step.description,
                "step_type": step.step_type,
            }
            for step in steps
        ],
        "edges": [
            {
                "id": edge.id,
                "from_step_id": edge.from_step_id,
                "to_step_id": edge.to_step_id,
                "from_handle": getattr(edge, "from_handle", None),
                "to_handle": getattr(edge, "to_handle", None),
                "edge_type": edge.edge_type,
                "condition": edge.condition,
                "label": edge.label,
            }
            for edge in edges
        ],
        "implementations": [
            {
                "impl_id": impl.impl_id,
                "name": impl.name,
                "type": impl.type,
                "system": impl.system,
                "description": impl.description,
                "code_ref": impl.code_ref,
            }
            for impl in implementations
        ],
        "step_impl_links": [
            {
                "id": link.id,
                "step_id": link.step_id,
                "impl_id": link.impl_id,
                "step_handle": getattr(link, "step_handle", None),
                "impl_handle": getattr(link, "impl_handle", None),
            }
            for link in step_impl_rows
        ],
        "data_resources": [
            {
                "resource_id": res.resource_id,
                "name": res.name,
                "type": res.type,
                "system": res.system,
                "location": res.location,
                "entity_id": res.entity_id,
                "description": res.description,
            }
            for res in data_resources
        ],
        "impl_data_links": [
            {
                "id": link.id,
                "impl_id": link.impl_id,
                "resource_id": link.resource_id,
                "impl_handle": getattr(link, "impl_handle", None),
                "resource_handle": getattr(link, "resource_handle", None),
                "access_type": link.access_type,
                "access_pattern": link.access_pattern,
            }
            for link in impl_data_rows
        ],
    }

    logger.info(
        f"画布加载完成 process_id={process_id}, steps={len(steps)}, edges={len(edges)}, impls={len(implementations)}, data_res={len(data_resources)}"
    )

    return result

def save_process_canvas(db: Session, process_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """保存前端提交的画布定义，并同步到 Neo4j。"""
    process_data: Dict[str, Any] = payload.get("process") or {}
    steps_data: List[Dict[str, Any]] = payload.get("steps") or []
    edges_data: List[Dict[str, Any]] = payload.get("edges") or []
    implementations_data: List[Dict[str, Any]] = payload.get("implementations") or []
    data_resources_data: List[Dict[str, Any]] = payload.get("data_resources") or []
    step_impl_links_data: List[Dict[str, Any]] = payload.get("step_impl_links") or []
    impl_data_links_data: List[Dict[str, Any]] = payload.get("impl_data_links") or []

    entrypoints = process_data.get("entrypoints") or []
    entrypoints_str = ",".join(entrypoints)

    incoming_step_ids: Set[str] = {
        item["step_id"] for item in steps_data if item.get("step_id")
    }

    incoming_impl_ids: Set[str] = {
        item["impl_id"] for item in implementations_data if item.get("impl_id")
    }

    logger.info(
        f"保存画布开始 process_id={process_id}, steps={len(steps_data)}, edges={len(edges_data)}, impls={len(implementations_data)}, data_res={len(data_resources_data)}"
    )

    with db.begin():
        business: Optional[Business] = (
            db.query(Business)
            .filter(Business.process_id == process_id)
            .first()
        )
        if business is None:
            business = Business(process_id=process_id)
            db.add(business)

        business.name = process_data.get("name", business.name)
        business.channel = process_data.get("channel")
        business.description = process_data.get("description")
        business.entrypoints = entrypoints_str

        for step_item in steps_data:
            step_id = step_item.get("step_id")
            if not step_id:
                continue
            step = db.query(Step).filter(Step.step_id == step_id).first()
            if step is None:
                step = Step(step_id=step_id)
                db.add(step)
            step.name = step_item.get("name")
            step.description = step_item.get("description")
            step.step_type = step_item.get("step_type")

        db.query(ProcessStepEdge).filter(
            ProcessStepEdge.process_id == process_id
        ).delete(synchronize_session=False)

        for edge_item in edges_data:
            from_step_id = edge_item.get("from_step_id")
            to_step_id = edge_item.get("to_step_id")
            if not from_step_id or not to_step_id:
                continue
            db.add(
                ProcessStepEdge(
                    process_id=process_id,
                    from_step_id=from_step_id,
                    to_step_id=to_step_id,
                    from_handle=edge_item.get("from_handle"),
                    to_handle=edge_item.get("to_handle"),
                    edge_type=edge_item.get("edge_type"),
                    condition=edge_item.get("condition"),
                    label=edge_item.get("label"),
                )
            )

        for impl_item in implementations_data:
            impl_id = impl_item.get("impl_id")
            if not impl_id:
                continue
            impl = (
                db.query(Implementation)
                .filter(Implementation.impl_id == impl_id)
                .first()
            )
            if impl is None:
                impl = Implementation(impl_id=impl_id)
                db.add(impl)
            impl.name = impl_item.get("name")
            impl.type = impl_item.get("type")
            impl.system = impl_item.get("system")
            impl.description = impl_item.get("description")
            impl.code_ref = impl_item.get("code_ref")

        for res_item in data_resources_data:
            resource_id = res_item.get("resource_id")
            if not resource_id:
                continue
            resource = (
                db.query(DataResource)
                .filter(DataResource.resource_id == resource_id)
                .first()
            )
            if resource is None:
                resource = DataResource(resource_id=resource_id)
                db.add(resource)
            resource.name = res_item.get("name")
            resource.type = res_item.get("type")
            resource.system = res_item.get("system")
            resource.location = res_item.get("location")
            resource.entity_id = res_item.get("entity_id")
            resource.description = res_item.get("description")

        if incoming_step_ids:
            db.query(StepImplementation).filter(
                StepImplementation.step_id.in_(incoming_step_ids)
            ).delete(synchronize_session=False)

        for link_item in step_impl_links_data:
            step_id = link_item.get("step_id")
            impl_id = link_item.get("impl_id")
            if not step_id or not impl_id:
                continue
            db.add(
                StepImplementation(
                    step_id=step_id,
                    impl_id=impl_id,
                    step_handle=link_item.get("step_handle"),
                    impl_handle=link_item.get("impl_handle"),
                )
            )

        if incoming_impl_ids:
            db.query(ImplementationDataResource).filter(
                ImplementationDataResource.impl_id.in_(incoming_impl_ids)
            ).delete(synchronize_session=False)

        for link_item in impl_data_links_data:
            impl_id = link_item.get("impl_id")
            resource_id = link_item.get("resource_id")
            if not impl_id or not resource_id:
                continue
            db.add(
                ImplementationDataResource(
                    impl_id=impl_id,
                    resource_id=resource_id,
                    impl_handle=link_item.get("impl_handle"),
                    resource_handle=link_item.get("resource_handle"),
                    access_type=link_item.get("access_type"),
                    access_pattern=link_item.get("access_pattern"),
                )
            )

    logger.info(f"开始同步流程到图数据库 process_id={process_id}")
    sync_process(db, process_id)

    logger.info(f"保存画布完成 process_id={process_id}")
    return get_process_canvas(db, process_id)
