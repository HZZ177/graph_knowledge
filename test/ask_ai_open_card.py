"""示例脚本：从 Neo4j 查询“C 端开通月卡”流程，并调用大模型生成中文说明。

功能概述：
    1. 连接 Neo4j，读取 process_id = "c_open_card" 相关的流程、步骤、能力、实现与数据资源信息；
    2. 将查询结果整理成结构化 JSON 作为上下文；
    3. 调用大模型（以 OpenAI 官方 Python SDK 为例），让模型仅基于这些信息回答“开卡流程怎么走”。

前置条件：
    1. Neo4j 中已经通过 test/neo4j_load_open_card.py 写入了示例数据；
    2. 已安装依赖：

        pip install neo4j langchain langchain-openai

    3. 在本脚本中直接修改常量配置（开发阶段硬编码即可）：
        - Neo4j 连接：NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD
        - 大模型访问：OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL

运行方式（建议在项目根目录）：

    python -m test.ask_ai_open_card

本脚本仅用于演示：
    - 如何把图数据库中的“业务流程子图”变成 LLM 的上下文；
    - 不做问题意图识别，默认只回答 C 端开通月卡（process_id = c_open_card）。
"""

import json
import os
from dataclasses import dataclass
from time import sleep
from typing import Any, Dict, List

from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage


# Neo4j 连接配置（开发阶段直接在代码中硬编码，根据实际环境修改）
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Keytop@123"

# 大模型配置（开发阶段硬编码，注意不要在生产环境中这样使用）
OPENAI_API_KEY = "sk-cvqWUuYL0c6Nw3gK9UH3TtGzfnUWyntiFtolbzw7sgFSWQQ2"
# 注意：base_url 应该是 API 根地址（例如 https://api.xxx.com/v1），
# ChatOpenAI / OpenAI SDK 会在其后自动拼接 /chat/completions 等具体路径。
OPENAI_BASE_URL = "https://x666.me/v1"  # 按照 OpenAI 协议风格的根路径
OPENAI_MODEL = "gemini-2.5-flash"  # 如使用其他模型，可在此修改

# 调试开关：为 True 时，会打印发送给大模型的消息内容
DEBUG_PRINT_MESSAGES = True


@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str


def get_neo4j_config() -> Neo4jConfig:
    """构造 Neo4j 配置（开发阶段使用代码中的常量）。"""

    return Neo4jConfig(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )


def get_llm() -> ChatOpenAI:
    """创建 LangChain 的 ChatOpenAI 客户端。

    说明：
        - 开发阶段直接使用脚本中硬编码的 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL；
        - 如使用自建网关，可以在 OPENAI_BASE_URL 中指定自定义 base_url；
        - 底层仍然走 OpenAI 协议，但通过 LangChain 的 ChatOpenAI 封装调用。
    """

    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_API_KEY_HERE":
        raise RuntimeError("请先在脚本中设置正确的 OPENAI_API_KEY 常量。")

    client_kwargs: Dict[str, Any] = {
        "api_key": OPENAI_API_KEY,
        "model": OPENAI_MODEL,
    }
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**client_kwargs)


def fetch_process_context(process_id: str) -> Dict[str, Any]:
    """从 Neo4j 查询指定业务流程及其相关节点，整理为结构化上下文。

    返回的结构大致形如：
        {
            "process": {...},
            "steps": [
                {
                    "step": {...},
                    "capability": {...},
                    "implementations": [...],
                    "data_accesses": [...],
                },
                ...
            ]
        }
    """

    cfg = get_neo4j_config()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))

    try:
        with driver.session() as session:
            # 查询业务节点
            record = session.run(
                "MATCH (b:Business {process_id: $pid}) RETURN b",
                pid=process_id,
            ).single()
            if record is None:
                raise RuntimeError(f"未在图中找到 process_id={process_id!r} 对应的 BusinessProcess 节点。")
            b_node = record["b"]
            process_data = dict(b_node)

            # 查询该业务下的主流程：
            # - 从 Business-[:START_AT]->(start:Step) 出发
            # - 沿 [:NEXT] 关系找到一条最长路径
            # - 对路径上的每个 Step 查询其 Implementation 与 DataResource
            result = session.run(
                """
                MATCH (b:Business {process_id: $pid})-[:START_AT]->(start:Step)
                MATCH path = (start)-[:NEXT*0..10]->(end:Step)
                WITH b, path
                ORDER BY length(path) DESC
                LIMIT 1
                WITH b, nodes(path) AS steps
                UNWIND range(0, size(steps) - 1) AS idx
                WITH b, steps[idx] AS step, idx AS order_index
                OPTIONAL MATCH (step)-[:EXECUTED_BY]->(impl:Implementation)
                OPTIONAL MATCH (impl)-[rel:ACCESSES_RESOURCE]->(dr:DataResource)
                WITH b, step, order_index,
                     collect(DISTINCT impl) AS impls,
                     collect(DISTINCT {resource: dr, rel: rel}) AS accesses
                RETURN b, step, order_index, impls, accesses
                ORDER BY order_index
                """,
                pid=process_id,
            )

            steps: List[Dict[str, Any]] = []
            for rec in result:
                step_node = rec["step"]
                impl_nodes = rec["impls"] or []
                access_items = rec["accesses"] or []
                order_index = rec["order_index"]

                step_data = dict(step_node)
                step_data["order_index"] = order_index

                implementations: List[Dict[str, Any]] = []
                for impl in impl_nodes:
                    if impl is None:
                        continue
                    implementations.append(dict(impl))

                data_resources: List[Dict[str, Any]] = []
                for item in access_items:
                    dr = item.get("resource") if isinstance(item, dict) else None
                    rel = item.get("rel") if isinstance(item, dict) else None
                    if dr is None or rel is None:
                        continue
                    data_resources.append(
                        {
                            "resource": dict(dr),
                            "access_type": rel.get("access_type"),
                            "access_pattern": rel.get("access_pattern"),
                        }
                    )

                steps.append(
                    {
                        "step": step_data,
                        "implementations": implementations,
                        "data_resources": data_resources,
                    }
                )

        return {"process": process_data, "steps": steps}

    finally:
        driver.close()


