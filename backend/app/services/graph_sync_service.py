from typing import Any, Dict, List, Set, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from neo4j.exceptions import ServiceUnavailable, AuthError, ClientError

from backend.app.db.neo4j_client import (
    DEFAULT_NEO4J_DATABASE,
    get_neo4j_driver,
)
from backend.app.models.resource_graph import (
    Business,
    DataResource,
    Implementation,
    ImplementationDataResource,
    ProcessStepEdge,
    Step,
    StepImplementation,
)
from backend.app.core.logger import logger


class SyncError(Exception):
    """同步过程中的自定义异常"""
    def __init__(self, message: str, error_type: str = "unknown"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


def _create_constraints(session: Any) -> None:
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Business) REQUIRE b.process_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Step) REQUIRE s.step_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (r:DataResource) REQUIRE r.resource_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Implementation) REQUIRE i.impl_id IS UNIQUE"
    )


def sync_process(db: Session, process_id: str) -> Dict[str, Any]:
    """同步流程到Neo4j，返回同步结果
    
    Returns:
        Dict包含: success (bool), message (str), error_type (str), synced_at (datetime)
    """
    logger.info(f"[同步开始] process_id={process_id}")
    
    process = (
        db.query(Business)
        .filter(Business.process_id == process_id)
        .first()
    )
    if not process:
        error_msg = f"流程不存在: {process_id}"
        logger.error(f"[同步失败] {error_msg}")
        raise ValueError(error_msg)
    
    # 更新状态为同步中
    process.sync_status = "syncing"
    process.sync_error = None
    db.commit()
    logger.info(f"[同步中] process_id={process_id}, status=syncing")

    # 从 canvas_node_ids 读取节点ID列表
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
        except json.JSONDecodeError:
            logger.warning(f"[同步警告] 无法解析canvas_node_ids字段 process_id={process_id}")

    # 获取流程边
    edges: List[ProcessStepEdge] = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .all()
    )

    # 获取步骤信息
    steps_db: List[Step] = []
    if step_ids:
        steps_db = (
            db.query(Step)
            .filter(Step.step_id.in_(step_ids))
            .all()
        )
    step_by_id: Dict[str, Step] = {s.step_id: s for s in steps_db}

    # 获取实现信息
    impl_by_id: Dict[str, Implementation] = {}
    if impl_ids:
        impls_db = (
            db.query(Implementation)
            .filter(Implementation.impl_id.in_(impl_ids))
            .all()
        )
        impl_by_id = {impl.impl_id: impl for impl in impls_db}

    # 获取步骤-实现关联（限定process_id）
    impl_rows: List[StepImplementation] = []
    if step_ids:
        impl_rows = (
            db.query(StepImplementation)
            .filter(
                StepImplementation.process_id == process_id,
                StepImplementation.step_id.in_(step_ids)
            )
            .all()
        )

    step_impl_map: Dict[str, List[str]] = {}
    for link in impl_rows:
        step_impl_map.setdefault(link.step_id, []).append(link.impl_id)

    # 获取数据资源信息
    dr_by_id: Dict[str, DataResource] = {}
    if resource_ids:
        drs_db = (
            db.query(DataResource)
            .filter(DataResource.resource_id.in_(resource_ids))
            .all()
        )
        dr_by_id = {dr.resource_id: dr for dr in drs_db}

    # 获取实现-数据资源关联（限定process_id）
    da_rows: List[ImplementationDataResource] = []
    if impl_ids:
        da_rows = (
            db.query(ImplementationDataResource)
            .filter(
                ImplementationDataResource.process_id == process_id,
                ImplementationDataResource.impl_id.in_(impl_ids)
            )
            .all()
        )

    data_by_impl: Dict[str, List[ImplementationDataResource]] = {}
    for link in da_rows:
        data_by_impl.setdefault(link.impl_id, []).append(link)

    # 尝试连接Neo4j并同步
    driver = None
    try:
        logger.info(f"[Neo4j连接] 正在连接到Neo4j数据库...")
        driver = get_neo4j_driver()
        
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            logger.info(f"[Neo4j连接] 连接成功, database={DEFAULT_NEO4J_DATABASE}")
            _create_constraints(session)

            # 删除该流程的所有边（按process_id过滤）
            session.run(
                """
                MATCH ()-[r {process_id: $pid}]->()
                DELETE r
                """,
                pid=process_id,
            )
            logger.info(f"[同步-删除边] 删除流程{process_id}的所有旧边完成")

            # 删除Business节点的START_AT关系（这个关系没有process_id）
            session.run(
                """
                MATCH (b:Business {process_id: $pid})-[r:START_AT]->()
                DELETE r
                """,
                pid=process_id,
            )
            logger.info(f"[同步-删除边] 删除START_AT关系完成")

            # 删除Business节点
            session.run(
                "MATCH (b:Business {process_id: $pid}) DELETE b",
                pid=process_id,
            )
            logger.info(f"[同步-删除节点] 删除Business节点完成")

            # ========== 创建节点阶段（批量优化）==========
            logger.info(f"[同步-创建节点] 开始批量创建节点...")
            
            # 1. 创建Business节点（单个）
            session.run(
                """
                MERGE (b:Business {process_id: $process_id})
                SET b.name = $name,
                    b.channel = $channel,
                    b.description = $description,
                    b.entrypoints = $entrypoints
                """,
                process_id=process.process_id,
                name=process.name,
                channel=process.channel,
                description=process.description,
                entrypoints=process.entrypoints or "",
            )
            logger.info(f"[同步-创建节点] Business节点创建完成")

            # 2. 批量创建Step节点
            if step_ids:
                step_data = [
                    {
                        "step_id": step.step_id,
                        "name": step.name,
                        "description": step.description or "",
                        "step_type": step.step_type or ""
                    }
                    for step in steps_db
                ]
                session.run(
                    """
                    UNWIND $steps AS step
                    MERGE (s:Step {step_id: step.step_id})
                    SET s.name = step.name,
                        s.description = step.description,
                        s.step_type = step.step_type
                    """,
                    steps=step_data
                )
                logger.info(f"[同步-创建节点] 批量创建{len(step_data)}个Step节点完成")

            # 3. 批量创建DataResource节点
            if dr_by_id:
                resource_data = [
                    {
                        "resource_id": dr.resource_id,
                        "name": dr.name,
                        "type": dr.type or "",
                        "system": dr.system or "",
                        "description": dr.description or ""
                    }
                    for dr in dr_by_id.values()
                ]
                session.run(
                    """
                    UNWIND $resources AS res
                    MERGE (r:DataResource {resource_id: res.resource_id})
                    SET r.name = res.name,
                        r.type = res.type,
                        r.system = res.system,
                        r.description = res.description
                    """,
                    resources=resource_data
                )
                logger.info(f"[同步-创建节点] 批量创建{len(resource_data)}个DataResource节点完成")

            # 4. 批量创建Implementation节点
            if impl_by_id:
                impl_data = [
                    {
                        "impl_id": impl.impl_id,
                        "name": impl.name,
                        "type": impl.type or "",
                        "system": impl.system or "",
                        "description": impl.description or "",
                        "code_ref": impl.code_ref or ""
                    }
                    for impl in impl_by_id.values()
                ]
                session.run(
                    """
                    UNWIND $impls AS impl
                    MERGE (i:Implementation {impl_id: impl.impl_id})
                    SET i.name = impl.name,
                        i.type = impl.type,
                        i.system = impl.system,
                        i.description = impl.description,
                        i.code_ref = impl.code_ref
                    """,
                    impls=impl_data
                )
                logger.info(f"[同步-创建节点] 批量创建{len(impl_data)}个Implementation节点完成")

            # ========== 创建关系阶段（批量优化）==========
            logger.info(f"[同步-创建关系] 开始批量创建关系...")
            
            # 5. 批量创建START_AT关系（拓扑排序找起始步骤）
            indegree: Dict[str, int] = {sid: 0 for sid in step_ids}
            for e in edges:
                if e.from_step_id in indegree and e.to_step_id in indegree:
                    indegree[e.to_step_id] += 1

            start_step_ids = [sid for sid, deg in indegree.items() if deg == 0]
            if start_step_ids:
                session.run(
                    """
                    UNWIND $start_steps AS step_id
                    MATCH (b:Business {process_id: $process_id})
                    MATCH (s:Step {step_id: step_id})
                    MERGE (b)-[:START_AT]->(s)
                    """,
                    start_steps=start_step_ids,
                    process_id=process_id,
                )
                logger.info(f"[同步-创建关系] 批量创建{len(start_step_ids)}个START_AT关系完成")

            # 6. 批量创建NEXT关系（步骤顺序连线）
            if edges:
                edge_data = [
                    {
                        "from_step_id": e.from_step_id,
                        "to_step_id": e.to_step_id,
                        "process_id": process_id,
                        "edge_type": e.edge_type or "",
                        "condition": e.condition or "",
                        "label": e.label or ""
                    }
                    for e in edges
                ]
                session.run(
                    """
                    UNWIND $edges AS edge
                    MATCH (from:Step {step_id: edge.from_step_id})
                    MATCH (to:Step {step_id: edge.to_step_id})
                    CREATE (from)-[r:NEXT {
                        process_id: edge.process_id,
                        edge_type: edge.edge_type,
                        condition: edge.condition,
                        label: edge.label
                    }]->(to)
                    """,
                    edges=edge_data
                )
                logger.info(f"[同步-创建关系] 批量创建{len(edge_data)}个NEXT关系完成")

            # 7. 批量创建EXECUTED_BY关系（步骤-实现关系）
            step_impl_links = []
            for step_id, impl_list in step_impl_map.items():
                for impl_id in impl_list:
                    step_impl_links.append({
                        "step_id": step_id,
                        "impl_id": impl_id
                    })
            
            if step_impl_links:
                session.run(
                    """
                    UNWIND $links AS link
                    MATCH (s:Step {step_id: link.step_id})
                    MATCH (i:Implementation {impl_id: link.impl_id})
                    CREATE (s)-[r:EXECUTED_BY {process_id: $process_id}]->(i)
                    """,
                    links=step_impl_links,
                    process_id=process_id
                )
                logger.info(f"[同步-创建关系] 批量创建{len(step_impl_links)}个EXECUTED_BY关系完成")

            # 8. 批量创建ACCESSES_RESOURCE关系（实现-数据资源关系）
            access_links = []
            for impl_id, items in data_by_impl.items():
                for link in items:
                    access_links.append({
                        "impl_id": impl_id,
                        "resource_id": link.resource_id,
                        "access_type": link.access_type or "",
                        "access_pattern": link.access_pattern or ""
                    })
            
            if access_links:
                session.run(
                    """
                    UNWIND $links AS link
                    MATCH (i:Implementation {impl_id: link.impl_id})
                    MATCH (r:DataResource {resource_id: link.resource_id})
                    CREATE (i)-[rel:ACCESSES_RESOURCE {
                        process_id: $process_id,
                        access_type: link.access_type,
                        access_pattern: link.access_pattern
                    }]->(r)
                    """,
                    links=access_links,
                    process_id=process_id
                )
                logger.info(f"[同步-创建关系] 批量创建{len(access_links)}个ACCESSES_RESOURCE关系完成")
            
            # 同步成功
            logger.info(f"[同步成功] process_id={process_id}, steps={len(step_ids)}, implementations={len(impl_ids)}, resources={len(dr_by_id)}, edges={len(edges)}")

            # 更新同步状态
            process.sync_status = "synced"
            process.last_sync_at = datetime.now()
            process.sync_error = None
            db.commit()
            
            return {
                "success": True,
                "message": "同步成功",
                "synced_at": process.last_sync_at.isoformat(),
                "stats": {
                    "steps": len(step_ids),
                    "implementations": len(impl_ids),
                    "data_resources": len(dr_by_id)
                }
            }
            
    except ServiceUnavailable as e:
        error_msg = f"Neo4j服务不可用: {str(e)}"
        error_type = "connection_error"
        logger.error(f"[同步失败] {error_msg}")
        
        process.sync_status = "failed"
        process.sync_error = error_msg
        db.commit()
        
        raise SyncError(error_msg, error_type)
        
    except AuthError as e:
        error_msg = f"Neo4j认证失败: {str(e)}"
        error_type = "auth_error"
        logger.error(f"[同步失败] {error_msg}")
        
        process.sync_status = "failed"
        process.sync_error = error_msg
        db.commit()
        
        raise SyncError(error_msg, error_type)
        
    except ClientError as e:
        error_msg = f"Neo4j查询错误: {str(e)}"
        error_type = "query_error"
        logger.error(f"[同步失败] {error_msg}")
        
        process.sync_status = "failed"
        process.sync_error = error_msg
        db.commit()
        
        raise SyncError(error_msg, error_type)
        
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        error_type = "unknown_error"
        logger.error(f"[同步失败] {error_msg}", exc_info=True)
        
        process.sync_status = "failed"
        process.sync_error = error_msg
        db.commit()
        
        raise SyncError(error_msg, error_type)
        
    finally:
        if driver:
            driver.close()
            logger.info(f"[Neo4j连接] 连接已关闭")


