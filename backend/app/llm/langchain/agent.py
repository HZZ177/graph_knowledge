"""LangChain Chat Agent 配置

使用 LangChain + LangGraph 实现支持多轮对话的 Chat Agent。

核心特性：
- 基于 AgentRegistry 单例管理多类型 Agent
- 支持懒加载 + 配置变更检测
- 通过 thread_id 区分不同会话
- 支持流式输出

新架构（推荐）：
    from backend.app.llm.langchain.registry import AgentRegistry, get_agent_run_config
    
    registry = AgentRegistry.get_instance()
    agent = registry.get_agent("knowledge_qa", db)
    config = get_agent_run_config(thread_id, checkpointer)
    
旧接口（向后兼容，但不推荐）：
    from backend.app.llm.langchain.agent import create_chat_agent, get_agent_config
"""

import warnings
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.core.logger import logger

# 从新模块导入，保持向后兼容
from backend.app.llm.langchain.configs import (
    KNOWLEDGE_QA_SYSTEM_PROMPT as CHAT_SYSTEM_PROMPT,  # 向后兼容别名
    list_agent_configs,
)
from backend.app.llm.langchain.registry import (
    AgentRegistry,
    get_agent_run_config,
)


# ============================================================
# 向后兼容接口（Deprecated）
# ============================================================

def create_chat_agent(db: Session, checkpointer: Optional[AsyncSqliteSaver] = None):
    """创建 Chat Agent（已废弃，请使用 AgentRegistry）
    
    .. deprecated::
        此函数已废弃，请使用 AgentRegistry.get_instance().get_agent() 代替。
        新接口支持缓存复用，避免每次请求重复编译 Agent。
    
    Args:
        db: 数据库会话（用于获取 LLM 配置）
        checkpointer: 可选的检查点存储（用于持久化对话历史）
        
    Returns:
        配置好的 LangGraph Agent
    """
    warnings.warn(
        "create_chat_agent 已废弃，请使用 AgentRegistry.get_instance().get_agent() 代替。"
        "新接口支持缓存复用，避免每次请求重复编译 Agent。",
        DeprecationWarning,
        stacklevel=2,
    )
    
    # 使用新的 Registry 获取 Agent
    registry = AgentRegistry.get_instance()
    agent = registry.get_agent("knowledge_qa", db)
    
    logger.info("[ChatAgent] 通过兼容接口获取 Agent（建议迁移到 AgentRegistry）")
    return agent


def get_agent_config(thread_id: str) -> Dict[str, Any]:
    """获取 Agent 执行配置（向后兼容）
    
    Args:
        thread_id: 会话 ID，用于区分不同对话
        
    Returns:
        Agent 配置字典
    """
    return get_agent_run_config(thread_id)
