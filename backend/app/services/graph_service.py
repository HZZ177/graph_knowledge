from typing import Any, Dict, List, Optional, Sequence

from neo4j.exceptions import ServiceUnavailable, AuthError, ClientError

from backend.app.db.neo4j_client import get_neo4j_driver, DEFAULT_NEO4J_DATABASE
from backend.app.core.logger import logger


_GRAPH_REL_TYPES = [
    "START_AT",
    "NEXT",
    "EXECUTED_BY",
    "ACCESSES_RESOURCE",
    "IMPL_CALL",
]


def _node_props(node) -> Dict[str, Any]:
    return {k: node.get(k) for k in node.keys()}


def _business_from_node(node) -> Dict[str, Any]:
    props = _node_props(node)
    return {
        "process_id": props.get("process_id"),
        "name": props.get("name"),
        "channel": props.get("channel"),
        "description": props.get("description"),
        "entrypoints": props.get("entrypoints"),
    }


def _step_from_node(node) -> Dict[str, Any]:
    props = _node_props(node)
    return {
        "step_id": props.get("step_id"),
        "name": props.get("name"),
        "description": props.get("description"),
        "step_type": props.get("step_type"),
    }


def _implementation_from_node(node) -> Dict[str, Any]:
    props = _node_props(node)
    return {
        "impl_id": props.get("impl_id"),
        "name": props.get("name"),
        "type": props.get("type"),
        "system": props.get("system"),
        "description": props.get("description"),
        "code_ref": props.get("code_ref"),
    }


def _data_resource_from_node(node) -> Dict[str, Any]:
    props = _node_props(node)
    return {
        "resource_id": props.get("resource_id"),
        "name": props.get("name"),
        "type": props.get("type"),
        "system": props.get("system"),
        "description": props.get("description"),
    }


