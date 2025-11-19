from sqlalchemy.orm import Session

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

    # 1. Business
    for item in SAMPLE_DATA.get("business_processes", []):
        db.add(
            Business(
                process_id=item["process_id"],
                name=item.get("name", ""),
                channel=item.get("channel"),
                description=item.get("description"),
                entrypoints=",".join(item.get("entrypoints", []) or []),
            )
        )

    # 2. Step（来自 business_capabilities）
    for cap in SAMPLE_DATA.get("business_capabilities", []):
        db.add(
            Step(
                step_id=cap["capability_id"],
                name=cap.get("name", ""),
                description=cap.get("description"),
                step_type=cap.get("capability_type"),
            )
        )

    # 3. Implementation
    # 为每个 capability 生成稳定的 impl_id（impl_1...），并记录映射关系
    impl_id_by_cap = {}
    for idx, impl in enumerate(SAMPLE_DATA.get("capability_implementations", []), start=1):
        cap_id = impl["capability_id"]
        impl_id = f"impl_{idx}"
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

    # 4. DataResource
    for dr in SAMPLE_DATA.get("data_resources", []):
        db.add(
            DataResource(
                resource_id=dr["resource_id"],
                name=dr.get("name", ""),
                type=dr.get("type"),
                system=dr.get("system"),
                location=dr.get("location"),
                entity_id=dr.get("entity_id"),
                description=dr.get("description"),
            )
        )

    db.flush()

    # 5. ProcessStepEdge：根据 SAMPLE_DATA 中的 order_no 生成主链路边
    steps_by_process = {}
    for s in SAMPLE_DATA.get("business_process_steps", []):
        steps_by_process.setdefault(s["process_id"], []).append(s)

    for process_id, items in steps_by_process.items():
        items_sorted = sorted(items, key=lambda x: x.get("order_no", 0))
        for prev, curr in zip(items_sorted, items_sorted[1:]):
            db.add(
                ProcessStepEdge(
                    process_id=process_id,
                    from_step_id=prev["capability_id"],
                    to_step_id=curr["capability_id"],
                    edge_type=None,
                    condition=None,
                    label=None,
                )
            )

    # 6. StepImplementation（基于 capability_id → impl_id 映射）
    for impl in SAMPLE_DATA.get("capability_implementations", []):
        cap_id = impl["capability_id"]
        impl_id = impl_id_by_cap.get(cap_id)
        if not impl_id:
            continue
        db.add(
            StepImplementation(
                step_id=cap_id,
                impl_id=impl_id,
            )
        )

    # 7. ImplementationDataResource（通过 capability_id 找到对应 impl_id）
    for da in SAMPLE_DATA.get("capability_data_access", []):
        cap_id = da["capability_id"]
        impl_id = impl_id_by_cap.get(cap_id)
        if not impl_id:
            continue
        db.add(
            ImplementationDataResource(
                impl_id=impl_id,
                resource_id=da["resource_id"],
                access_type=da.get("access_type"),
                access_pattern=da.get("access_pattern"),
            )
        )

    db.commit()
