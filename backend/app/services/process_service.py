from typing import Any, Dict, List, Optional, Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.resource_graph import Business, Step, ProcessStepEdge


def _business_to_dict(obj: Business) -> Dict[str, Any]:
    entrypoints = (
        obj.entrypoints.split(",") if obj.entrypoints else []
    )
    return {
        "process_id": obj.process_id,
        "name": obj.name,
        "channel": obj.channel,
        "description": obj.description,
        "entrypoints": entrypoints,
    }


def list_processes(db: Session) -> List[Dict[str, Any]]:
    items = db.query(Business).order_by(Business.process_id).all()
    return [_business_to_dict(p) for p in items]


def get_process(db: Session, process_id: str) -> Optional[Dict[str, Any]]:
    obj = db.query(Business).filter(Business.process_id == process_id).first()
    if not obj:
        return None
    return _business_to_dict(obj)


def create_process(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    process_id = data["process_id"]
    existing = db.query(Business).filter(Business.process_id == process_id).first()
    if existing:
        raise ValueError("process_id already exists")

    entrypoints = data.get("entrypoints") or []
    obj = Business(
        process_id=process_id,
        name=data.get("name", ""),
        channel=data.get("channel"),
        description=data.get("description"),
        entrypoints=",".join(entrypoints),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _business_to_dict(obj)


def update_process(db: Session, process_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    obj = db.query(Business).filter(Business.process_id == process_id).first()
    if obj is None:
        raise ValueError("process not found")

    if "name" in data:
        obj.name = data["name"]
    if "channel" in data and data["channel"] is not None:
        obj.channel = data["channel"]
    if "description" in data and data["description"] is not None:
        obj.description = data["description"]
    if "entrypoints" in data and data["entrypoints"] is not None:
        entrypoints = data["entrypoints"] or []
        obj.entrypoints = ",".join(entrypoints)

    db.commit()
    db.refresh(obj)
    return _business_to_dict(obj)


def delete_process(db: Session, process_id: str) -> None:
    # 删除该流程下的边和 Business 本身
    db.query(ProcessStepEdge).filter(
        ProcessStepEdge.process_id == process_id
    ).delete(synchronize_session=False)

    obj = db.query(Business).filter(Business.process_id == process_id).first()
    if obj:
        db.delete(obj)
    db.commit()


def get_process_steps(db: Session, process_id: str) -> List[Dict[str, Any]]:
    """基于 ProcessStepEdge + Step 计算流程内的有序步骤列表。

    为兼容现有前端，返回结构中：
        - step_id: 仅作为流程内位置的序号（从 1 开始）
        - capability_id: 实际的 Step.step_id
        - order_no: 按拓扑排序生成的顺序号（10, 20, ...）
    """

    edges = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .all()
    )

    step_ids = set()
    for e in edges:
        step_ids.add(e.from_step_id)
        step_ids.add(e.to_step_id)

    if not step_ids:
        return []

    steps = (
        db.query(Step)
        .filter(Step.step_id.in_(step_ids))
        .all()
    )
    step_by_id = {s.step_id: s for s in steps}

    # 简单拓扑排序（如果存在环，则剩余节点按 step_id 排序附加到末尾）
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

    result: List[Dict[str, Any]] = []
    for idx, sid in enumerate(ordered):
        s = step_by_id.get(sid)
        result.append(
            {
                "step_id": idx + 1,  # 流程内位置序号
                "process_id": process_id,
                "order_no": (idx + 1) * 10,
                "name": s.name if s else sid,
                "capability_id": sid,
            }
        )

    return result


def save_process_steps(
    db: Session, process_id: str, items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """当前仅支持更新步骤名称。

    顺序由 ProcessStepEdge 表达，因此忽略 order_no。
    """

    for item in items:
        cap_id = item.get("capability_id")
        if not cap_id:
            continue
        step = db.query(Step).filter(Step.step_id == cap_id).first()
        if not step:
            continue
        if "name" in item and item["name"] is not None:
            step.name = item["name"]

    db.commit()
    return get_process_steps(db, process_id)


def delete_process_step(db: Session, process_id: str, step_id: int) -> None:
    """从指定流程中移除一个步骤（通过其在流程内的位置序号 step_id）。

    为了保持 Step 在全局可复用，仅删除该流程下与该 capability 的边。
    """

    steps = get_process_steps(db, process_id)
    target = next((s for s in steps if int(s["step_id"]) == int(step_id)), None)
    if not target:
        return

    cap_id = target.get("capability_id")
    if not cap_id:
        return

    db.query(ProcessStepEdge).filter(
        ProcessStepEdge.process_id == process_id,
        or_(
            ProcessStepEdge.from_step_id == cap_id,
            ProcessStepEdge.to_step_id == cap_id,
        ),
    ).delete(synchronize_session=False)

    db.commit()