def get_business_context(process_id: str) -> Dict[str, Any]:
    """基于 Neo4j 获取指定业务流程的完整图上下文。"""

    logger.info(f"[图查询] 获取业务流程上下文 process_id={process_id}")
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            record = (
                session.run(
                    "MATCH (b:Business {process_id: $pid}) RETURN b", pid=process_id
                ).single()
            )
            if not record:
                msg = f"流程不存在: {process_id}"
                logger.warning(f"[图查询] {msg}")
                raise ValueError(msg)
            b_node = record["b"]
            process = _business_from_node(b_node)

            edge_records = session.run(
                """
                MATCH (from:Step)-[e:NEXT {process_id: $pid}]->(to:Step)
                RETURN from.step_id AS from_id,
                       to.step_id AS to_id,
                       e.edge_type AS edge_type,
                       e.condition AS condition,
                       e.label AS label
                """,
                pid=process_id,
            )
            edges: List[Dict[str, Any]] = [r.data() for r in edge_records]

            step_ids = set()
            for e in edges:
                step_ids.add(e["from_id"])
                step_ids.add(e["to_id"])

            exec_step_records = session.run(
                """
                MATCH (s:Step)-[:EXECUTED_BY {process_id: $pid}]->(:Implementation)
                RETURN DISTINCT s.step_id AS step_id
                """,
                pid=process_id,
            )
            for r in exec_step_records:
                step_ids.add(r["step_id"])

            step_by_id: Dict[str, Dict[str, Any]] = {}
            if step_ids:
                step_result = session.run(
                    """
                    MATCH (s:Step)
                    WHERE s.step_id IN $step_ids
                    RETURN s
                    """,
                    step_ids=list(step_ids),
                )
                for r in step_result:
                    s_node = r["s"]
                    sid = s_node.get("step_id")
                    if sid is None:
                        continue
                    step_by_id[sid] = _step_from_node(s_node)

            indegree: Dict[str, int] = {sid: 0 for sid in step_ids}
            adj: Dict[str, List[str]] = {sid: [] for sid in step_ids}
            for e in edges:
                from_id = e["from_id"]
                to_id = e["to_id"]
                if from_id in adj and to_id in adj:
                    adj[from_id].append(to_id)
                    indegree[to_id] += 1

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

            prev_steps_by_id: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in step_ids}
            next_steps_by_id: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in step_ids}
            for e in edges:
                from_id = e["from_id"]
                to_id = e["to_id"]

                from_step = step_by_id.get(from_id)
                to_step = step_by_id.get(to_id)

                next_entry = {
                    "step_id": to_id,
                    "name": to_step.get("name") if to_step else None,
                    "edge_type": e.get("edge_type"),
                    "condition": e.get("condition"),
                    "label": e.get("label"),
                }
                if from_id in next_steps_by_id:
                    next_steps_by_id[from_id].append(next_entry)

                prev_entry = {
                    "step_id": from_id,
                    "name": from_step.get("name") if from_step else None,
                    "edge_type": e.get("edge_type"),
                    "condition": e.get("condition"),
                    "label": e.get("label"),
                }
                if to_id in prev_steps_by_id:
                    prev_steps_by_id[to_id].append(prev_entry)

            impl_rows = session.run(
                """
                MATCH (s:Step)-[r:EXECUTED_BY {process_id: $pid}]->(i:Implementation)
                WHERE s.step_id IN $step_ids
                RETURN s.step_id AS step_id, i
                """,
                pid=process_id,
                step_ids=list(step_ids) if step_ids else [],
            )
            impls_by_step: Dict[str, List[Dict[str, Any]]] = {}
            impl_ids_by_step: Dict[str, List[str]] = {}
            impl_by_id: Dict[str, Dict[str, Any]] = {}
            for r in impl_rows:
                step_id = r["step_id"]
                i_node = r["i"]
                impl = _implementation_from_node(i_node)
                impls_by_step.setdefault(step_id, []).append(impl)
                impl_id = impl.get("impl_id")
                if impl_id is not None:
                    impl_ids_by_step.setdefault(step_id, []).append(impl_id)
                    if impl_id not in impl_by_id:
                        impl_by_id[impl_id] = impl

            data_rows = session.run(
                """
                MATCH (s:Step)-[:EXECUTED_BY {process_id: $pid}]->(i:Implementation)
                MATCH (i)-[r:ACCESSES_RESOURCE {process_id: $pid}]->(d:DataResource)
                WHERE s.step_id IN $step_ids
                RETURN s.step_id AS step_id,
                       i.impl_id AS impl_id,
                       d,
                       r
                """,
                pid=process_id,
                step_ids=list(step_ids) if step_ids else [],
            )

            data_by_step: Dict[str, List[Dict[str, Any]]] = {}
            resources_by_id: Dict[str, Dict[str, Any]] = {}
            accessed_resources_by_impl: Dict[str, List[Dict[str, Any]]] = {}
            for r in data_rows:
                step_id = r["step_id"]
                impl_id = r["impl_id"]
                d_node = r["d"]
                rel = r["r"]
                dr = _data_resource_from_node(d_node)
                resource_id = dr.get("resource_id")
                if resource_id is not None and resource_id not in resources_by_id:
                    resources_by_id[resource_id] = dr

                entry = {
                    **dr,
                    "access_type": rel.get("access_type"),
                    "access_pattern": rel.get("access_pattern"),
                }
                data_by_step.setdefault(step_id, []).append(entry)

                accessed_entry = {
                    "resource": dr,
                    "access": {
                        "access_type": rel.get("access_type"),
                        "access_pattern": rel.get("access_pattern"),
                        "process_id": rel.get("process_id"),
                    },
                }
                accessed_resources_by_impl.setdefault(impl_id, []).append(
                    accessed_entry
                )

            impl_impl_rows = session.run(
                """
                MATCH (from:Implementation)-[r:IMPL_CALL {process_id: $pid}]->(to:Implementation)
                RETURN from.impl_id AS from_impl_id,
                       to.impl_id AS to_impl_id,
                       r.edge_type AS edge_type,
                       r.condition AS condition,
                       r.label AS label,
                       r.process_id AS process_id
                """,
                pid=process_id,
            )
            impl_impl_links = [row.data() for row in impl_impl_rows]

            called_impls_by_impl: Dict[str, List[Dict[str, Any]]] = {}
            called_by_impls_by_impl: Dict[str, List[Dict[str, Any]]] = {}
            for link in impl_impl_links:
                from_id = link.get("from_impl_id")
                to_id = link.get("to_impl_id")
                if not from_id or not to_id:
                    continue

                from_impl = impl_by_id.get(from_id)
                to_impl = impl_by_id.get(to_id)

                if to_impl is not None:
                    outgoing_entry = {
                        "impl": {
                            "impl_id": to_impl.get("impl_id"),
                            "name": to_impl.get("name"),
                            "type": to_impl.get("type"),
                            "system": to_impl.get("system"),
                        },
                        "edge_type": link.get("edge_type"),
                        "condition": link.get("condition"),
                        "label": link.get("label"),
                        "process_id": link.get("process_id"),
                    }
                    called_impls_by_impl.setdefault(from_id, []).append(
                        outgoing_entry
                    )

                if from_impl is not None:
                    incoming_entry = {
                        "impl": {
                            "impl_id": from_impl.get("impl_id"),
                            "name": from_impl.get("name"),
                            "type": from_impl.get("type"),
                            "system": from_impl.get("system"),
                        },
                        "edge_type": link.get("edge_type"),
                        "condition": link.get("condition"),
                        "label": link.get("label"),
                        "process_id": link.get("process_id"),
                    }
                    called_by_impls_by_impl.setdefault(to_id, []).append(
                        incoming_entry
                    )

            steps: List[Dict[str, Any]] = []
            for idx, sid in enumerate(ordered):
                s = step_by_id.get(sid)
                if not s:
                    continue

                impl_refs: List[Dict[str, Any]] = []
                for impl_id in impl_ids_by_step.get(sid, []):
                    impl = impl_by_id.get(impl_id)
                    if not impl:
                        continue
                    impl_refs.append(
                        {
                            "impl_id": impl.get("impl_id"),
                            "name": impl.get("name"),
                            "type": impl.get("type"),
                            "system": impl.get("system"),
                            "description": impl.get("description"),
                            "code_ref": impl.get("code_ref"),
                        }
                    )

                step_entry: Dict[str, Any] = {
                    "step": {
                        "order_no": (idx + 1) * 10,
                        "step_id": sid,
                        "name": s.get("name"),
                        "description": s.get("description"),
                        "step_type": s.get("step_type"),
                    },
                    "prev_steps": prev_steps_by_id.get(sid, []),
                    "next_steps": next_steps_by_id.get(sid, []),
                    "implementations": impl_refs,
                    "data_resources": data_by_step.get(sid, []),
                }
                steps.append(step_entry)

            implementations: List[Dict[str, Any]] = []
            for impl_id, impl in impl_by_id.items():
                implementations.append(
                    {
                        **impl,
                        "accessed_resources": accessed_resources_by_impl.get(
                            impl_id, []
                        ),
                        "called_impls": called_impls_by_impl.get(impl_id, []),
                        "called_by_impls": called_by_impls_by_impl.get(impl_id, []),
                    }
                )

            resources: List[Dict[str, Any]] = list(resources_by_id.values())

            logger.info(
                f"[图查询] 获取业务流程上下文成功 process_id={process_id}, steps={len(steps)}, implementations={len(implementations)}, resources={len(resources)}"
            )

            return {
                "process": process,
                "steps": steps,
                "implementations": implementations,
                "resources": resources,
            }
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(
            f"[图查询] 获取业务流程上下文 Neo4j 错误 process_id={process_id}, error={e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[图查询] 获取业务流程上下文未知异常 process_id={process_id}, error={e}",
            exc_info=True,
        )
        raise
    finally:
        driver.close()


