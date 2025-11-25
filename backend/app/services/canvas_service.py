from typing import Any, Dict, List, Set

from sqlalchemy.orm import Session

from backend.app.models.resource_graph import Business
from backend.app.repositories.sqlite_repository import SQLiteRepository
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
    """从 SQLite 中加载指定流程的画布结构。"""
    logger.info(f"加载流程画布 process_id={process_id}")
    
    repo = SQLiteRepository(db)
    
    # 1. 获取流程基本信息
    process = repo.get_business(process_id)
    if not process:
        logger.warning(f"流程不存在，无法加载画布 process_id={process_id}")
        raise ValueError("Process not found")

    # 2. 从canvas_node_ids字段读取节点ID列表
    import json
    step_ids: Set[str] = set()
    impl_ids: Set[str] = set()
    resource_ids: Set[str] = set()
    
    if process.canvas_node_ids:
        try:
            node_ids_data = json.loads(process.canvas_node_ids)
            step_ids = set(node_ids_data.get("step_ids", []))
            impl_ids = set(node_ids_data.get("impl_ids", []))
            resource_ids = set(node_ids_data.get("resource_ids", []))
        except json.JSONDecodeError as e:
            logger.warning(f"无法解析canvas_node_ids字段 process_id={process_id}, error={e}")
    
    # 3. 获取流程边
    edges = repo.get_process_edges(process_id)
    
    # 4. 获取步骤信息
    steps = repo.get_steps_by_ids(step_ids)
    
    # 5. 获取步骤-实现关联（限定process_id）
    step_impl_rows = repo.get_step_implementations_by_process(process_id, step_ids)
    
    # 6. 获取实现信息
    implementations = repo.get_implementations_by_ids(impl_ids)
    
    # 7. 获取实现-数据资源关联（限定process_id）
    impl_data_rows = repo.get_implementation_data_resources_by_process(process_id, impl_ids)

    # 8. 获取实现-实现关联（限定process_id）
    impl_link_rows = repo.get_implementation_links_by_process(process_id, impl_ids)
    
    # 9. 获取数据资源信息
    data_resources = repo.get_data_resources_by_ids(resource_ids)

    # 10. 组装返回结果
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
        "impl_links": [
            {
                "id": link.id,
                "from_impl_id": link.from_impl_id,
                "to_impl_id": link.to_impl_id,
                "from_handle": getattr(link, "from_handle", None),
                "to_handle": getattr(link, "to_handle", None),
                "edge_type": link.edge_type,
                "condition": link.condition,
                "label": link.label,
            }
            for link in impl_link_rows
        ],
    }

    logger.info(
        f"画布加载完成 process_id={process_id}, steps={len(steps)}, edges={len(edges)}, impls={len(implementations)}, data_res={len(data_resources)}"
    )

    return result

