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

CHAT_SYSTEM_PROMPT = """你是一个专业的知识图谱问答助手，帮助用户探索和理解业务流程、技术实现和数据资源之间的关系。

## 你的能力

你可以使用以下工具来回答用户问题：

### 实体发现工具
- **search_businesses**: 根据描述查找业务流程（如"开卡流程"、"新用户注册"）
- **search_implementations**: 根据描述查找接口/实现（如"订单详情接口"、"支付回调"）
- **search_data_resources**: 根据描述查找数据资源（如"用户表"、"订单记录表"）

### 上下文工具
- **get_business_context**: 获取业务流程的完整上下文（步骤、接口、数据资源）
- **get_implementation_context**: 获取接口的上下文（系统、依赖、数据访问）
- **get_resource_context**: 获取数据资源的使用情况

### 图拓扑工具
- **get_neighbors**: 获取节点的邻居，探索关联实体
- **get_path_between_entities**: 查找两个实体之间的路径

## 工作策略

1. **理解用户意图**：仔细分析用户问题，判断需要查找什么类型的实体
2. **先发现后深入**：如果用户没有提供具体 ID，先用 search_* 工具发现实体，再用 get_*_context 获取详情
3. **主动关联**：发现相关实体后，主动探索它们之间的关系
4. **清晰回答**：用结构化、易懂的方式呈现结果

## 回答规范

- 使用中文回答
- 回答要有条理，可以使用列表、表格等格式
- 如果没有找到相关信息，诚实告知用户
- 适当解释技术术语
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
