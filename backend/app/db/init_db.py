from sqlalchemy.orm import Session

from uuid import uuid4
import json

from backend.app.models.resource_graph import (
    Business,
    Step,
    Implementation,
    DataResource,
    ProcessStepEdge,
    StepImplementation,
    ImplementationDataResource,
)
from test.neo4j_load_open_card import SAMPLE_DATA


def init_db(db: Session) -> None:
    """如果业务表为空，则根据 SAMPLE_DATA 初始化 sqlite 数据。

    仅在第一次启动时导入一次，之后如果表中已有数据则跳过。
    """

    # 如果已经有业务流程，认为已经初始化过
    existing_business = db.query(Business).first()
    if existing_business:
        return

    # 1. Business：为每个业务流程生成独立的 UUID 作为 process_id
    process_id_map = {}
    for item in SAMPLE_DATA.get("business_processes", []):
        original_pid = item["process_id"]
        new_pid = uuid4().hex
        process_id_map[original_pid] = new_pid

        db.add(
            Business(
                process_id=new_pid,
                name=item.get("name", ""),
                channel=item.get("channel"),
                description=item.get("description"),
                entrypoints=item.get("entrypoints", ""),
            )
        )

    # 2. Step（来自 business_capabilities）：为每个 capability 生成 UUID step_id
    step_id_by_cap = {}
    for cap in SAMPLE_DATA.get("business_capabilities", []):
        cap_id = cap["capability_id"]
        new_step_id = uuid4().hex
        step_id_by_cap[cap_id] = new_step_id

        db.add(
            Step(
                step_id=new_step_id,
                name=cap.get("name", ""),
                description=cap.get("description"),
                step_type=cap.get("capability_type"),
            )
        )

    # 3. Implementation：为每个 capability 生成 UUID impl_id 并记录映射关系
    impl_id_by_cap = {}
    for impl in SAMPLE_DATA.get("capability_implementations", []):
        cap_id = impl["capability_id"]
        impl_id = uuid4().hex
        impl_id_by_cap[cap_id] = impl_id

        db.add(
            Implementation(
                impl_id=impl_id,
                name=impl.get("entry_name", ""),
                type=impl.get("entry_type"),
                system=impl.get("system"),
                description=None,
                code_ref=impl.get("code_ref"),
            )
        )

    # 4. DataResource：为每个数据资源生成 UUID resource_id
    resource_id_map = {}
    for dr in SAMPLE_DATA.get("data_resources", []):
        original_rid = dr["resource_id"]
        new_rid = uuid4().hex
        resource_id_map[original_rid] = new_rid

        db.add(
            DataResource(
                resource_id=new_rid,
                name=dr.get("name", ""),
                type=dr.get("type"),
                system=dr.get("system"),
                location=dr.get("location"),
                description=dr.get("description"),
            )
        )

    db.flush()

    # 5. ProcessStepEdge：根据 SAMPLE_DATA 中的 order_no 生成主链路边，
    # 使用上面生成的 UUID process_id / step_id
    steps_by_process = {}
    for s in SAMPLE_DATA.get("business_process_steps", []):
        steps_by_process.setdefault(s["process_id"], []).append(s)

    for process_id, items in steps_by_process.items():
        items_sorted = sorted(items, key=lambda x: x.get("order_no", 0))
        for prev, curr in zip(items_sorted, items_sorted[1:]):
            new_process_id = process_id_map.get(process_id)
            from_step = step_id_by_cap.get(prev["capability_id"])
            to_step = step_id_by_cap.get(curr["capability_id"])
            if not new_process_id or not from_step or not to_step:
                continue
            db.add(
                ProcessStepEdge(
                    process_id=new_process_id,
                    from_step_id=from_step,
                    to_step_id=to_step,
                    edge_type=None,
                    condition=None,
                    label=None,
                )
            )

    # 6. StepImplementation（基于 capability_id → step_id / impl_id 映射）
    # 注意：需要找到该 capability 属于哪个 process
    cap_to_process = {}
    for s in SAMPLE_DATA.get("business_process_steps", []):
        cap_to_process[s["capability_id"]] = s["process_id"]
    
    for impl in SAMPLE_DATA.get("capability_implementations", []):
        cap_id = impl["capability_id"]
        impl_id = impl_id_by_cap.get(cap_id)
        step_id = step_id_by_cap.get(cap_id)
        original_process_id = cap_to_process.get(cap_id)
        new_process_id = process_id_map.get(original_process_id) if original_process_id else None
        
        if not impl_id or not step_id or not new_process_id:
            continue
        db.add(
            StepImplementation(
                process_id=new_process_id,
                step_id=step_id,
                impl_id=impl_id,
            )
        )

    # 7. ImplementationDataResource（通过 capability_id 找到对应 impl_id，
    #    通过原始 resource_id 找到新的 UUID resource_id）
    for da in SAMPLE_DATA.get("capability_data_access", []):
        cap_id = da["capability_id"]
        impl_id = impl_id_by_cap.get(cap_id)
        new_res_id = resource_id_map.get(da["resource_id"])
        original_process_id = cap_to_process.get(cap_id)
        new_process_id = process_id_map.get(original_process_id) if original_process_id else None
        
        if not impl_id or not new_res_id or not new_process_id:
            continue
        db.add(
            ImplementationDataResource(
                process_id=new_process_id,
                impl_id=impl_id,
                resource_id=new_res_id,
                access_type=da.get("access_type"),
                access_pattern=da.get("access_pattern"),
            )
        )

    # 8. 为每个 Business 填充 canvas_node_ids
    # 收集每个流程包含的节点ID
    process_nodes = {}  # {process_id: {step_ids: [], impl_ids: [], resource_ids: []}}
    
    # 从 business_process_steps 收集步骤ID
    for s in SAMPLE_DATA.get("business_process_steps", []):
        original_process_id = s["process_id"]
        new_process_id = process_id_map.get(original_process_id)
        cap_id = s["capability_id"]
        step_id = step_id_by_cap.get(cap_id)
        
        if new_process_id and step_id:
            if new_process_id not in process_nodes:
                process_nodes[new_process_id] = {"step_ids": [], "impl_ids": [], "resource_ids": []}
            if step_id not in process_nodes[new_process_id]["step_ids"]:
                process_nodes[new_process_id]["step_ids"].append(step_id)
    
    # 从 capability_implementations 收集实现ID
    for impl in SAMPLE_DATA.get("capability_implementations", []):
        cap_id = impl["capability_id"]
        impl_id = impl_id_by_cap.get(cap_id)
        original_process_id = cap_to_process.get(cap_id)
        new_process_id = process_id_map.get(original_process_id) if original_process_id else None
        
        if new_process_id and impl_id:
            if new_process_id not in process_nodes:
                process_nodes[new_process_id] = {"step_ids": [], "impl_ids": [], "resource_ids": []}
            if impl_id not in process_nodes[new_process_id]["impl_ids"]:
                process_nodes[new_process_id]["impl_ids"].append(impl_id)
    
    # 从 capability_data_access 收集数据资源ID
    for da in SAMPLE_DATA.get("capability_data_access", []):
        cap_id = da["capability_id"]
        new_res_id = resource_id_map.get(da["resource_id"])
        original_process_id = cap_to_process.get(cap_id)
        new_process_id = process_id_map.get(original_process_id) if original_process_id else None
        
        if new_process_id and new_res_id:
            if new_process_id not in process_nodes:
                process_nodes[new_process_id] = {"step_ids": [], "impl_ids": [], "resource_ids": []}
            if new_res_id not in process_nodes[new_process_id]["resource_ids"]:
                process_nodes[new_process_id]["resource_ids"].append(new_res_id)
    
    # 更新每个 Business 的 canvas_node_ids
    for process_id, node_ids in process_nodes.items():
        business = db.query(Business).filter(Business.process_id == process_id).first()
        if business:
            business.canvas_node_ids = json.dumps(node_ids)

    db.commit()
