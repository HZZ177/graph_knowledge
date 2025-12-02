"""LangChain 相关模块

包含 LangChain Agent 配置、工具定义、Agent 注册表。
注意：get_langchain_llm 应从 llm.factory 导入。

新架构（推荐）：
    from backend.app.llm.langchain import AgentRegistry, get_agent_run_config
    
    registry = AgentRegistry.get_instance()
    agent = registry.get_agent("knowledge_qa", db)
"""

# 新架构导出
from backend.app.llm.langchain.registry import (
    AgentRegistry,
    get_agent_run_config,
)
from backend.app.llm.langchain.configs import (
    AgentConfig,
    AGENT_CONFIGS,
    get_agent_config as get_agent_type_config,
    list_agent_configs,
    KNOWLEDGE_QA_SYSTEM_PROMPT,
)

# 向后兼容导出（Deprecated）
from backend.app.llm.langchain.agent import (
    create_chat_agent,
    get_agent_config,
    CHAT_SYSTEM_PROMPT,
)
from backend.app.llm.langchain.tools import get_all_chat_tools

__all__ = [
    # 新架构
    "AgentRegistry",
    "get_agent_run_config",
    "AgentConfig",
    "AGENT_CONFIGS",
    "get_agent_type_config",
    "list_agent_configs",
    "KNOWLEDGE_QA_SYSTEM_PROMPT",
    # 向后兼容（Deprecated）
    "create_chat_agent",
    "get_agent_config",
    "get_all_chat_tools",
    "CHAT_SYSTEM_PROMPT",
]