def list_businesses(
    channel: Optional[str] = None,
    name_contains: Optional[str] = None,
    uses_system: Optional[str] = None,
    uses_resource: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按条件从 Neo4j 中查询业务流程列表。"""

    logger.info(
        f"[图查询] 列出业务流程 channel={channel}, name_contains={name_contains}, uses_system={uses_system}, uses_resource={uses_resource}"
    )
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            records = session.run(
                """
                MATCH (b:Business)
                WHERE ($channel IS NULL OR b.channel = $channel)
                  AND ($name_contains IS NULL OR toLower(b.name) CONTAINS toLower($name_contains))
                  AND ($uses_system IS NULL OR EXISTS {
                        MATCH (b)-[:START_AT|NEXT*0..10]->(s:Step)-[:EXECUTED_BY {process_id: b.process_id}]->(i:Implementation)
                        WHERE i.system = $uses_system
                      })
                  AND ($uses_resource IS NULL OR EXISTS {
                        MATCH (b)-[:START_AT|NEXT*0..10]->(s:Step)-[:EXECUTED_BY {process_id: b.process_id}]->(i:Implementation)-[:ACCESSES_RESOURCE {process_id: b.process_id}]->(r:DataResource)
                        WHERE r.resource_id = $uses_resource
                      })
                RETURN b
                ORDER BY b.name
                """,
                channel=channel,
                name_contains=name_contains,
                uses_system=uses_system,
                uses_resource=uses_resource,
            )
            result: List[Dict[str, Any]] = []
            for r in records:
                b_node = r["b"]
                result.append(_business_from_node(b_node))

            logger.info(f"[图查询] 列出业务流程完成 count={len(result)}")
            return result
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(f"[图查询] 列出业务流程 Neo4j 错误 error={e}")
        raise
    except Exception as e:
        logger.error(f"[图查询] 列出业务流程未知异常 error={e}", exc_info=True)
        raise
    finally:
        driver.close()


def get_resource_usages(resource_id: str) -> Dict[str, Any]:
    """查询指定数据资源在各业务流程中的使用情况。"""

    logger.info(f"[图查询] 查询数据资源使用情况 resource_id={resource_id}")
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            res_record = (
                session.run(
                    "MATCH (r:DataResource {resource_id: $rid}) RETURN r",
                    rid=resource_id,
                ).single()
            )
            if not res_record:
                msg = f"数据资源不存在: {resource_id}"
                logger.warning(f"[图查询] {msg}")
                raise ValueError(msg)
            r_node = res_record["r"]
            resource = _data_resource_from_node(r_node)

            rows = session.run(
                """
                MATCH (i:Implementation)-[ar:ACCESSES_RESOURCE]->(r:DataResource {resource_id: $rid})
                MATCH (s:Step)-[ex:EXECUTED_BY {process_id: ar.process_id}]->(i)
                MATCH (b:Business {process_id: ar.process_id})
                RETURN b, s, i, ar
                ORDER BY b.name, s.name, i.name
                """,
                rid=resource_id,
            )
            usages: List[Dict[str, Any]] = []
            for row in rows:
                b_node = row["b"]
                s_node = row["s"]
                i_node = row["i"]
                ar = row["ar"]
                usages.append(
                    {
                        "process": _business_from_node(b_node),
                        "step": _step_from_node(s_node),
                        "implementation": _implementation_from_node(i_node),
                        "access": {
                            "access_type": ar.get("access_type"),
                            "access_pattern": ar.get("access_pattern"),
                            "process_id": ar.get("process_id"),
                        },
                    }
                )

            logger.info(
                f"[图查询] 查询数据资源使用情况完成 resource_id={resource_id}, usages={len(usages)}"
            )
            return {"resource": resource, "usages": usages}
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(
            f"[图查询] 查询数据资源使用情况 Neo4j 错误 resource_id={resource_id}, error={e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[图查询] 查询数据资源使用情况未知异常 resource_id={resource_id}, error={e}",
            exc_info=True,
        )
        raise
    finally:
        driver.close()


def get_resource_context(resource_id: str) -> Dict[str, Any]:
    """围绕指定数据资源返回相关业务、步骤与实现的上下文。"""

    logger.info(f"[图查询] 获取数据资源上下文 resource_id={resource_id}")
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            res_record = (
                session.run(
                    "MATCH (r:DataResource {resource_id: $rid}) RETURN r",
                    rid=resource_id,
                ).single()
            )
            if not res_record:
                msg = f"数据资源不存在: {resource_id}"
                logger.warning(f"[图查询] {msg}")
                raise ValueError(msg)
            r_node = res_record["r"]
            resource = _data_resource_from_node(r_node)

            rows = session.run(
                """
                MATCH (i:Implementation)-[ar:ACCESSES_RESOURCE]->(r:DataResource {resource_id: $rid})
                OPTIONAL MATCH (s:Step)-[ex:EXECUTED_BY {process_id: ar.process_id}]->(i)
                OPTIONAL MATCH (b:Business {process_id: ar.process_id})
                RETURN b, s, i, ar
                """,
                rid=resource_id,
            )

            businesses: Dict[str, Dict[str, Any]] = {}
            steps: Dict[str, Dict[str, Any]] = {}
            implementations: Dict[str, Dict[str, Any]] = {}
            impl_resource_links: List[Dict[str, Any]] = []

            for row in rows:
                b_node = row["b"]
                s_node = row["s"]
                i_node = row["i"]
                ar = row["ar"]

                if b_node is not None:
                    b = _business_from_node(b_node)
                    bid = b.get("process_id")
                    if bid is not None and bid not in businesses:
                        businesses[bid] = b
                if s_node is not None:
                    s = _step_from_node(s_node)
                    sid = s.get("step_id")
                    if sid is not None and sid not in steps:
                        steps[sid] = s
                if i_node is not None:
                    impl = _implementation_from_node(i_node)
                    iid = impl.get("impl_id")
                    if iid is not None and iid not in implementations:
                        implementations[iid] = impl
                if i_node is not None and ar is not None:
                    impl_resource_links.append(
                        {
                            "process_id": ar.get("process_id"),
                            "impl_id": i_node.get("impl_id"),
                            "resource_id": resource_id,
                            "access_type": ar.get("access_type"),
                            "access_pattern": ar.get("access_pattern"),
                        }
                    )

            logger.info(
                f"[图查询] 获取数据资源上下文完成 resource_id={resource_id}, businesses={len(businesses)}, steps={len(steps)}, implementations={len(implementations)}, links={len(impl_resource_links)}"
            )

            return {
                "resource": resource,
                "businesses": list(businesses.values()),
                "steps": list(steps.values()),
                "implementations": list(implementations.values()),
                "impl_resource_links": impl_resource_links,
            }
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(
            f"[图查询] 获取数据资源上下文 Neo4j 错误 resource_id={resource_id}, error={e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[图查询] 获取数据资源上下文未知异常 resource_id={resource_id}, error={e}",
            exc_info=True,
        )
        raise
    finally:
        driver.close()


def get_implementation_context(impl_id: str) -> Dict[str, Any]:
    """获取指定实现的业务使用情况、资源依赖及实现间调用关系。"""

    logger.info(f"[图查询] 获取实现上下文 impl_id={impl_id}")
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            impl_record = (
                session.run(
                    "MATCH (i:Implementation {impl_id: $iid}) RETURN i",
                    iid=impl_id,
                ).single()
            )
            if not impl_record:
                msg = f"实现不存在: {impl_id}"
                logger.warning(f"[图查询] {msg}")
                raise ValueError(msg)
            i_node = impl_record["i"]
            implementation = _implementation_from_node(i_node)

            rows = session.run(
                """
                MATCH (s:Step)-[ex:EXECUTED_BY]->(i:Implementation {impl_id: $iid})
                MATCH (b:Business {process_id: ex.process_id})
                RETURN b, s, ex
                ORDER BY b.name, s.name
                """,
                iid=impl_id,
            )

            process_usages: List[Dict[str, Any]] = []
            for row in rows:
                b_node = row["b"]
                s_node = row["s"]
                process_usages.append(
                    {
                        "process": _business_from_node(b_node),
                        "step": _step_from_node(s_node),
                    }
                )

            res_rows = session.run(
                """
                MATCH (i:Implementation {impl_id: $iid})-[ar:ACCESSES_RESOURCE]->(d:DataResource)
                RETURN d, ar
                ORDER BY d.name
                """,
                iid=impl_id,
            )
            resources: List[Dict[str, Any]] = []
            for row in res_rows:
                d_node = row["d"]
                ar = row["ar"]
                dr = _data_resource_from_node(d_node)
                dr["access_type"] = ar.get("access_type")
                dr["access_pattern"] = ar.get("access_pattern")
                dr["process_id"] = ar.get("process_id")
                resources.append(dr)

            outgoing_rows = session.run(
                """
                MATCH (i:Implementation {impl_id: $iid})-[r:IMPL_CALL]->(to:Implementation)
                RETURN to, r
                """,
                iid=impl_id,
            )
            outgoing: List[Dict[str, Any]] = []
            for row in outgoing_rows:
                to_node = row["to"]
                r = row["r"]
                outgoing.append(
                    {
                        "to": _implementation_from_node(to_node),
                        "edge_type": r.get("edge_type"),
                        "condition": r.get("condition"),
                        "label": r.get("label"),
                        "process_id": r.get("process_id"),
                    }
                )

            incoming_rows = session.run(
                """
                MATCH (from:Implementation)-[r:IMPL_CALL]->(i:Implementation {impl_id: $iid})
                RETURN from, r
                """,
                iid=impl_id,
            )
            incoming: List[Dict[str, Any]] = []
            for row in incoming_rows:
                from_node = row["from"]
                r = row["r"]
                incoming.append(
                    {
                        "from": _implementation_from_node(from_node),
                        "edge_type": r.get("edge_type"),
                        "condition": r.get("condition"),
                        "label": r.get("label"),
                        "process_id": r.get("process_id"),
                    }
                )

            logger.info(
                f"[图查询] 获取实现上下文完成 impl_id={impl_id}, process_usages={len(process_usages)}, resources={len(resources)}, outgoing_calls={len(outgoing)}, incoming_calls={len(incoming)}"
            )

            return {
                "implementation": implementation,
                "process_usages": process_usages,
                "resources": resources,
                "calls": {
                    "outgoing": outgoing,
                    "incoming": incoming,
                },
            }
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(
            f"[图查询] 获取实现上下文 Neo4j 错误 impl_id={impl_id}, error={e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[图查询] 获取实现上下文未知异常 impl_id={impl_id}, error={e}",
            exc_info=True,
        )
        raise
    finally:
        driver.close()


def get_system_usages(system: str) -> Dict[str, Any]:
    """查询指定系统在业务流程图中的使用情况。"""

    logger.info(f"[图查询] 查询系统使用情况 system={system}")
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            rows = session.run(
                """
                MATCH (i:Implementation {system: $system})
                OPTIONAL MATCH (s:Step)-[ex:EXECUTED_BY]->(i)
                OPTIONAL MATCH (b:Business {process_id: ex.process_id})
                OPTIONAL MATCH (i)-[ar:ACCESSES_RESOURCE]->(d:DataResource)
                RETURN i, s, b, collect(DISTINCT d) AS resources
                """,
                system=system,
            )

            usages: List[Dict[str, Any]] = []
            for row in rows:
                i_node = row["i"]
                s_node = row["s"]
                b_node = row["b"]
                res_nodes = row["resources"] or []
                usages.append(
                    {
                        "implementation": _implementation_from_node(i_node),
                        "step": _step_from_node(s_node) if s_node is not None else None,
                        "process": _business_from_node(b_node) if b_node is not None else None,
                        "resources": [
                            _data_resource_from_node(n) for n in res_nodes
                        ],
                    }
                )

            logger.info(
                f"[图查询] 查询系统使用情况完成 system={system}, usages={len(usages)}"
            )
            return {"system": system, "usages": usages}
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(
            f"[图查询] 查询系统使用情况 Neo4j 错误 system={system}, error={e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[图查询] 查询系统使用情况未知异常 system={system}, error={e}",
            exc_info=True,
        )
        raise
    finally:
        driver.close()


def get_neighborhood(
    start_nodes: Sequence[Dict[str, str]],
    depth: int = 1,
    relationship_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """从若干起点节点出发，查询限定深度与关系类型的邻域子图。"""

    if not start_nodes:
        raise ValueError("start_nodes 参数不能为空")
    if depth < 1:
        raise ValueError("depth 必须 >= 1")

    rel_types = list(relationship_types) if relationship_types else list(_GRAPH_REL_TYPES)
    invalid = [t for t in rel_types if t not in _GRAPH_REL_TYPES]
    if invalid:
        raise ValueError(f"不支持的关系类型: {invalid}")

    business_ids: List[str] = []
    step_ids: List[str] = []
    impl_ids: List[str] = []
    resource_ids: List[str] = []
    for ref in start_nodes:
        t = ref.get("type")
        i = ref.get("id")
        if not i:
            continue
        if t == "business":
            business_ids.append(i)
        elif t == "step":
            step_ids.append(i)
        elif t == "implementation":
            impl_ids.append(i)
        elif t == "resource":
            resource_ids.append(i)

    if not any([business_ids, step_ids, impl_ids, resource_ids]):
        raise ValueError("没有提供有效的起点节点 ID")

    depth_clause = f"*1..{int(depth)}"

    where_clause = " OR ".join(
        [
            "(size($business_ids) > 0 AND start:Business AND start.process_id IN $business_ids)",
            "(size($step_ids) > 0 AND start:Step AND start.step_id IN $step_ids)",
            "(size($impl_ids) > 0 AND start:Implementation AND start.impl_id IN $impl_ids)",
            "(size($resource_ids) > 0 AND start:DataResource AND start.resource_id IN $resource_ids)",
        ]
    )

    query = f"""
    MATCH (start)
    WHERE {where_clause}
    MATCH p=(start)-[rel{depth_clause}]-(n)
    WHERE all(r IN rel WHERE type(r) IN $rel_types)
    WITH collect(p) AS paths
    UNWIND paths AS p
    UNWIND nodes(p) AS n
    WITH collect(DISTINCT n) AS nodes, paths
    UNWIND paths AS p2
    UNWIND relationships(p2) AS r
    WITH nodes, collect(DISTINCT r) AS rels
    RETURN [n IN nodes | {{id: id(n), labels: labels(n), properties: properties(n)}}] AS nodes,
           [r IN rels  | {{id: id(r), type: type(r), start_id: id(startNode(r)), end_id: id(endNode(r)), properties: properties(r)}}] AS relationships
    """

    logger.info(
        f"[图查询] 查询图邻域 start_nodes={len(start_nodes)}, depth={depth}, rel_types={rel_types}"
    )
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            record = session.run(
                query,
                business_ids=business_ids,
                step_ids=step_ids,
                impl_ids=impl_ids,
                resource_ids=resource_ids,
                rel_types=rel_types,
            ).single()
            if not record:
                logger.info("[图查询] 查询图邻域结果为空")
                return {"nodes": [], "relationships": []}
            nodes = record["nodes"]
            relationships = record["relationships"]
            logger.info(
                f"[图查询] 查询图邻域完成 nodes={len(nodes)}, relationships={len(relationships)}"
            )
            return {
                "nodes": nodes,
                "relationships": relationships,
            }
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(f"[图查询] 查询图邻域 Neo4j 错误 error={e}")
        raise
    except Exception as e:
        logger.error(f"[图查询] 查询图邻域未知异常 error={e}", exc_info=True)
        raise
    finally:
        driver.close()


def find_path(
    start: Dict[str, str],
    end: Dict[str, str],
    max_depth: int = 5,
    relationship_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """在图中查找两个节点之间的最短路径。"""

    if max_depth < 1:
        raise ValueError("max_depth 必须 >= 1")

    rel_types = list(relationship_types) if relationship_types else list(_GRAPH_REL_TYPES)
    invalid = [t for t in rel_types if t not in _GRAPH_REL_TYPES]
    if invalid:
        raise ValueError(f"不支持的关系类型: {invalid}")

    start_type = start.get("type")
    start_id = start.get("id")
    end_type = end.get("type")
    end_id = end.get("id")
    if not start_type or not start_id or not end_type or not end_id:
        raise ValueError("start 和 end 必须包含 type 和 id 字段")

    def _single_where(var: str, node_type: str, param_name: str) -> str:
        if node_type == "business":
            return f"{var}:Business AND {var}.process_id = ${param_name}"
        if node_type == "step":
            return f"{var}:Step AND {var}.step_id = ${param_name}"
        if node_type == "implementation":
            return f"{var}:Implementation AND {var}.impl_id = ${param_name}"
        if node_type == "resource":
            return f"{var}:DataResource AND {var}.resource_id = ${param_name}"
        raise ValueError(f"Unsupported node type: {node_type}")

    start_where = _single_where("start", start_type, "start_id")
    end_where = _single_where("end", end_type, "end_id")
    depth_clause = f"1..{int(max_depth)}"

    query = f"""
    MATCH (start), (end)
    WHERE {start_where}
      AND {end_where}
    MATCH p=shortestPath((start)-[*{depth_clause}]-(end))
    WHERE all(r IN relationships(p) WHERE type(r) IN $rel_types)
    RETURN [n IN nodes(p) | {{id: id(n), labels: labels(n), properties: properties(n)}}] AS nodes,
           [r IN relationships(p) | {{id: id(r), type: type(r), start_id: id(startNode(r)), end_id: id(endNode(r)), properties: properties(r)}}] AS relationships
    LIMIT 1
    """

    logger.info(
        f"[图查询] 查询最短路径 start={start}, end={end}, max_depth={max_depth}, rel_types={rel_types}"
    )
    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            record = session.run(
                query,
                start_id=start_id,
                end_id=end_id,
                rel_types=rel_types,
            ).single()
            if not record:
                logger.info("[图查询] 查询最短路径结果为空")
                return {"nodes": [], "relationships": []}
            nodes = record["nodes"]
            relationships = record["relationships"]
            logger.info(
                f"[图查询] 查询最短路径完成 nodes={len(nodes)}, relationships={len(relationships)}"
            )
            return {
                "nodes": nodes,
                "relationships": relationships,
            }
    except (ServiceUnavailable, AuthError, ClientError) as e:
        logger.error(f"[图查询] 查询最短路径 Neo4j 错误 error={e}")
        raise
    except Exception as e:
        logger.error(f"[图查询] 查询最短路径未知异常 error={e}", exc_info=True)
        raise
    finally:
        driver.close()