def save_process_canvas(db: Session, process_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """保存前端提交的画布定义到 SQLite（不包含 Neo4j 同步，由 API 层控制）"""
    process_data: Dict[str, Any] = payload.get("process") or {}
    steps_data: List[Dict[str, Any]] = payload.get("steps") or []
    edges_data: List[Dict[str, Any]] = payload.get("edges") or []
    implementations_data: List[Dict[str, Any]] = payload.get("implementations") or []
    data_resources_data: List[Dict[str, Any]] = payload.get("data_resources") or []
    step_impl_links_data: List[Dict[str, Any]] = payload.get("step_impl_links") or []
    impl_data_links_data: List[Dict[str, Any]] = payload.get("impl_data_links") or []
    impl_links_data: List[Dict[str, Any]] = payload.get("impl_links") or []

    entrypoints = process_data.get("entrypoints") or []
    entrypoints_str = ",".join(entrypoints)

    incoming_step_ids: Set[str] = {
        item["step_id"] for item in steps_data if item.get("step_id")
    }

    logger.info(
        f"保存画布开始 process_id={process_id}, steps={len(steps_data)}, edges={len(edges_data)}, impls={len(implementations_data)}, data_res={len(data_resources_data)}"
    )

    repo = SQLiteRepository(db)
    import json
    
    # ========== 预处理：查询已存在的同名记录，构建ID映射（处理唯一约束）==========
    
    # 1. 业务流程（Business）- 按name去重
    process_name = process_data.get("name")
    if process_name:
        existing_business = repo.get_business_by_name(process_name)
        if existing_business:
            process_id = existing_business.process_id  # 复用已有的process_id
    
    # 2. 步骤（Step）- 按name去重
    step_names = [item.get("name") for item in steps_data if item.get("name")]
    existing_steps = repo.get_steps_by_names(step_names)
    existing_step_name_to_id = {step.name: step.step_id for step in existing_steps}
    
    step_id_mapping: Dict[str, str] = {}
    for step_item in steps_data:
        new_step_id = step_item.get("step_id")
        step_name = step_item.get("name")
        if new_step_id and step_name:
            step_id_mapping[new_step_id] = existing_step_name_to_id.get(step_name, new_step_id)
    
    # 3. 实现（Implementation）- 按name去重
    impl_names = [item.get("name") for item in implementations_data if item.get("name")]
    existing_impls = repo.get_implementations_by_names(impl_names)
    existing_impl_name_to_id = {impl.name: impl.impl_id for impl in existing_impls}
    
    impl_id_mapping: Dict[str, str] = {}
    for impl_item in implementations_data:
        new_impl_id = impl_item.get("impl_id")
        impl_name = impl_item.get("name")
        if new_impl_id and impl_name:
            impl_id_mapping[new_impl_id] = existing_impl_name_to_id.get(impl_name, new_impl_id)
    
    # 4. 数据资源（DataResource）- 按name去重
    res_names = [item.get("name") for item in data_resources_data if item.get("name")]
    existing_resources = repo.get_data_resources_by_names(res_names)
    existing_res_name_to_id = {res.name: res.resource_id for res in existing_resources}
    
    resource_id_mapping: Dict[str, str] = {}
    for res_item in data_resources_data:
        new_resource_id = res_item.get("resource_id")
        res_name = res_item.get("name")
        if new_resource_id and res_name:
            resource_id_mapping[new_resource_id] = existing_res_name_to_id.get(res_name, new_resource_id)
    
    # 使用映射后的实际ID
    actual_step_ids: Set[str] = set(step_id_mapping.values())
    actual_impl_ids: Set[str] = set(impl_id_mapping.values())
    actual_resource_ids: Set[str] = set(resource_id_mapping.values())
    
    # 构造节点ID列表JSON（使用映射后的ID）
    canvas_node_ids_json = json.dumps({
        "step_ids": list(actual_step_ids),
        "impl_ids": list(actual_impl_ids),
        "resource_ids": list(actual_resource_ids),
    })

    # 1. 创建或更新业务流程（包含节点ID列表）
    repo.create_or_update_business(
        process_id=process_id,
        name=process_data.get("name"),
        channel=process_data.get("channel"),
        description=process_data.get("description"),
        entrypoints=entrypoints_str,
        canvas_node_ids=canvas_node_ids_json,
    )

    # 2. 创建或更新步骤（使用映射后的ID）
    for step_item in steps_data:
        orig_step_id = step_item.get("step_id")
        step_name = step_item.get("name")
        if not orig_step_id or not step_name:
            continue
        actual_step_id = step_id_mapping.get(orig_step_id, orig_step_id)
        repo.create_or_update_step(
            step_id=actual_step_id,
            name=step_name,
            description=step_item.get("description"),
            step_type=step_item.get("step_type"),
        )

    # 3. 重建流程边（使用映射后的step_id）
    repo.delete_process_edges(process_id)
    for edge_item in edges_data:
        orig_from_step_id = edge_item.get("from_step_id")
        orig_to_step_id = edge_item.get("to_step_id")
        if not orig_from_step_id or not orig_to_step_id:
            continue
        actual_from_step_id = step_id_mapping.get(orig_from_step_id, orig_from_step_id)
        actual_to_step_id = step_id_mapping.get(orig_to_step_id, orig_to_step_id)
        repo.create_edge(
            process_id=process_id,
            from_step_id=actual_from_step_id,
            to_step_id=actual_to_step_id,
            from_handle=edge_item.get("from_handle"),
            to_handle=edge_item.get("to_handle"),
            edge_type=edge_item.get("edge_type"),
            condition=edge_item.get("condition"),
            label=edge_item.get("label"),
        )

    # 4. 创建或更新实现（使用预处理的映射）
    for impl_item in implementations_data:
        new_impl_id = impl_item.get("impl_id")
        impl_name = impl_item.get("name")
        if not new_impl_id or not impl_name:
            continue
        actual_impl_id = impl_id_mapping.get(new_impl_id, new_impl_id)
        repo.create_or_update_implementation(
            impl_id=actual_impl_id,
            name=impl_name,
            type_=impl_item.get("type"),
            system=impl_item.get("system"),
            description=impl_item.get("description"),
            code_ref=impl_item.get("code_ref"),
        )

    # 5. 创建或更新数据资源（使用预处理的映射）
    for res_item in data_resources_data:
        new_resource_id = res_item.get("resource_id")
        res_name = res_item.get("name")
        if not new_resource_id or not res_name:
            continue
        actual_resource_id = resource_id_mapping.get(new_resource_id, new_resource_id)
        repo.create_or_update_data_resource(
            resource_id=actual_resource_id,
            name=res_name,
            type_=res_item.get("type"),
            system=res_item.get("system"),
            location=res_item.get("location"),
            description=res_item.get("description"),
        )

    # 6. 重建步骤-实现关联（使用映射后的ID）
    repo.delete_step_implementations(process_id, actual_step_ids)
    for link_item in step_impl_links_data:
        orig_step_id = link_item.get("step_id")
        orig_impl_id = link_item.get("impl_id")
        if not orig_step_id or not orig_impl_id:
            continue
        actual_step_id = step_id_mapping.get(orig_step_id, orig_step_id)
        actual_impl_id = impl_id_mapping.get(orig_impl_id, orig_impl_id)
        repo.create_step_implementation(
            process_id=process_id,
            step_id=actual_step_id,
            impl_id=actual_impl_id,
            step_handle=link_item.get("step_handle"),
            impl_handle=link_item.get("impl_handle"),
        )

    # 7. 重建实现-实现关联（使用映射后的ID）
    repo.delete_implementation_links(process_id, actual_impl_ids)
    for link_item in impl_links_data:
        orig_from_impl_id = link_item.get("from_impl_id")
        orig_to_impl_id = link_item.get("to_impl_id")
        if not orig_from_impl_id or not orig_to_impl_id:
            continue
        actual_from_impl_id = impl_id_mapping.get(orig_from_impl_id, orig_from_impl_id)
        actual_to_impl_id = impl_id_mapping.get(orig_to_impl_id, orig_to_impl_id)
        repo.create_implementation_link(
            process_id=process_id,
            from_impl_id=actual_from_impl_id,
            to_impl_id=actual_to_impl_id,
            from_handle=link_item.get("from_handle"),
            to_handle=link_item.get("to_handle"),
            edge_type=link_item.get("edge_type"),
            condition=link_item.get("condition"),
            label=link_item.get("label"),
        )

    # 8. 重建实现-数据资源关联（使用映射后的ID）
    repo.delete_implementation_data_resources(process_id, actual_impl_ids)
    for link_item in impl_data_links_data:
        orig_impl_id = link_item.get("impl_id")
        orig_resource_id = link_item.get("resource_id")
        if not orig_impl_id or not orig_resource_id:
            continue
        actual_impl_id = impl_id_mapping.get(orig_impl_id, orig_impl_id)
        actual_resource_id = resource_id_mapping.get(orig_resource_id, orig_resource_id)
        repo.create_implementation_data_resource(
            process_id=process_id,
            impl_id=actual_impl_id,
            resource_id=actual_resource_id,
            impl_handle=link_item.get("impl_handle"),
            resource_handle=link_item.get("resource_handle"),
            access_type=link_item.get("access_type"),
            access_pattern=link_item.get("access_pattern"),
        )
    
    # 提交更改
    db.commit()

    logger.info(f"保存画布完成 process_id={process_id}")
    return get_process_canvas(db, process_id)
