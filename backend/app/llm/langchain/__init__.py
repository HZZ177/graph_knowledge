"""LangChain 相关模块

包含 LangChain Agent 配置、工具定义。
注意：get_langchain_llm 应从 llm.factory 导入。
"""

from backend.app.llm.langchain.agent import (
    create_chat_agent,
    get_agent_config,
    CHAT_SYSTEM_PROMPT,
)
from backend.app.llm.langchain.tools import get_all_chat_tools

__all__ = [
    "create_chat_agent",
    "get_agent_config",
    "get_all_chat_tools",
    "CHAT_SYSTEM_PROMPT",
]