def check_neo4j_health() -> Dict[str, Any]:
    """检查Neo4j连接健康状态
    
    Returns:
        Dict包含: connected (bool), message (str), database (str), error (str)
    """
    driver = None
    try:
        logger.info("[健康检查] 正在检查Neo4j连接...")
        driver = get_neo4j_driver()
        
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            # 执行简单查询测试连接
            result = session.run("RETURN 1 AS test")
            result.single()
            
        logger.info("[健康检查] Neo4j连接正常")
        return {
            "connected": True,
            "message": "Neo4j连接正常",
            "database": DEFAULT_NEO4J_DATABASE,
            "error": None
        }
        
    except ServiceUnavailable as e:
        error_msg = f"Neo4j服务不可用: {str(e)}"
        logger.error(f"[健康检查] {error_msg}")
        return {
            "connected": False,
            "message": "Neo4j服务不可用",
            "database": DEFAULT_NEO4J_DATABASE,
            "error": error_msg
        }
        
    except AuthError as e:
        error_msg = f"Neo4j认证失败: {str(e)}"
        logger.error(f"[健康检查] {error_msg}")
        return {
            "connected": False,
            "message": "Neo4j认证失败",
            "database": DEFAULT_NEO4J_DATABASE,
            "error": error_msg
        }
        
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        logger.error(f"[健康检查] {error_msg}")
        return {
            "connected": False,
            "message": "连接检查失败",
            "database": DEFAULT_NEO4J_DATABASE,
            "error": error_msg
        }
        
    finally:
        if driver:
            driver.close()
