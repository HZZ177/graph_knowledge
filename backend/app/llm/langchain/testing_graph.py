"""智能测试助手 LangGraph 状态机

实现三阶段工作流：
1. 需求分析（analysis）：深度分析需求文档和代码
2. 方案生成（plan）：制定测试范围和策略
3. 用例生成（generate）：生成结构化测试用例

关键设计：
- 每个阶段使用独立的 thread_id，避免历史消息累积导致 Token 爆炸
- 阶段间通过数据库存储的摘要传递信息
- 使用 LangGraph StateGraph 强制控制阶段顺序
"""

from typing import Annotated, Optional, Any, Dict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, ModelCallLimitMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from backend.app.core.logger import logger


# ============================================================
# 状态定义
# ============================================================

class TestingState(TypedDict):
    """测试助手状态定义
    
    使用 Annotated + add_messages 实现消息自动追加
    """
    # messages 字段使用 add_messages reducer（自动追加而非覆盖）
    messages: Annotated[list, add_messages]
    
    # 会话信息（普通覆盖）
    session_id: str
    requirement_id: str
    project_name: str
    
    # 阶段流转
    current_phase: str  # analysis / plan / generate / completed
    
    # 阶段间传递的摘要（从数据库读取后注入）
    analysis_summary: str
    test_plan: str
    test_cases: str
    
    # 错误信息
    error: str


# ============================================================
# Prompt 模板
# ============================================================

PHASE1_ANALYSIS_PROMPT = """
# Role: 需求分析与代码理解专家

## Profile
- 你是一个专业的测试分析师，擅长理解需求文档和代码实现
- 你需要深入分析 Coding 需求，理解业务流程和代码逻辑
- 你的分析结果将作为后续测试方案和用例生成的基础

## 当前任务
- 会话ID: {session_id}
- 需求ID: {requirement_id}
- 项目: {project_name}

## 可用代码库
{workspace_description}

## 工作流程

### 第一步：创建任务看板
分析需求后，**立即调用** `create_task_board` 工具创建任务看板。任务应包含：
- 解析需求文档
- 分析各功能模块的业务流程
- 代码逻辑分析

### 第二步：获取需求详情
调用 `get_coding_issue_detail` 工具获取完整的需求文档内容。

### 第三步：逐个执行任务
对于每个任务：
1. 调用 `update_task_status(task_id, "in_progress")` 标记开始
2. 执行分析（调用代码搜索、知识图谱等工具）
3. 调用 `update_task_status(task_id, "completed", result="...")` 标记完成

### 第四步：保存分析摘要（必须执行）
**所有任务完成后，必须调用** `save_phase_summary` 工具保存结构化摘要：
- session_id: "{session_id}"（直接使用这个值，不要修改）
- analysis_type: "requirement_summary"
- content: JSON 格式的分析摘要

**重要：如果不保存摘要，下一阶段将无法获取分析结果！**

## 摘要内容要求（JSON格式）
摘要必须包含以下结构化信息：
```json
{{
  "requirement": {{
    "id": "需求编号",
    "title": "需求标题",
    "modules": ["涉及模块1", "涉及模块2"]
  }},
  "business_flow": [
    {{"step": 1, "name": "步骤名称", "description": "步骤描述"}}
  ],
  "code_logic": {{
    "entry_point": "主入口函数",
    "validations": ["校验条件1", "校验条件2"],
    "exceptions": ["异常类型1", "异常类型2"],
    "db_operations": ["数据库操作1"]
  }},
  "test_focus": {{
    "boundary_values": ["边界值场景1"],
    "exception_scenarios": ["异常场景1"]
  }}
}}
```

## 工具使用规范
- 使用 `get_coding_issue_detail` 获取需求详情（返回结构化数据，保留图片位置）
- 使用 `search_code_context` 进行代码语义搜索
- 使用 `read_file` 读取具体代码文件
- 使用 `search_businesses` 等知识图谱工具了解业务上下文
- 调用代码工具时必须指定 `workspace` 参数

## 结构化需求理解
`get_coding_issue_detail` 返回的 content_blocks 按原始顺序保持文本和图片的位置关系：
- `type: "text"`: 文本内容块
- `type: "image"`: 图片块（包含 url、alt 描述、index 序号）

你应该：
1. 理解图片在需求文档中的位置和上下文（图片前后的文本通常是对图片的说明）
2. 根据 alt 描述和上下文推断图片内容（如"流程图"、"原型图"、"界面截图"等）
3. 将图片位置信息与文本描述结合，形成完整的需求理解

## 输出规范
- 在消息中展示你的分析思路和发现
- 关键代码片段可以引用展示

## 阶段结束时的必要操作（按顺序）
1. **必须先调用** `save_phase_summary(session_id="{session_id}", analysis_type="requirement_summary", content="...")` 保存摘要
2. **确认摘要保存成功后**，调用 `transition_phase` 切换到下一阶段

警告：如果不保存摘要就切换阶段，下一阶段将无法获取你的分析结果！
"""

