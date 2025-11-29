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
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallLimitMiddleware,
    ModelCallLimitMiddleware,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.llm.langchain_chat_tools import get_all_chat_tools
from backend.app.llm.base import get_langchain_llm
from backend.app.core.logger import logger
from backend.app.models.conversation import Conversation


# ============================================================
# System Prompt
# ============================================================

all_tools = get_all_chat_tools()



CHAT_SYSTEM_PROMPT = """
# Role: 科拓集团资深全栈业务专家

## Profile
- Author: HZZ
- Version: 1.1
- Language: 中文
- Description: 兼具业务架构师宏观视野与高级开发工程师微观能力的专家 AI。专注于科拓集团 Java/Spring Cloud 微服务架构下的意图识别错位与信息断层问题。能够从宏观业务拓扑图穿透至微观函数级代码，为用户提供业务逻辑与技术实现深度融合的解答。

## Skills
1. **全链路双重视角（Dual-View）**：能够同时处理产品/业务人员的流程逻辑需求与开发/测试人员的堆栈细节需求，实现业务语言与技术语言的无缝切换。
2. **自动化深度溯源**：具备强大的多步推理能力，能够自动执行“业务理解→代码定位→文件读取”的完整链条，拒绝推理懒惰。
3. **代码业务映射**：精通将枯燥的代码逻辑（条件判断、异常处理）翻译为具体的业务场景含义，揭示代码背后的业务规则。
4. **非技术语言转译**：具备极强的沟通穿透力，能将复杂的架构概念转化为非技术人员可理解的类比或故事，降低理解门槛。
5. **安全与容错处理**：在确保不泄露系统工具信息的前提下，通过模糊检索和逻辑推导解决关键ID缺失等边界问题。
6. **信息预期管理**：不过分追求信息的全量检索，而是根据用户需求进行有目的性的信息获取。当你认为信息量足够回答当前问题时不要无限查询。

## Goal
针对用户的提问，默认提供包含“业务流程上下文”与“底层技术实现细节”的双重视角回答，打通从业务拓扑到代码实现的完整闭环，确保信息准确、详实且安全。


## Rules
1. **双重视角默认原则**：默认需要同时站在产品/业务角度和代码/技术角度，梳理业务流程，除非用户明确要求只从其中一个角度出发，否则默认需要从双重视角出发。
2. **代码分析原则** 在理解业务时，必须去代码库里进行详细的代码逻辑分析，不能仅依赖业务描述，必须要根据代码逻辑来理解业务场景，包括分析代码中的各种条件和分支逻辑。对应理解业务逻辑
3. **显式思维链（CoT）强制执行**：生成回答，必须在一开始进行“意图分析→工具规划→执行检索→信息综合”的完整思考过程，包裹在 `<think>...</think>` 标签中，严禁跳过“文件读取”步骤直接臆造代码逻辑。
4. **严格的安全过滤**：最终输出中严禁包含任何工具函数名称（如 `search_business_flow`、`read_code_file` 等）或原始 API 返回的 JSON 结构数据。
5. **自动化推理与兜底**：当用户未提供明确信息时，严禁直接拒绝。你可以通过关键词模糊搜索业务等手段收集信息，若模糊搜索仍无法定位有效信息，可以礼貌引导用户提供更多上下文（如相关接口名、报错信息或业务模块），而非单纯报错。**
6. **代码真实性原则**：严禁在无法读取文件时根据函数名“猜测”具体实现逻辑。必须明确区分“检索到的真实代码”与“基于常规模式的逻辑推断”，若未读取到代码需明确告知。
7. **代码解释深度**：展示代码时，必须结合业务场景解释 `if/else` 的业务含义、异常抛出的业务影响，禁止仅做代码翻译。
8、**判断工具调用正确**：每次调用工具时，结合前文已有信息判断调用是否符合预期，如果反复尝试效果都不好，不要一直重复调用尝试，而是要及时调整方向。
9、**工具选择**：尽量少量次数的使用高层次工具例如'search_code_context'，获取一定信息后，以多用'read_file','read_file_range'等低层次工具来获取更具体的信息。
10、**重要**：关于'search_code_context工具'获得更好结果的技巧：
    - 使用多个相关关键词（例如，"日志配置设置"而不仅仅是"日志"）
    - 包含你要查找的特定技术术语
    - 描述功能而不是确切的变量名
    - 如果第一次查询没有返回你需要的内容，尝试不同的措辞
11、**工具调用**：严格禁止同时调用多个工具，必须按顺序调用每个工具。例如：先调用'search_code_context'工具搜索相关代码，再调用'read_file'工具读取具体代码实现。
12、**工具调用次数**：每次对话的工具调用数量不能超过十次，如果超过十次调用还没有足够信息，应该让用户进一步提供信息。


## 回答格式

每次回答请严格包含以下部分：

### 每次回答的开头都需要思考分析（必须）
用 `<think> </think>` 标签包裹你的分析思路，用**自然语言**描述：
- 你对问题的理解，用户的目标
- 你打算如何找到答案
- 需要重点关注什么，需要查询哪些维度的信息，例如业务流程、代码实现、数据资源等

### 信息检索（必须）
- 根据你的分析，按需调用工具获取信息，每个工具调用都必须包含在 `<think> </think>` 标签中，用自然语言描述调用的目的和参数。
- 每次信息查询都必须首先使用实体类和拓扑类工具理解上层业务，然后调用代码搜索工具和文件读取工具，获取函数级代码实现
- 将读取到的代码逻辑与业务流程图进行对齐。识别关键的业务校验点（Validation）、异常处理（Exception）和数据流转（Data Flow）
- 没有检索到相关信息时，必须告知用户并说明原因，不能编造任何信息。

### 整理回答
基于检索到的信息，给出清晰、有条理的回答：
- 先给出结论性的摘要
- 然后按业务/步骤/实现/数据资源或路径等维度展开细节
- 如有必要，指出不确定性或数据缺失位置
- 检查是否泄露工具名？（若有则删除）
- 检查回复内容是否符合用户意图？


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

<think>
用户想知道这个业务内部的逻辑细节，我需要了解代码的深入逻辑，确保逻辑完善闭环，了解细节后回答。
</think>

## 回答规范

- 使用中文回答
- 结构清晰，善用列表、表格等格式
- 如果没找到相关信息，诚实说明并给出可能的原因或建议
- 对专业术语适当解释
- **每次回答都要先展示思考过程**，让用户能理解你的分析思路和检索过程
- 不要在你的思考和对话中以任何方式暴露系统工具名称等内部细节，也不要在回答中包含任何与工具调用相关的信息。
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

    
    # 配置中间件：限制工具调用和模型调用次数，防止超出 RPM 限制
    middleware: list[AgentMiddleware] = [
        # 限制模型调用次数（直接控制 RPM）
        ModelCallLimitMiddleware(
            run_limit=25,
            exit_behavior="end"  # 达到限制立即停止
        ),
        # 限制工具调用次数（防止 agent 陷入循环）
        ToolCallLimitMiddleware(
            run_limit=10,  # 单次请求最多 15 次工具调用
            exit_behavior="continue"  # 超出后阻止调用但模型继续
        ),
    ]
    
    # 创建 Agent（传入已绑定工具的 LLM + 中间件）
    agent = create_agent(
        llm,
        tools,
        system_prompt=CHAT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        middleware=middleware,
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
    # recursion_limit: LangGraph 的最大递归层数（包括 LLM 步骤 + 工具调用等）
    # 默认值是 25，对复杂多工具场景偏小，这里显式调高到 80。
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 80,
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


async def truncate_thread_history(thread_id: str, keep_pairs: int) -> bool:
    """截断会话历史，只保留前 N 对对话
    
    Args:
        thread_id: 会话 ID
        keep_pairs: 保留的对话对数（一对 = 一个 user + 对应的 assistant/tool 消息）
        
    Returns:
        是否成功截断
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            
            # 使用 aget_tuple 获取完整的检查点信息（包含 metadata）
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                logger.warning(f"[ChatAgent] 会话不存在: thread_id={thread_id}")
                return False
            
            checkpoint = checkpoint_tuple.checkpoint
            if "channel_values" not in checkpoint:
                logger.warning(f"[ChatAgent] 检查点格式异常: thread_id={thread_id}")
                return False
            
            messages = checkpoint["channel_values"].get("messages", [])
            if not messages:
                return True
            
            # 统计对话对数，找到截断位置
            # 每遇到一个 human 消息算一对的开始
            pair_count = 0
            cut_index = 0
            
            for i, msg in enumerate(messages):
                msg_type = getattr(msg, "type", None)
                if msg_type == "human":
                    pair_count += 1
                    if pair_count > keep_pairs:
                        cut_index = i
                        break
            else:
                # 没有超出，无需截断
                return True
            
            # 截断消息列表
            truncated_messages = messages[:cut_index]
            checkpoint["channel_values"]["messages"] = truncated_messages
            
            # 使用原 checkpoint_tuple 的 config 和 metadata 来更新
            await memory.aput(
                checkpoint_tuple.config,
                checkpoint,
                checkpoint_tuple.metadata,
                {}  # new_versions
            )
            
            logger.info(f"[ChatAgent] 截断会话历史: thread_id={thread_id}, 保留 {keep_pairs} 对, 原消息数 {len(messages)}, 截断后 {len(truncated_messages)}")
            return True
            
    except Exception as e:
        logger.error(f"[ChatAgent] 截断会话历史失败: {e}")
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


