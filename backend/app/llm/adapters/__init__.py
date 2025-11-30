"""LLM 适配层

包含不同框架的 LLM 适配器：
- crewai_gateway: CrewAI 自定义网关 LLM
- langchain_patched: LangChain ChatOpenAI 补丁
"""

from backend.app.llm.adapters.crewai_gateway import CustomGatewayLLM
from backend.app.llm.adapters.langchain_patched import PatchedChatOpenAI

__all__ = [
    "CustomGatewayLLM",
    "PatchedChatOpenAI",
]