PHASE2_PLAN_PROMPT = """
# Role: 测试方案设计师

## Profile
- 你是一个经验丰富的测试架构师
- 基于需求分析结果，制定全面的测试方案
- 你的方案将指导后续的测试用例生成

## 当前任务
- 会话ID: {session_id}

## 上下文
以下是需求分析阶段的摘要：
{analysis_summary}

## 工作流程

### 第一步：创建任务看板
```json
{{
  "phase": "plan",
  "tasks": [
    {{"id": "plan_1", "title": "确定测试范围", "scope": "scope"}},
    {{"id": "plan_2", "title": "制定测试策略", "scope": "strategy"}},
    {{"id": "plan_3", "title": "风险分析", "scope": "risk"}}
  ]
}}
```

### 第二步：逐个执行并更新状态
对于每个任务，分析后更新状态。

### 第三步：保存测试方案（必须执行）
**必须调用** `save_phase_summary` 工具保存方案：
- session_id: "{session_id}"（直接使用这个值）
- analysis_type: "test_plan"
- content: JSON 格式的测试方案

## 方案内容要求（JSON格式）
```json
{{
  "scope": {{
    "in_scope": ["测试范围内的功能"],
    "out_scope": ["测试范围外的功能"]
  }},
  "strategy": {{
    "functional": "功能测试策略",
    "boundary": "边界测试策略",
    "exception": "异常测试策略"
  }},
  "risks": [
    {{"risk": "风险描述", "mitigation": "缓解措施"}}
  ],
  "priority": {{
    "P0": ["最高优先级用例"],
    "P1": ["高优先级用例"],
    "P2": ["中优先级用例"]
  }},
  "modules": [
    {{"name": "模块名称", "test_points": ["测试点1", "测试点2"]}}
  ]
}}
```

## 输出规范
- 输出清晰的测试方案文档
- 包含测试范围、策略、风险分析
- 为每个功能模块指定测试优先级

## 阶段结束时的必要操作（按顺序）
1. **必须先调用** `save_phase_summary(session_id="{session_id}", analysis_type="test_plan", content="...")` 保存方案
2. **确认方案保存成功后**，调用 `transition_phase` 切换到下一阶段

警告：如果不保存方案就切换阶段，下一阶段将无法获取测试方案！
"""

PHASE3_GENERATE_PROMPT = """
# Role: 测试用例生成专家

## Profile
- 你是一个专业的测试用例设计师
- 基于测试方案，生成详细的测试用例
- 确保覆盖功能、边界、异常三类场景

## 当前任务
- 会话ID: {session_id}

## 上下文
以下是测试方案：
{test_plan}

## 工作流程

### 第一步：按功能模块创建任务
根据测试方案中的 modules，为每个模块创建生成任务。

### 第二步：逐个功能生成用例
对于每个功能模块：
1. 标记任务开始
2. 生成功能用例（正常流程）
3. 生成边界用例（边界值）
4. 生成异常用例（异常场景）
5. 标记任务完成，result 中包含该模块的用例数量

### 第三步：保存用例集（必须执行）
**必须调用** `save_phase_summary` 工具保存所有用例：
- session_id: "{session_id}"（直接使用这个值）
- analysis_type: "test_cases"
- content: JSON 格式的用例集

## 用例格式要求（JSON格式）
```json
{{
  "summary": {{
    "total_count": 50,
    "by_type": {{"functional": 20, "boundary": 15, "exception": 15}},
    "by_priority": {{"P0": 10, "P1": 20, "P2": 20}}
  }},
  "test_cases": [
    {{
      "id": "TC_001",
      "module": "功能模块名称",
      "type": "functional",
      "priority": "P0",
      "title": "用例标题",
      "precondition": "前置条件",
      "steps": ["步骤1", "步骤2", "步骤3"],
      "expected": "预期结果",
      "test_data": {{"key": "value"}}
    }}
  ]
}}
```

## 用例类型说明
- **functional**: 功能用例，验证正常业务流程
- **boundary**: 边界用例，验证边界值和临界条件
- **exception**: 异常用例，验证异常处理和错误场景

## 优先级说明
- **P0**: 核心功能，必须测试
- **P1**: 重要功能，应该测试
- **P2**: 一般功能，可选测试

## 输出规范
- 按模块组织输出用例
- 每个模块包含功能、边界、异常三类用例
- 最终汇总用例统计

## 阶段结束时的必要操作（按顺序）
1. **必须先调用** `save_phase_summary(session_id="{session_id}", analysis_type="test_cases", content="...")` 保存用例集
2. **确认用例集保存成功后**，调用 `transition_phase` 切换到 completed 状态

警告：如果不保存用例集，测试结果将会丢失！
"""


