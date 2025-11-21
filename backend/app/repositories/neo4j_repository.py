"""Neo4j 数据访问层 - 负责所有 Neo4j 图数据库操作"""

from typing import List, Dict, Any, Set
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
from backend.app.db.neo4j_client import get_neo4j_driver, DEFAULT_NEO4J_DATABASE


class Neo4jRepository:
    """Neo4j 图数据库仓储类，封装所有 Neo4j 数据访问操作"""

    def __init__(self):
        self.driver = get_neo4j_driver()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.close()

    def _create_constraints(self, session) -> None:
        """创建唯一性约束"""
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (b:Business) REQUIRE b.process_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Step) REQUIRE s.step_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Implementation) REQUIRE i.impl_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:DataResource) REQUIRE r.resource_id IS UNIQUE")

    def clear_process_graph(self, process_id: str) -> None:
        """清除流程相关的图数据"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            # 删除该流程的所有边（按process_id过滤）
            session.run(
                """
                MATCH ()-[r {process_id: $pid}]->()
                DELETE r
                """,
                pid=process_id,
            )
            
            # 删除Business节点的START_AT关系（这个关系没有process_id）
            session.run(
                """
                MATCH (b:Business {process_id: $pid})-[r:START_AT]->()
                DELETE r
                """,
                pid=process_id,
            )
            
            # 删除Business节点
            session.run(
                "MATCH (b:Business {process_id: $pid}) DELETE b",
                pid=process_id,
            )

    def clear_step_implementation_relations(self, process_id: str, step_ids: List[str]) -> None:
        """清除步骤-实现关系（按process_id过滤）"""
        if not step_ids:
            return
        
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (s:Step)-[r:EXECUTED_BY {process_id: $process_id}]->(i:Implementation)
                WHERE s.step_id IN $step_ids
                DELETE r
                """,
                process_id=process_id,
                step_ids=step_ids,
            )

    def clear_implementation_resource_relations(self, process_id: str, impl_ids: List[str]) -> None:
        """清除实现-数据资源关系（按process_id过滤）"""
        if not impl_ids:
            return
        
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (i:Implementation)-[r:ACCESSES_RESOURCE {process_id: $process_id}]->(d:DataResource)
                WHERE i.impl_id IN $impl_ids
                DELETE r
                """,
                process_id=process_id,
                impl_ids=impl_ids,
            )

    def create_or_update_business_node(
        self,
        process_id: str,
        name: str,
        channel: str,
        description: str,
        entrypoints: str,
    ) -> None:
        """创建或更新业务流程节点"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            self._create_constraints(session)
            session.run(
                """
                MERGE (b:Business {process_id: $process_id})
                SET b.name = $name,
                    b.channel = $channel,
                    b.description = $description,
                    b.entrypoints = $entrypoints
                """,
                process_id=process_id,
                name=name,
                channel=channel,
                description=description,
                entrypoints=entrypoints,
            )

    def create_or_update_step_node(
        self,
        step_id: str,
        name: str,
        description: str,
        step_type: str,
    ) -> None:
        """创建或更新步骤节点"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (s:Step {step_id: $step_id})
                SET s.name = $name,
                    s.description = $description,
                    s.step_type = $step_type
                """,
                step_id=step_id,
                name=name,
                description=description,
                step_type=step_type,
            )

    def create_or_update_implementation_node(
        self,
        impl_id: str,
        name: str,
        type_: str,
        system: str,
        description: str,
        code_ref: str,
    ) -> None:
        """创建或更新实现节点"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (i:Implementation {impl_id: $impl_id})
                SET i.name = $name,
                    i.type = $type,
                    i.system = $system,
                    i.description = $description,
                    i.code_ref = $code_ref
                """,
                impl_id=impl_id,
                name=name,
                type=type_,
                system=system,
                description=description,
                code_ref=code_ref,
            )

    def create_or_update_data_resource_node(
        self,
        resource_id: str,
        name: str,
        type_: str,
        system: str,
        description: str,
    ) -> None:
        """创建或更新数据资源节点"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (r:DataResource {resource_id: $resource_id})
                SET r.name = $name,
                    r.type = $type,
                    r.system = $system,
                    r.description = $description
                """,
                resource_id=resource_id,
                name=name,
                type=type_,
                system=system,
                description=description,
            )

    def create_business_start_relation(self, process_id: str, step_id: str) -> None:
        """创建业务流程起始关系"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (b:Business {process_id: $process_id})
                MATCH (s:Step {step_id: $step_id})
                MERGE (b)-[:START_AT]->(s)
                """,
                process_id=process_id,
                step_id=step_id,
            )

    def create_step_next_relation(
        self,
        from_step_id: str,
        to_step_id: str,
        process_id: str,
        edge_type: str,
        condition: str,
        label: str,
    ) -> None:
        """创建步骤之间的 NEXT 关系"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (from:Step {step_id: $from_step_id})
                MATCH (to:Step {step_id: $to_step_id})
                CREATE (from)-[r:NEXT {
                    process_id: $process_id,
                    edge_type: $edge_type,
                    condition: $condition,
                    label: $label
                }]->(to)
                """,
                from_step_id=from_step_id,
                to_step_id=to_step_id,
                process_id=process_id,
                edge_type=edge_type,
                condition=condition,
                label=label,
            )

    def create_step_implementation_relation(self, process_id: str, step_id: str, impl_id: str) -> None:
        """创建步骤-实现关系"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (s:Step {step_id: $step_id})
                MATCH (i:Implementation {impl_id: $impl_id})
                CREATE (s)-[r:EXECUTED_BY {process_id: $process_id}]->(i)
                """,
                process_id=process_id,
                step_id=step_id,
                impl_id=impl_id,
            )

    def create_implementation_resource_relation(
        self,
        process_id: str,
        impl_id: str,
        resource_id: str,
        access_type: str,
        access_pattern: str,
    ) -> None:
        """创建实现-数据资源关系"""
        with self.driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (i:Implementation {impl_id: $impl_id})
                MATCH (r:DataResource {resource_id: $resource_id})
                CREATE (i)-[rel:ACCESSES_RESOURCE {
                    process_id: $process_id,
                    access_type: $access_type,
                    access_pattern: $access_pattern
                }]->(r)
                """,
                process_id=process_id,
                impl_id=impl_id,
                resource_id=resource_id,
                access_type=access_type,
                access_pattern=access_pattern,
            )

    def close(self) -> None:
        """关闭驱动连接"""
        if self.driver:
            self.driver.close()