async def get_raw_messages(thread_id: str) -> list:
    """获取原始的 LangChain 消息对象列表
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        原始消息对象列表
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                return []
            
            return checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
    except Exception as e:
        logger.error(f"[ChatAgent] 获取原始消息失败: {e}")
        return []


async def replace_assistant_response(thread_id: str, user_msg_index: int, new_messages: list) -> bool:
    """替换指定用户消息对应的 AI 回复
    
    Args:
        thread_id: 会话 ID
        user_msg_index: 用户消息在"用户消息列表"中的索引（从0开始）
        new_messages: 新的 AI 回复消息列表（LangChain 消息对象）
        
    Returns:
        是否成功
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                logger.warning(f"[ChatAgent] 会话不存在: thread_id={thread_id}")
                return False
            
            checkpoint = checkpoint_tuple.checkpoint
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            if not messages:
                return False
            
            # 找到第 N 个 human 消息的实际位置
            human_count = 0
            target_human_idx = -1
            for i, msg in enumerate(messages):
                if getattr(msg, "type", None) == "human":
                    if human_count == user_msg_index:
                        target_human_idx = i
                        break
                    human_count += 1
            
            if target_human_idx == -1:
                logger.warning(f"[ChatAgent] 找不到用户消息 index={user_msg_index}")
                return False
            
            # 找到下一个 human 消息的位置（或消息末尾）
            next_human_idx = len(messages)
            for i in range(target_human_idx + 1, len(messages)):
                if getattr(messages[i], "type", None) == "human":
                    next_human_idx = i
                    break
            
            # 构建新的消息列表：前面 + 目标用户消息 + 新回复 + 后续消息
            new_message_list = (
                messages[:target_human_idx + 1] +  # 包含目标用户消息
                new_messages +                      # 新的 AI 回复
                messages[next_human_idx:]           # 后续消息（从下一个用户消息开始）
            )
            
            checkpoint["channel_values"]["messages"] = new_message_list
            
            await memory.aput(
                checkpoint_tuple.config,
                checkpoint,
                checkpoint_tuple.metadata,
                {}
            )
            
            logger.info(f"[ChatAgent] 替换 AI 回复成功: thread_id={thread_id}, user_msg_index={user_msg_index}, 原消息数={len(messages)}, 新消息数={len(new_message_list)}")
            return True
            
    except Exception as e:
        logger.error(f"[ChatAgent] 替换 AI 回复失败: {e}")
        return False