# ============================================================
# 辅助函数
# ============================================================

async def get_phase_summary_from_db(session_id: str, analysis_type: str) -> str:
    """从数据库读取阶段摘要"""
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionAnalysis
    
    db = SessionLocal()
    try:
        record = db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type == analysis_type
        ).first()
        return record.content if record else ""
    finally:
        db.close()


def get_workspace_description() -> str:
    """获取代码库工作区描述"""
    from backend.app.llm.config import CodeWorkspaceConfig
    return CodeWorkspaceConfig.get_workspace_description()


# ============================================================
# 节点函数
# ============================================================

async def analysis_node(state: TestingState, config: RunnableConfig) -> dict:
    """阶段1：需求分析节点
    
    使用 langchain.agents.create_agent 执行多轮 ReAct 工具调用。
    """
    from backend.app.llm.langchain.tools.testing import get_testing_tools_phase1
    from backend.app.llm.factory import get_langchain_llm
    from backend.app.db.sqlite import SessionLocal
    
    session_id = state["session_id"]
    requirement_id = state["requirement_id"]
    project_name = state["project_name"]
    
    logger.info(f"[TestingGraph] 开始阶段1-需求分析: session={session_id}, requirement={requirement_id}")
    
    # 获取 LLM
    db = SessionLocal()
    try:
        llm = get_langchain_llm(db)
    finally:
        db.close()
    
    # 构建 Prompt
    prompt = PHASE1_ANALYSIS_PROMPT.format(
        session_id=session_id,
        requirement_id=requirement_id,
        project_name=project_name,
        workspace_description=get_workspace_description(),
    )
    
    # 创建 Agent（使用新版 langchain.agents.create_agent）
    tools = get_testing_tools_phase1()
    middleware = [
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=30, exit_behavior="continue"),
    ]
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=prompt,
        middleware=middleware,
    )
    
    # 执行 Agent
    result = await agent.ainvoke({"messages": state["messages"]}, config)
    
    # 从数据库读取 AI 保存的摘要
    summary = await get_phase_summary_from_db(session_id, "requirement_summary")
    
    logger.info(f"[TestingGraph] 阶段1完成: session={session_id}, summary_len={len(summary)}")
    
    return {
        "messages": result["messages"],
        "analysis_summary": summary,
        "current_phase": "plan",
    }


async def plan_node(state: TestingState, config: RunnableConfig) -> dict:
    """阶段2：方案生成节点"""
    from backend.app.llm.langchain.tools.testing import get_testing_tools_phase2
    from backend.app.llm.factory import get_langchain_llm
    from backend.app.db.sqlite import SessionLocal
    
    session_id = state["session_id"]
    analysis_summary = state.get("analysis_summary", "")
    
    # 如果摘要为空，从数据库重新读取
    if not analysis_summary:
        analysis_summary = await get_phase_summary_from_db(session_id, "requirement_summary")
    
    logger.info(f"[TestingGraph] 开始阶段2-方案生成: session={session_id}")
    
    # 获取 LLM
    db = SessionLocal()
    try:
        llm = get_langchain_llm(db)
    finally:
        db.close()
    
    # 构建 Prompt
    prompt = PHASE2_PLAN_PROMPT.format(
        session_id=session_id,
        analysis_summary=analysis_summary,
    )
    
    # 创建 Agent（使用新版 langchain.agents.create_agent）
    tools = get_testing_tools_phase2()
    middleware = [
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=30, exit_behavior="continue"),
    ]
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=prompt,
        middleware=middleware,
    )
    
    # 阶段2 使用新的消息（不携带阶段1的工具调用历史）
    initial_message = HumanMessage(content="请基于需求分析摘要生成测试方案")
    result = await agent.ainvoke({"messages": [initial_message]}, config)
    
    # 读取保存的方案
    plan = await get_phase_summary_from_db(session_id, "test_plan")
    
    logger.info(f"[TestingGraph] 阶段2完成: session={session_id}, plan_len={len(plan)}")
    
    return {
        "messages": result["messages"],
        "test_plan": plan,
        "current_phase": "generate",
    }


