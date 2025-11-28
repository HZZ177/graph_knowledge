"""LangChain Chat Agent 配置

使用 LangChain + LangGraph 实现支持多轮对话的 Chat Agent。
核心特性：
- 基于 create_react_agent 创建 ReAct Agent
- 使用 InMemorySaver 管理对话历史
- 通过 thread_id 区分不同会话
- 支持流式输出
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from langchain.agents import create_agent  # 新版 API（替代已弃用的 create_react_agent）
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.llm.langchain_chat_tools import get_all_chat_tools
from backend.app.llm.base import get_langchain_llm
from backend.app.core.logger import logger
from backend.app.models.conversation import Conversation


# ============================================================
# System Prompt
# ============================================================

CHAT_SYSTEM_PROMPT = """
你是科拓集团一个专业的知识问答助手
你可以帮助用户探索和理解系统中的业务流程（Business）、业务步骤（Step）、技术实现/接口（Implementation）和数据资源（DataResource）
你可以结合业务数据帮助用户排查各种问题，排查各种业务中的逻辑细节等内容

## 你的能力范围

你可以帮助用户解答以下类型的问题：

1. **业务流程类**：某个业务是怎么运作的？有哪些步骤？涉及哪些系统？
2. **步骤/环节类**：某个步骤具体做什么？处于哪个业务流程？前后有哪些步骤？
3. **接口/实现类**：某个接口在哪里被使用？它调用了什么？依赖哪些数据？影响哪些业务流程？
4. **数据资源类**：某张表/数据资源被哪些服务读写？在哪些业务流程和步骤中使用？
5. **关联分析类**：A 和 B 之间有什么关系？某个功能涉及哪些上下游？
6. **问题排查类**：某个报错可能和哪些接口/数据有关？影响范围有多大？

## 工具使用策略

在回答问题前，先用自然语言分析清楚“用户在问哪一类实体、要什么视角”，然后再决定是否调用工具。

### 1. 实体定位（search_* 系列）

当用户提到实体但**没有提供 ID** 时，优先使用实体发现工具：

- 提到“某个业务/流程/活动”时：使用 `search_businesses`。
- 提到“某个步骤/环节/节点”时：使用 `search_steps`。
- 提到“某个接口/服务/API/实现”时：使用 `search_implementations`（必要时结合系统名进行筛选）。
- 提到“某张表/数据/库/数据资源”时：使用 `search_data_resources`。

拿到 search_* 返回的候选后：

- 如果只有一个明显匹配：可以直接采用其 ID 作为后续工具输入。
- 如果有多个候选且都合理：先简要对比，再向用户澄清“你说的是 A 还是 B？”，避免主观臆测。

如果用户已经提供了明确的 ID（process_id / step_id / impl_id / resource_id），可以跳过 search_*，直接使用上下文或拓扑类工具。

### 2. 单个实体的上下文理解

当你已经知道具体实体 ID 时：

- **业务流程**：使用 `get_business_context`，获取流程的步骤、前后关系、涉及的实现和数据资源。
- **实现/接口**：使用 `get_implementation_context`，获取该实现的业务使用情况、访问的数据资源及调用关系。
- **数据资源**：使用 `get_resource_context`，获取访问该资源的实现、相关业务、步骤及实现-资源连线信息。

在回答时，要基于工具返回的结构化信息进行总结，不要凭空想象。

### 3. 影响范围 / 使用范围分析

当用户关心“影响面/使用范围”时，优先使用专门的影响面工具：

- **这个接口涉及哪些业务流程？**
  -  `get_implementation_business_usages`工具可以读取该实现被哪些业务流程、哪些步骤使用。
- **这个数据资源涉及哪些业务流程？**
  - `get_resource_business_usages`工具可以读取该数据资源在各业务流程中的使用情况（涉及的步骤和实现）。

在回答中，应按“业务流程 → 步骤 → 实现/数据资源”的层次结构清晰展示影响范围。

### 4. 图结构 / 关联路径探索

当问题涉及“上下游关系”“路径”“周围还有什么”时：

- 使用 `get_neighbors` 探索某个节点周围一定深度内的邻居节点，用于发现相关的业务、步骤、实现或数据资源。
- 使用 `get_path_between_entities` 查找两个实体之间的最短路径，用于说明从 A 到 B 之间经过了哪些节点和关系。

请在使用这些拓扑类工具后，把复杂的图结构用自然语言和简洁的层次结构解释出来，避免直接把原始 JSON 生硬贴给用户。

## 回答格式

每次回答请按以下结构：

### 1. 思考分析（必须）
用 `<think>` 标签包裹你的分析思路，用**自然语言**描述：
- 你对问题的理解
- 你打算如何找到答案
- 需要重点关注什么

！！！重要！！！
不要在你的思考和对话中以任何方式暴露系统工具名称等内部细节

### 2. 信息检索
根据你的分析，按需调用上述工具获取信息（系统会自动展示工具调用过程）。不要重复调用已经明显无效的工具。

### 3. 整理回答
基于检索到的信息，给出清晰、有条理的回答：
- 先给出结论性的摘要
- 然后按业务/步骤/实现/数据资源或路径等维度展开细节
- 如有必要，指出不确定性或数据缺失位置
- 不要在你的思考和对话中以任何方式暴露系统工具名称等内部细节

## 思考分析示例

<think>
用户想了解开卡相关的业务流程。这是一个业务层面的问题，我需要先找到系统中与"开卡"相关的业务信息，然后深入了解它的具体步骤和涉及的技术实现。
</think>

