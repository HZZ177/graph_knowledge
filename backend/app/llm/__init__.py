"""LLM 模块

提供向后兼容的导入，新代码请使用子模块导入。

目录结构：
- factory.py: LLM 实例工厂
- config.py: 配置
- adapters/: LLM 适配层（CrewAI 网关、LangChain 补丁）
- crewai/: CrewAI Agent/Task/流式输出
- langchain/: LangChain Agent/工具
"""

# 向后兼容导入
from backend.app.llm.factory import (
    get_crewai_llm,
    get_langchain_llm,
    get_lite_task_llm,
)
from backend.app.llm.adapters.crewai_gateway import CustomGatewayLLM
from backend.app.llm.adapters.langchain_patched import PatchedChatOpenAI
from backend.app.llm.crewai.agents import CrewAiAgents
from backend.app.llm.crewai.tasks import CrewAiTasks
from backend.app.llm.crewai.streaming import run_agent_stream
from backend.app.llm.langchain.agent import (
    create_chat_agent,
    get_agent_config,
    CHAT_SYSTEM_PROMPT,
)
from backend.app.llm.langchain.tools import get_all_chat_tools

__all__ = [
    # Factory
    "get_crewai_llm",
    "get_langchain_llm",
    "get_lite_task_llm",
    # Adapters
    "CustomGatewayLLM",
    "PatchedChatOpenAI",
    # CrewAI
    "CrewAiAgents",
    "CrewAiTasks",
    "run_agent_stream",
    # LangChain
    "create_chat_agent",
    "get_agent_config",
    "get_all_chat_tools",
    "CHAT_SYSTEM_PROMPT",
]