async def generate_node(state: TestingState, config: RunnableConfig) -> dict:
    """阶段3：用例生成节点"""
    from backend.app.llm.langchain.tools.testing import get_testing_tools_phase3
    from backend.app.llm.factory import get_langchain_llm
    from backend.app.db.sqlite import SessionLocal
    
    session_id = state["session_id"]
    test_plan = state.get("test_plan", "")
    
    # 如果方案为空，从数据库重新读取
    if not test_plan:
        test_plan = await get_phase_summary_from_db(session_id, "test_plan")
    
    logger.info(f"[TestingGraph] 开始阶段3-用例生成: session={session_id}")
    
    # 获取 LLM
    db = SessionLocal()
    try:
        llm = get_langchain_llm(db)
    finally:
        db.close()
    
    # 构建 Prompt
    prompt = PHASE3_GENERATE_PROMPT.format(
        session_id=session_id,
        test_plan=test_plan,
    )
    
    # 创建 Agent（使用新版 langchain.agents.create_agent）
    tools = get_testing_tools_phase3()
    middleware = [
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=30, exit_behavior="continue"),
    ]
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=prompt,
        middleware=middleware,
    )
    
    # 阶段3 使用新的消息
    initial_message = HumanMessage(content="请基于测试方案生成测试用例")
    result = await agent.ainvoke({"messages": [initial_message]}, config)
    
    # 读取保存的用例
    cases = await get_phase_summary_from_db(session_id, "test_cases")
    
    logger.info(f"[TestingGraph] 阶段3完成: session={session_id}, cases_len={len(cases)}")
    
    return {
        "messages": result["messages"],
        "test_cases": cases,
        "current_phase": "completed",
    }


# ============================================================
# 构建状态图
# ============================================================

def create_testing_graph(checkpointer=None):
    """创建测试助手状态机
    
    Args:
        checkpointer: 检查点存储（可选，用于持久化状态）
        
    Returns:
        编译后的 CompiledGraph
    """
    # 创建图构建器
    graph_builder = StateGraph(TestingState)
    
    # 添加节点
    graph_builder.add_node("analysis", analysis_node)
    graph_builder.add_node("plan", plan_node)
    graph_builder.add_node("generate", generate_node)
    
    # 添加边（START 是新版 API）
    graph_builder.add_edge(START, "analysis")
    graph_builder.add_edge("analysis", "plan")
    graph_builder.add_edge("plan", "generate")
    graph_builder.add_edge("generate", END)
    
    # 编译图（可选传入 checkpointer）
    return graph_builder.compile(checkpointer=checkpointer)


def get_initial_state(
    session_id: str,
    requirement_id: str,
    project_name: str,
    requirement_name: str = "",
) -> TestingState:
    """获取初始状态
    
    Args:
        session_id: 会话 ID
        requirement_id: 需求编号（Coding issue code）
        project_name: Coding 项目名称
        requirement_name: 需求标题（可选，用于展示）
    """
    # 构建明确的初始指令，让 AI 自动开始工作
    initial_message = f"""请开始分析以下需求并生成测试用例：

**项目**: {project_name}
**需求编号**: {requirement_id}
**需求标题**: {requirement_name or '待获取'}

请按照以下步骤执行：
1. 首先调用 `get_coding_issue_detail` 工具获取需求详情（参数：project_name="{project_name}", issue_code={requirement_id}）
2. 分析需求内容和相关代码实现
3. 保存分析摘要并进入下一阶段"""

    return {
        "messages": [HumanMessage(content=initial_message)],
        "session_id": session_id,
        "requirement_id": requirement_id,
        "project_name": project_name,
        "current_phase": "analysis",
        "analysis_summary": "",
        "test_plan": "",
        "test_cases": "",
        "error": "",
    }
