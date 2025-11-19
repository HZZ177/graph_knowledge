from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    Step,
    Implementation,
    ImplementationDataResource,
    StepImplementation,
    DataResource,
    ProcessStepEdge,
)
from .process_service import get_process


def get_process_context(db: Session, process_id: str) -> Dict[str, Any]:
    """基于 sqlite 中的业务表与关系表构建流程上下文。

    返回结构保持与原 PoC 版本兼容：
        {
          "process": { ... },
          "steps": [
            {
              "step": {...},
              "implementations": [...],
              "data_resources": [...],
            },
            ...
          ]
        }
    """

    process = get_process(db, process_id)
    if not process:
        raise ValueError(f"Unknown process_id: {process_id}")

    # 找出该流程涉及的步骤（基于 ProcessStepEdge）
    edges = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .all()
    )

    step_ids = set()
    for e in edges:
        step_ids.add(e.from_step_id)
        step_ids.add(e.to_step_id)

    steps_q = db.query(Step)
    if step_ids:
        steps_q = steps_q.filter(Step.step_id.in_(step_ids))
    steps_db = steps_q.all()
    step_by_id = {s.step_id: s for s in steps_db}

    # 简单拓扑排序，得到顺序（与 process_service.get_process_steps 保持一致）
    indegree: Dict[str, int] = {sid: 0 for sid in step_ids}
    adj: Dict[str, List[str]] = {sid: [] for sid in step_ids}
    for e in edges:
        if e.from_step_id in step_ids and e.to_step_id in step_ids:
            adj[e.from_step_id].append(e.to_step_id)
            indegree[e.to_step_id] += 1

    queue: List[str] = [sid for sid, deg in indegree.items() if deg == 0]
    ordered: List[str] = []
    while queue:
        sid = queue.pop(0)
        ordered.append(sid)
        for nb in adj.get(sid, []):
            indegree[nb] -= 1
            if indegree[nb] == 0:
                queue.append(nb)

    remaining = [sid for sid in step_ids if sid not in ordered]
    ordered.extend(sorted(remaining))

    # 预加载实现与数据访问关系
    impl_rows = (
        db.query(StepImplementation, Implementation)
        .join(Implementation, StepImplementation.impl_id == Implementation.impl_id)
        .filter(StepImplementation.step_id.in_(step_ids))
        .all()
    )
    impls_by_step: Dict[str, List[Implementation]] = {}
    for link, impl in impl_rows:
        impls_by_step.setdefault(link.step_id, []).append(impl)

    da_rows = (
        db.query(
            StepImplementation.step_id,
            ImplementationDataResource,
            DataResource,
        )
        .join(
            Implementation,
            StepImplementation.impl_id == Implementation.impl_id,
        )
        .join(
            ImplementationDataResource,
            Implementation.impl_id == ImplementationDataResource.impl_id,
        )
        .join(
            DataResource,
            ImplementationDataResource.resource_id == DataResource.resource_id,
        )
        .filter(StepImplementation.step_id.in_(step_ids))
        .all()
    )

    data_by_step: Dict[str, List[Dict[str, Any]]] = {}
    impl_data_links: List[Dict[str, Any]] = []
    seen_impl_data_ids: set[int] = set()
    for step_id, link, dr in da_rows:
        data_by_step.setdefault(step_id, []).append(
            {
                "resource_id": dr.resource_id,
                "name": dr.name,
                "type": dr.type,
                "system": dr.system,
                "description": dr.description,
                "access_type": link.access_type,
                "access_pattern": link.access_pattern,
            }
        )

        if link.id not in seen_impl_data_ids:
            seen_impl_data_ids.add(link.id)
            impl_data_links.append(
                {
                    "id": link.id,
                    "impl_id": link.impl_id,
                    "resource_id": link.resource_id,
                    "access_type": link.access_type,
                    "access_pattern": link.access_pattern,
                }
            )

    # Step-Implementation 关系列表
    step_impl_links: List[Dict[str, Any]] = []
    for link, impl in impl_rows:
        step_impl_links.append(
            {
                "id": link.id,
                "step_id": link.step_id,
                "impl_id": link.impl_id,
            }
        )

    steps: List[Dict[str, Any]] = []
    for idx, sid in enumerate(ordered):
        s = step_by_id.get(sid)
        if not s:
          # 跳过找不到定义的步骤
          continue

        impl_items: List[Dict[str, Any]] = []
        for impl in impls_by_step.get(sid, []):
            impl_items.append(
                {
                    "impl_id": impl.impl_id,
                    "name": impl.name,
                    "type": impl.type,
                    "system": impl.system,
                    "code_ref": impl.code_ref,
                    "capability_id": sid,
                }
            )

        data_items: List[Dict[str, Any]] = data_by_step.get(sid, [])

        step_entry: Dict[str, Any] = {
            "step": {
                "order_no": (idx + 1) * 10,
                "step_id": sid,
                "name": s.name,
                "description": s.description,
                "step_type": s.step_type,
            },
            "implementations": impl_items,
            "data_resources": data_items,
        }
        steps.append(step_entry)

    return {
        "process": process,
        "steps": steps,
        "step_impl_links": step_impl_links,
        "impl_data_links": impl_data_links,
    }