def build_system_message() -> SystemMessage:
    """构造系统消息，描述可选的“查询业务流程图”工具和回答风格约束。

    简化工具协议：
        - 你拥有一个可选的内部工具：GET_C_OPEN_CARD_GRAPH；
        - 当你觉得有必要查看“C 端开通月卡”业务流程的详细图谱时，
          请在单独一条回复中只输出：TOOL:GET_C_OPEN_CARD_GRAPH；
        - 脚本会据此从 Neo4j 查询 process_id = "c_open_card" 的流程子图，
          并以系统消息的形式把 JSON 上下文提供给你；
        - 之后你应基于该上下文，用业务语言给出面向用户的回答；
        - 除非确实需要更精确的内部流程信息，否则不要随意请求该工具。"""

    system_prompt = (
        "你是一个企业内部的业务知识助手，主要任务是：\n"
        "- 首先基于你的一般业务理解来回答问题；\n"
        "- 当你觉得需要更精确的“C 端开通月卡”流程信息时，可以调用内部工具。\n\n"
        "工具使用约定：\n"
        "- 你可以使用一个内部工具 GET_C_OPEN_CARD_GRAPH；\n"
        "- 如果你需要调用该工具，请在单独一条回复中只输出：TOOL:GET_C_OPEN_CARD_GRAPH；\n"
        "- 不要在这条消息中输出其他任何内容；\n"
        "- 工具返回后，你会收到一条包含 JSON 的系统消息，其中是“C 端开通月卡”的业务流程子图；\n"
        "- 之后请基于该 JSON 回答用户的问题。\n\n"
        "回答风格要求：\n"
        "- 回答时要面向业务使用者，不要暴露内部的能力ID、服务内部类名、数据库表名等技术细节；\n"
        "- 用中文回答，按业务步骤说明流程的执行顺序，说明大概经过哪些系统，以及数据大致如何流转即可；\n"
        "- 不要编造上下文中不存在的系统、接口或表。"
    )

    return SystemMessage(content=system_prompt)


def ask_ai_about_open_card() -> None:
    """主入口：支持多轮对话的开卡流程问答。

    设计要点：
        - 启动时不主动查询 Neo4j，仅提供工具使用说明；
        - 进入循环，每次读取用户输入，将其作为 HumanMessage 追加到历史；
        - 对于每一轮，先让模型基于已有上下文思考，若模型显式请求工具，则再查询 Neo4j；
        - 将工具返回的 JSON 作为新的系统消息加入历史，再让模型生成最终面向用户的回答。"""

    print("输入 exit/退出 结束对话。")

    llm = get_llm()
    system_msg = build_system_message()

    # 消息历史：始终包含系统消息 + 多轮问答
    history: List[BaseMessage] = [system_msg]

    while True:
        question = input("你: ").strip()
        if question.lower() in {"exit", "quit", "q", "bye", "退出", "结束"}:
            print("结束对话。")
            break
        if not question:
            continue

        # 将用户输入加入历史
        user_msg = HumanMessage(content=question)
        history.append(user_msg)

        # 每轮最多处理一次工具调用 + 一次最终回答
        tool_used = False
        while True:
            if DEBUG_PRINT_MESSAGES:
                print("\n[调试] 本轮调用前的完整消息历史：")
                for i, msg in enumerate(history, start=1):
                    role = getattr(msg, "type", "unknown")
                    print(f"--- message {i} ({role}) ---")
                    print(msg.content)
                    print()

            # 先做一次非流式调用，用于判断是否需要触发工具
            probe_msg = llm.invoke(history)
            content = (probe_msg.content or "").strip()

            # 检查是否是工具调用请求：允许模型在说明后附带 TOOL 标记
            # 只要包含该标记且本轮尚未使用工具，即视为一次工具调用请求。
            if "TOOL:GET_C_OPEN_CARD_GRAPH" in content and not tool_used:
                print("\n[工具触发] 模型请求获取 C 端开通月卡流程图，正在查询 Neo4j ...")
                # 记录这次工具请求
                history.append(probe_msg)

                # 实际调用 Neo4j 工具
                sleep(5)  # 避免对 Neo4j 瞬时压力
                context = fetch_process_context("c_open_card")
                context_json = json.dumps(context, ensure_ascii=False, indent=2)
                tool_msg_text = (
                    "(系统消息) 工具 GET_C_OPEN_CARD_GRAPH 的返回结果：\n"
                    "下面是 C 端开通月卡的业务流程子图（JSON 格式）：\n"
                    "```json\n"
                    f"{context_json}\n"
                    "```"
                )
                history.append(SystemMessage(content=tool_msg_text))
                # 追加一条显式的人类提示，让模型继续基于上面的 JSON 回答问题，
                # 确保最后一条消息角色为 human。
                history.append(
                    HumanMessage(content="请你基于以上流程图的内容，继续回答用户刚才的问题。")
                )
                tool_used = True

                # 继续内层循环，让模型基于新上下文给出真正回答
                continue

            # 否则视为面向用户的正常回答：这里改为“伪流式”输出
            answer = content
            print("\nAI:")
            streamed_text = ""
            for ch in answer:
                streamed_text += ch
                print(ch, end="", flush=True)
            print()

            # 将完整回答加入历史，支持后续多轮对话
            history.append(probe_msg)
            break


if __name__ == "__main__":
    ask_ai_about_open_card()
