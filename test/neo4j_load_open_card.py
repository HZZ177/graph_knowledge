"""示例脚本：将一个最小化的“开通月卡”业务图写入 Neo4j。

使用方式：
    1. 安装依赖（建议在虚拟环境中）：

        pip install neo4j

    2. 通过环境变量配置 Neo4j 连接信息：

        NEO4J_URI=bolt://localhost:7687
        NEO4J_USER=neo4j
        NEO4J_PASSWORD=your_password

       或者直接修改本脚本中的 DEFAULT_* 默认值，便于本地快速测试。

    3. 在项目根目录（`test/` 为子目录）下运行：

        python -m test.neo4j_load_open_card

本脚本刻意保持简单，只创建少量节点标签和关系，
用于演示我们讨论的“C 端开通月卡”业务流程的最小数据集。
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from neo4j import GraphDatabase


# 默认连接配置（可通过环境变量覆盖）
DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "Keytop@123"
DEFAULT_DATABASE = "c-card"


@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str


def get_neo4j_config() -> Neo4jConfig:
    return Neo4jConfig(
        uri=DEFAULT_URI,
        user=DEFAULT_USER,
        password=DEFAULT_PASSWORD,
        database=DEFAULT_DATABASE,
    )


# ---- “C端开通月卡”的最小示例数据集 ----

SAMPLE_DATA: Dict[str, List[Dict[str, Any]]] = {
    "business_processes": [
        {
            "process_id": "c_open_card",
            "name": "C端开通月卡",
            "channel": "app",
            "domain": "membership/month_card",
            "description": "用户在C端App发起开通月卡的操作，从下单、支付到卡生效的完整流程。",
            "entrypoints": "用户在C端App点击开通月卡按钮，进入开卡流程页面",
        }
    ],
    "business_process_steps": [
        {
            "step_id": 1,
            "process_id": "c_open_card",
            "order_no": 10,
            "capability_id": "common/user.verify_identity",
            "name": "校验用户身份与账号状态",
            "branch": "main",
            "role": "system",
            "condition": "用户在App已登录",
        },
        {
            "step_id": 2,
            "process_id": "c_open_card",
            "order_no": 20,
            "capability_id": "membership/month_card/card.check_open_eligibility",
            "name": "校验用户是否具备开卡资格",
            "branch": "main",
            "role": "system",
            "condition": "通过基础身份校验后执行",
        },
        {
            "step_id": 3,
            "process_id": "c_open_card",
            "order_no": 30,
            "capability_id": "membership/month_card/card.open",
            "name": "创建月卡实例与支付订单",
            "branch": "main",
            "role": "system",
            "condition": "资格校验通过",
        },
        {
            "step_id": 4,
            "process_id": "c_open_card",
            "order_no": 40,
            "capability_id": "common/payment.pay_order",
            "name": "发起支付并确认支付结果",
            "branch": "main",
            "role": "system",
            "condition": "创建支付订单成功",
        },
        {
            "step_id": 5,
            "process_id": "c_open_card",
            "order_no": 50,
            "capability_id": "membership/month_card/card.bind_plate",
            "name": "绑定车牌到月卡",
            "branch": "main",
            "role": "system",
            "condition": "用户在前端填写了车牌号",
            "is_optional": True,
        },
    ],
    "business_capabilities": [
        {
            "capability_id": "common/user.verify_identity",
            "domain": "common/user",
            "name": "校验用户身份与账号状态",
            "description": "根据用户登录态、账号状态、风控标签等信息，判断用户是否允许进行开卡类操作。",
            "capability_type": "technical",
        },
        {
            "capability_id": "membership/month_card/card.check_open_eligibility",
            "domain": "membership/month_card",
            "name": "校验用户开通月卡资格",
            "description": "根据用户是否已有同类型有效月卡、是否存在未结清欠费、车场与产品规则等，判断是否允许开通新的月卡。",
            "capability_type": "business",
        },
        {
            "capability_id": "membership/month_card/card.open",
            "domain": "membership/month_card",
            "name": "创建月卡实例与支付订单",
            "description": "为用户创建一条待生效的月卡记录，并生成对应的支付订单，记录产品、价格、车场、有效期等信息。",
            "capability_type": "business",
        },
        {
            "capability_id": "common/payment.pay_order",
            "domain": "common/payment",
            "name": "支付订单并更新支付结果",
            "description": "拉起支付渠道对指定订单进行付款，并在支付成功后回写支付结果。",
            "capability_type": "technical",
        },
        {
            "capability_id": "membership/month_card/card.bind_plate",
            "domain": "membership/month_card",
            "name": "将车牌绑定到月卡",
            "description": "在指定车场内，将用户提供的车牌号与月卡实例建立绑定关系，作为后续进出场免费或优惠的依据。",
            "capability_type": "business",
        },
    ],
    "data_resources": [
        {
            "name": "user_card",
            "resource_id": "member_db.user_card",
            "type": "db_table",
            "system": "member-service",
            "location": "member_db.user_card",
            "description": "月卡实例表，记录每张月卡的用户、车场、产品、状态、生效时间与到期时间等信息。",
        },
        {
            "name": "pay_order",
            "resource_id": "pay_db.pay_order",
            "type": "db_table",
            "system": "payment-service",
            "location": "pay_db.pay_order",
            "description": "支付订单表，记录订单金额、支付渠道、支付状态、业务关联（如月卡ID）等信息。",
        },
        {
            "name": "card_plate_bind",
            "resource_id": "member_db.card_plate_bind",
            "type": "db_table",
            "system": "member-service",
            "location": "member_db.card_plate_bind",
            "description": "月卡与车牌的绑定关系表，支持一张月卡绑定多车牌或一车牌绑定多张卡的配置。",
        },
    ],
    "capability_implementations": [
        {
            "capability_id": "common/user.verify_identity",
            "system": "user-service",
            "entry_type": "http_endpoint",
            "entry_name": "POST /api/v1/user/verify_identity",
            "code_ref": "user-service/controllers/user_controller.py:verify_identity",
        },
        {
            "capability_id": "membership/month_card/card.check_open_eligibility",
            "system": "member-service",
            "entry_type": "rpc_method",
            "entry_name": "MemberCardService.CheckOpenEligibility",
            "code_ref": "member-service/services/card_service.py:check_open_eligibility",
        },
        {
            "capability_id": "membership/month_card/card.open",
            "system": "member-service",
            "entry_type": "http_endpoint",
            "entry_name": "POST /internal/month_card/open",
            "code_ref": "member-service/controllers/card_controller.py:open_card",
        },
        {
            "capability_id": "common/payment.pay_order",
            "system": "payment-service",
            "entry_type": "http_endpoint",
            "entry_name": "POST /api/v1/pay",
            "code_ref": "payment-service/controllers/pay_controller.py:pay_order",
        },
        {
            "capability_id": "membership/month_card/card.bind_plate",
            "system": "member-service",
            "entry_type": "rpc_method",
            "entry_name": "MemberCardService.BindPlate",
            "code_ref": "member-service/services/card_service.py:bind_plate",
        },
    ],
    "capability_data_access": [
        {
            "capability_id": "membership/month_card/card.check_open_eligibility",
            "resource_id": "member_db.user_card",
            "access_type": "read",
            "access_pattern": "按user_id和product_id查询现有有效月卡",
        },
        {
            "capability_id": "membership/month_card/card.open",
            "resource_id": "member_db.user_card",
            "access_type": "write",
            "access_pattern": "插入一条status=PENDING的新月卡记录",
        },
        {
            "capability_id": "membership/month_card/card.open",
            "resource_id": "pay_db.pay_order",
            "access_type": "write",
            "access_pattern": "插入一条待支付订单，business_type=MONTH_CARD_OPEN",
        },
        {
            "capability_id": "common/payment.pay_order",
            "resource_id": "pay_db.pay_order",
            "access_type": "read_write",
            "access_pattern": "按order_id更新支付状态，写入支付成功时间与渠道流水号",
        },
        {
            "capability_id": "membership/month_card/card.bind_plate",
            "resource_id": "member_db.card_plate_bind",
            "access_type": "write",
            "access_pattern": "插入一条card_id与plate_no的绑定关系记录",
        },
    ],
}


# ---- Cypher 辅助函数 ----


def create_constraints(session) -> None:
    """创建基础唯一性约束，保证 MERGE 行为符合预期。

    当前仅保留四类节点：
        - Business(process_id)
        - Step(step_id)
        - DataResource(resource_id)
        - Implementation(impl_id)
    """

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


def load_business_processes(session) -> None:
    """加载业务节点（Business）。

    说明：
        - 这里沿用 SAMPLE_DATA["business_processes"] 作为配置来源；
        - 实际写入的标签为 :Business，而不是早期版本的 :BusinessProcess；
        - 只保留与业务视角直接相关的属性。
    """

    for p in SAMPLE_DATA["business_processes"]:
        params = {
            "process_id": p["process_id"],
            "name": p["name"],
            "channel": p["channel"],
            "description": p["description"],
            "entrypoints": p.get("entrypoints", ""),
        }
        session.run(
            """
            MERGE (b:Business {process_id: $process_id})
            SET b.name = $name,
                b.channel = $channel,
                b.description = $description,
                b.entrypoints = $entrypoints
            """,
            **params,
        )


def load_business_process_steps(session) -> None:
    """加载业务步骤（Step），并通过 START_AT + NEXT 关系表达顺序。

    设计要点：
        - 不再单独创建 BusinessCapability 节点；
        - 使用 capability_id 作为 step_id，实现跨流程复用；
        - step 的顺序完全由 Business-START_AT->Step 和 Step-NEXT->Step 表达。
    """

    # 预先构建 capability 映射，用于填充步骤描述与 step_type
    capability_by_id: Dict[str, Dict[str, Any]] = {
        c["capability_id"]: c for c in SAMPLE_DATA["business_capabilities"]
    }

    # 按流程分组步骤数据，后续用 START_AT + NEXT 关系表示顺序
    steps_by_process: Dict[str, List[Dict[str, Any]]] = {}
    for s in SAMPLE_DATA["business_process_steps"]:
        process_id = s["process_id"]
        steps_by_process.setdefault(process_id, []).append(s)

    for process_id, steps in steps_by_process.items():
        # 使用配置中的 order_no 作为构建 NEXT 链的顺序依据，
        # 不再将顺序写入 step 节点属性。
        steps_sorted = sorted(steps, key=lambda x: x["order_no"])

        # 先创建/更新步骤节点本身
        for s in steps_sorted:
            cap_id = s["capability_id"]
            cap = capability_by_id.get(cap_id, {})
            params = {
                # 使用 capability_id 作为 step_id，避免在 ID 中编码顺序，便于跨流程复用
                "step_id": cap_id,
                "name": s["name"],
                "description": cap.get("description", s.get("condition", "")),
                "step_type": cap.get("capability_type", "business"),
            }
            session.run(
                """
                MERGE (step:Step {step_id: $step_id})
                SET step.name = $name,
                    step.description = $description,
                    step.step_type = $step_type
                """,
                **params,
            )

        # 建立流程起点关系：第一步
        first_cap_id = steps_sorted[0]["capability_id"]
        session.run(
            """
            MATCH (b:Business {process_id: $process_id})
            MATCH (first:Step {step_id: $first_step_id})
            MERGE (b)-[:START_AT]->(first)
            """,
            process_id=process_id,
            first_step_id=first_cap_id,
        )

        # 依次连接 NEXT 关系表示执行顺序
        for prev, curr in zip(steps_sorted, steps_sorted[1:]):
            session.run(
                """
                MATCH (from:Step {step_id: $from_step_id})
                MATCH (to:Step {step_id: $to_step_id})
                MERGE (from)-[rel:NEXT {process_id: $process_id}]->(to)
                """,
                from_step_id=prev["capability_id"],
                to_step_id=curr["capability_id"],
                process_id=process_id,
            )


def load_business_capabilities(session) -> None:
    for c in SAMPLE_DATA["business_capabilities"]:
        session.run(
            """
            MERGE (cap:BusinessCapability {capability_id: $capability_id})
            SET cap.domain = $domain,
                cap.name = $name,
                cap.description = $description,
                cap.capability_type = $capability_type
            """,
            **c,
        )

    # Link steps to capabilities
    for s in SAMPLE_DATA["business_process_steps"]:
        session.run(
            """
            MATCH (step:BusinessProcessStep {step_id: $step_id})
            MATCH (cap:BusinessCapability {capability_id: $capability_id})
            MERGE (step)-[:USES_CAPABILITY]->(cap)
            """,
            step_id=s["step_id"],
            capability_id=s["capability_id"],
        )


def load_data_resources(session) -> None:
    """加载数据资源（DataResource）。

    仅写入与业务视角直接相关的属性：
        - resource_id, name, type, system, description
    其余如 location/entity_id 仍保留在 SAMPLE_DATA 中作为配置来源，
    但不写入节点属性，以保持图结构简洁。
    """

    for r in SAMPLE_DATA["data_resources"]:
        params = {
            "resource_id": r["resource_id"],
            "name": r["name"],
            "type": r["type"],
            "system": r["system"],
            "description": r["description"],
        }
        session.run(
            """
            MERGE (dr:DataResource {resource_id: $resource_id})
            SET dr.name = $name,
                dr.type = $type,
                dr.system = $system,
                dr.description = $description
            """,
            **params,
        )


def load_capability_implementations(session) -> None:
    """加载执行节点（Implementation）以及数据访问关系。

    说明：
        - 不再创建 BusinessCapability 节点；
        - 使用 capability_implementations 作为 Implementation 配置来源；
        - 使用 capability_data_access 决定 Implementation → DataResource 的访问关系；
        - 使用 capability_id 关联到 Step(step_id) 并建立 EXECUTED_BY 关系。
    """

    # capability_id -> capability 配置（用于填充实现描述、类型等）
    capability_by_id: Dict[str, Dict[str, Any]] = {
        c["capability_id"]: c for c in SAMPLE_DATA["business_capabilities"]
    }

    # capability_id -> 该能力对应的数据访问列表
    data_access_by_cap: Dict[str, List[Dict[str, Any]]] = {}
    for cda in SAMPLE_DATA["capability_data_access"]:
        cap_id = cda["capability_id"]
        data_access_by_cap.setdefault(cap_id, []).append(cda)

    for idx, impl in enumerate(SAMPLE_DATA["capability_implementations"], start=1):
        cap_id = impl["capability_id"]
        cap = capability_by_id.get(cap_id, {})

        impl_with_id = {
            "impl_id": f"impl_{idx}",
            "name": impl["entry_name"],
            "type": impl["entry_type"],
            "system": impl["system"],
            "description": cap.get("description", ""),
            "code_ref": impl["code_ref"],
            "capability_id": cap_id,
        }

        # 创建/更新 Implementation 节点
        session.run(
            """
            MERGE (i:Implementation {impl_id: $impl_id})
            SET i.name = $name,
                i.type = $type,
                i.system = $system,
                i.description = $description,
                i.code_ref = $code_ref
            """,
            **impl_with_id,
        )

        # Step -> Implementation 的 EXECUTED_BY 关系（以 capability_id 作为 step_id）
        session.run(
            """
            MATCH (step:Step {step_id: $capability_id})
            MATCH (i:Implementation {impl_id: $impl_id})
            MERGE (step)-[:EXECUTED_BY]->(i)
            """,
            capability_id=cap_id,
            impl_id=impl_with_id["impl_id"],
        )

        # Implementation -> DataResource 的 ACCESSES_RESOURCE 关系
        for cda in data_access_by_cap.get(cap_id, []):
            params = {
                "impl_id": impl_with_id["impl_id"],
                "resource_id": cda["resource_id"],
                "access_type": cda["access_type"],
                "access_pattern": cda["access_pattern"],
            }
            session.run(
                """
                MATCH (i:Implementation {impl_id: $impl_id})
                MATCH (dr:DataResource {resource_id: $resource_id})
                MERGE (i)-[rel:ACCESSES_RESOURCE]->(dr)
                SET rel.access_type = $access_type,
                    rel.access_pattern = $access_pattern
                """,
                **params,
            )


def load_capability_data_access(session) -> None:
    for cda in SAMPLE_DATA["capability_data_access"]:
        session.run(
            """
            MATCH (cap:BusinessCapability {capability_id: $capability_id})
            MATCH (dr:DataResource {resource_id: $resource_id})
            MERGE (cap)-[rel:ACCESSES_RESOURCE]->(dr)
            SET rel.access_type = $access_type,
                rel.access_pattern = $access_pattern
            """,
            **cda,
        )


def main() -> None:
    cfg = get_neo4j_config()
    print(f"Connecting to Neo4j at {cfg.uri} as {cfg.user} ...")

    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
    try:
        with driver.session(database=cfg.database) as session:
            create_constraints(session)
            load_business_processes(session)
            load_business_process_steps(session)
            load_data_resources(session)
            load_capability_implementations(session)

        print("Data load completed. You can now explore the graph in Neo4j Browser.")
        print(
            "Example query: MATCH (b:Business {process_id: 'c_open_card'})-[*1..4]->(n) RETURN b, n"
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
