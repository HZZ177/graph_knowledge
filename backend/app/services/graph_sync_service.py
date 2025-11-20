from typing import Any, Dict, List, Set, Tuple

from sqlalchemy.orm import Session

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


def sync_process(db: Session, process_id: str) -> None:
    process = (
        db.query(Business)
        .filter(Business.process_id == process_id)
        .first()
    )
    if not process:
        raise ValueError(f"Unknown process_id: {process_id}")

    edges: List[ProcessStepEdge] = (
        db.query(ProcessStepEdge)
        .filter(ProcessStepEdge.process_id == process_id)
        .all()
    )

    step_ids: Set[str] = set()
    for e in edges:
        step_ids.add(e.from_step_id)
        step_ids.add(e.to_step_id)

    steps_db: List[Step] = []
    if step_ids:
        steps_db = (
            db.query(Step)
            .filter(Step.step_id.in_(step_ids))
            .all()
        )
    step_by_id: Dict[str, Step] = {s.step_id: s for s in steps_db}

    impl_rows: List[Tuple[StepImplementation, Implementation]] = []
    if step_ids:
        impl_rows = (
            db.query(StepImplementation, Implementation)
            .join(Implementation, StepImplementation.impl_id == Implementation.impl_id)
            .filter(StepImplementation.step_id.in_(step_ids))
            .all()
        )

    impl_ids: Set[str] = set()
    impl_by_id: Dict[str, Implementation] = {}
    step_impl_map: Dict[str, List[str]] = {}
    for link, impl in impl_rows:
        impl_ids.add(impl.impl_id)
        impl_by_id[impl.impl_id] = impl
        step_impl_map.setdefault(link.step_id, []).append(impl.impl_id)

    da_rows: List[Tuple[ImplementationDataResource, DataResource]] = []
    if impl_ids:
        da_rows = (
            db.query(ImplementationDataResource, DataResource)
            .join(
                DataResource,
                ImplementationDataResource.resource_id == DataResource.resource_id,
            )
            .filter(ImplementationDataResource.impl_id.in_(impl_ids))
            .all()
        )

    data_by_impl: Dict[str, List[Tuple[ImplementationDataResource, DataResource]]] = {}
    dr_by_id: Dict[str, DataResource] = {}
    for link, dr in da_rows:
        dr_by_id[dr.resource_id] = dr
        data_by_impl.setdefault(link.impl_id, []).append((link, dr))

    driver = get_neo4j_driver()
    try:
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            _create_constraints(session)

            session.run(
                "MATCH (b:Business {process_id: $pid}) DETACH DELETE b",
                pid=process_id,
            )

            session.run(
                """
                MATCH (:Step)-[r:NEXT {process_id: $pid}]->(:Step)
                DELETE r
                """,
                pid=process_id,
            )

            if step_ids:
                session.run(
                    """
                    MATCH (s:Step)-[r:EXECUTED_BY]->(i:Implementation)
                    WHERE s.step_id IN $step_ids
                    DELETE r
                    """,
                    step_ids=list(step_ids),
                )

            if impl_ids:
                session.run(
                    """
                    MATCH (i:Implementation)-[r:ACCESSES_RESOURCE]->(d:DataResource)
                    WHERE i.impl_id IN $impl_ids
                    DELETE r
                    """,
                    impl_ids=list(impl_ids),
                )

            entrypoints: List[str] = []
            if process.entrypoints:
                entrypoints = [
                    item
                    for item in process.entrypoints.split(",")
                    if item
                ]

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
                entrypoints=entrypoints,
            )

            for sid in step_ids:
                step = step_by_id.get(sid)
                if not step:
                    continue
                session.run(
                    """
                    MERGE (s:Step {step_id: $step_id})
                    SET s.name = $name,
                        s.description = $description,
                        s.step_type = $step_type
                    """,
                    step_id=step.step_id,
                    name=step.name,
                    description=step.description,
                    step_type=step.step_type,
                )

            for dr in dr_by_id.values():
                session.run(
                    """
                    MERGE (r:DataResource {resource_id: $resource_id})
                    SET r.name = $name,
                        r.type = $type,
                        r.system = $system,
                        r.description = $description
                    """,
                    resource_id=dr.resource_id,
                    name=dr.name,
                    type=dr.type,
                    system=dr.system,
                    description=dr.description,
                )

            for impl in impl_by_id.values():
                session.run(
                    """
                    MERGE (i:Implementation {impl_id: $impl_id})
                    SET i.name = $name,
                        i.type = $type,
                        i.system = $system,
                        i.description = $description,
                        i.code_ref = $code_ref
                    """,
                    impl_id=impl.impl_id,
                    name=impl.name,
                    type=impl.type,
                    system=impl.system,
                    description=impl.description,
                    code_ref=impl.code_ref,
                )

            indegree: Dict[str, int] = {sid: 0 for sid in step_ids}
            for e in edges:
                if e.from_step_id in indegree and e.to_step_id in indegree:
                    indegree[e.to_step_id] += 1

            start_step_ids = [sid for sid, deg in indegree.items() if deg == 0]
            for sid in start_step_ids:
                session.run(
                    """
                    MATCH (b:Business {process_id: $process_id})
                    MATCH (s:Step {step_id: $step_id})
                    MERGE (b)-[:START_AT]->(s)
                    """,
                    process_id=process_id,
                    step_id=sid,
                )

            for e in edges:
                session.run(
                    """
                    MATCH (from:Step {step_id: $from_step_id})
                    MATCH (to:Step {step_id: $to_step_id})
                    MERGE (from)-[r:NEXT {process_id: $process_id}]->(to)
                    SET r.edge_type = $edge_type,
                        r.condition = $condition,
                        r.label = $label
                    """,
                    from_step_id=e.from_step_id,
                    to_step_id=e.to_step_id,
                    process_id=process_id,
                    edge_type=e.edge_type,
                    condition=e.condition,
                    label=e.label,
                )

            for step_id, impl_list in step_impl_map.items():
                for impl_id in impl_list:
                    session.run(
                        """
                        MATCH (s:Step {step_id: $step_id})
                        MATCH (i:Implementation {impl_id: $impl_id})
                        MERGE (s)-[:EXECUTED_BY]->(i)
                        """,
                        step_id=step_id,
                        impl_id=impl_id,
                    )

            for impl_id, items in data_by_impl.items():
                for link, dr in items:
                    session.run(
                        """
                        MATCH (i:Implementation {impl_id: $impl_id})
                        MATCH (r:DataResource {resource_id: $resource_id})
                        MERGE (i)-[rel:ACCESSES_RESOURCE]->(r)
                        SET rel.access_type = $access_type,
                            rel.access_pattern = $access_pattern
                        """,
                        impl_id=impl_id,
                        resource_id=dr.resource_id,
                        access_type=link.access_type,
                        access_pattern=link.access_pattern,
                    )
    finally:
        driver.close()