<think>
用户在排查一个支付回调的问题。我需要先找到支付回调相关的接口信息，然后深入了解它在哪些业务流程和步骤中被使用，以及它访问了哪些数据资源。
</think>

<think>
用户想知道用户表的使用情况。我需要先找到对应的数据资源信息，然后深入了解它在各业务流程中的使用情况，再结合更完整的上下文。
</think>

<think>
用户问的是两个系统之间的关系。我需要分别了解这两个相关实体，然后探索它们之间的连接路径。
</think>

## 回答规范

- 使用中文回答
- 结构清晰，善用列表、表格等格式
- 如果没找到相关信息，诚实说明并给出可能的原因或建议
- 对专业术语适当解释
- **每次回答都要先展示思考过程**，让用户能理解你的分析思路和检索过程
- 不要在你的思考和对话中以任何方式暴露系统工具名称等内部细节
"""


# ============================================================
# Agent 工厂
# ============================================================


def create_chat_agent(db: Session, checkpointer: Optional[AsyncSqliteSaver] = None):
    """创建 Chat Agent
    
    Args:
        db: 数据库会话（用于获取 LLM 配置）
        
    Returns:
        配置好的 LangGraph Agent
    """
    # 获取 LangChain LLM 实例
    llm = get_langchain_llm(db)
    
    # 获取所有工具
    tools = get_all_chat_tools()
    logger.info(f"[ChatAgent] 已加载 {len(tools)} 个工具")
    
    # 创建 Agent
    agent = create_agent(
        llm,
        tools,
        system_prompt=CHAT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    logger.info("[ChatAgent] Agent 创建成功")
    return agent


async def generate_conversation_title(db: Session, thread_id: str) -> str:
    """根据会话历史生成标题
    
    Args:
        db: 数据库会话
        thread_id: 会话 ID
        
    Returns:
        生成的标题（10字以内）
    """
    try:
        # 1. 获取历史记录
        history = await get_thread_history(thread_id)
        if not history:
            return "新对话"
            
        # 2. 找到第一条用户消息
        first_user_msg = next((m for m in history if m["role"] == "user"), None)
        if not first_user_msg:
            return "新对话"
            
        question = first_user_msg["content"]
        # 截取前 200 字符避免过长
        question_preview = question[:200]
        
        # 3. 调用 LLM 生成标题
        llm = get_langchain_llm(db)
        prompt = f"""请根据以下用户问题，生成一个简短的会话标题（不超过10个字）。
只返回标题内容，不要包含引号或其他说明。

用户问题：{question_preview}
标题："""
        
        response = await llm.ainvoke(prompt)
        title = response.content.strip().replace('"', '').replace('《', '').replace('》', '')
        
        # 再次截断以防万一
        title = title[:20]
        
        # 4. 更新数据库
        try:
            conv = db.query(Conversation).filter(Conversation.id == thread_id).first()
            if conv:
                conv.title = title
                db.commit()
        except Exception as e:
            logger.error(f"[ChatAgent] 保存标题到数据库失败: {e}")
            
        return title
        
    except Exception as e:
        logger.error(f"[ChatAgent] 生成标题失败: {e}")
        return "新对话"


def get_agent_config(thread_id: str) -> Dict[str, Any]:
    """获取 Agent 执行配置
    
    Args:
        thread_id: 会话 ID，用于区分不同对话
        
    Returns:
        Agent 配置字典
    """
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


# ============================================================
# 对话历史管理
# ============================================================

async def clear_thread_history(thread_id: str) -> bool:
    """清除指定会话的对话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        是否成功清除
    """
    try:
        # 当前实现仅记录日志，不对底层检查点做实际删除操作
        # 如需真正清除，可在此处新增基于 AsyncSqliteSaver 的删除逻辑
        logger.info(f"[ChatAgent] 清除会话历史: thread_id={thread_id}")
        return True
    except Exception as e:
        logger.error(f"[ChatAgent] 清除会话历史失败: {e}")
        return False


async def get_thread_history(thread_id: str) -> list:
    """获取指定会话的对话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        消息列表，包含 user/assistant/tool 类型消息
        - role: "user" | "assistant" | "tool"
        - content: 消息内容
        - tool_name: 工具名称（仅 tool 类型）
        - tool_calls: 工具调用信息（仅 assistant 调用工具时）
    """
    try:
        # 为每次查询单独打开 AsyncSqliteSaver 上下文
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            
            # 尝试获取检查点（异步）
            checkpoint = await memory.aget(config)
        if checkpoint and "channel_values" in checkpoint:
            messages = checkpoint["channel_values"].get("messages", [])
            result = []
            for msg in messages:
                msg_type = getattr(msg, "type", None)
                content = getattr(msg, "content", "")
                
                if msg_type == "human":
                    result.append({"role": "user", "content": content})
                elif msg_type == "ai":
                    # 检查是否有工具调用
                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        # 有工具调用的 AI 消息
                        result.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [
                                {"name": tc.get("name", ""), "args": tc.get("args", {})}
                                for tc in tool_calls
                            ]
                        })
                    else:
                        # 普通 AI 消息
                        result.append({"role": "assistant", "content": content})
                elif msg_type == "tool":
                    # 工具返回消息
                    tool_name = getattr(msg, "name", "unknown")
                    result.append({
                        "role": "tool",
                        "content": content,
                        "tool_name": tool_name
                    })
            
            return result
        return []
    except Exception as e:
        logger.error(f"[ChatAgent] 获取会话历史失败: {e}")
        return []
