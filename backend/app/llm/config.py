from enum import Enum
from typing import Literal, Optional

import os

from pydantic import BaseModel


class ProviderType(str, Enum):
    """LLM 提供商类型"""
    LITELLM = "litellm"  # 使用 LiteLLM 内置支持的提供商
    CUSTOM_GATEWAY = "custom_gateway"  # 自定义网关（如 NewAPI）


def get_provider_base_url(provider: str) -> Optional[str]:
    """获取提供商的默认 Base URL"""
    # LiteLLM 内置提供商的 Base URL 映射
    # 参考: https://docs.litellm.ai/docs/providers
    provider_base_urls: dict[str, str] = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "cohere": "https://api.cohere.ai/v1",
        "mistral": "https://api.mistral.ai/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "ollama": "http://localhost:11434",
    }
    return provider_base_urls.get(provider)


class LLMConfig(BaseModel):
    """LLM 配置
    
    支持两种模式：
    1. litellm: 使用 LiteLLM 内置的提供商支持（OpenAI、Anthropic 等）
    2. custom_gateway: 使用自定义网关（如 NewAPI），需要提供完整的 endpoint
    
    Examples:
        # LiteLLM 模式
        LLMConfig(
            provider_type="litellm",
            provider="openai",
            model_name="gpt-4",
            api_key="sk-xxx",
        )
        
        # 自定义网关模式
        LLMConfig(
            provider_type="custom_gateway",
            model_name="gpt-4",
            api_key="sk-xxx",
            gateway_endpoint="https://your-newapi.com/v1/chat/completions",
        )
    """
    # 提供商类型：litellm 或 custom_gateway
    provider_type: Literal["litellm", "custom_gateway"] = "litellm"
    
    # LiteLLM 模式下的提供商标识（如 openai、anthropic）
    provider: str | None = None
    
    # 模型名称
    model_name: str
    
    # LiteLLM 模式下的 base_url（可选，用于代理）
    base_url: str | None = None
    
    # API 密钥
    api_key: str
    
    # 自定义网关的完整端点 URL（provider_type=custom_gateway 时必填）
    gateway_endpoint: str | None = None
    
    # 温度参数
    temperature: float = 0.7
    
    # 最大输出 token 数
    max_tokens: int | None = None
    
    # 请求超时（秒）
    timeout: int = 120


class WorkspaceInfo(BaseModel):
    """单个代码工作区信息"""
    key: str              # 工作区标识符
    name: str             # 显示名称
    root: str             # 项目根目录路径
    description: str      # 工作区描述（用于 Agent 理解）


class CodeWorkspaceConfig:
    """代码工作区配置
    
    为代码相关工具提供多工作区配置，支持在多个代码库之间切换。
    AI Agent 可根据上下文选择正确的代码库进行搜索和文件读取。
    """
    
    # ============================================================
    # 多代码库配置（在此添加需要支持的代码库）
    # ============================================================
    WORKSPACES: dict[str, dict] = {
        "vehicle-owner-server": {
            "name": "C端逻辑服务",
            "root": r"C:\Users\86364\PycharmProjects\vehicle-owner-server",
            "description": "C端逻辑服务，主要包含非后台相关的owner-center和pay-center两大业务模块"
        },
        "vehicle-admin": {
            "name": "C端后台服务",
            "root": r"C:\Users\86364\PycharmProjects\yongce-pro-admin-vehicle-owner",
            "description": "C端后台服务，主要包含后台管理相关的业务模块"
        },
    }
    
    @classmethod
    def get_workspace_root(cls, workspace: Optional[str] = None) -> str:
        """获取指定工作区的项目根目录绝对路径。
        
        Args:
            workspace: 工作区标识符，必须指定
            
        Returns:
            项目根目录的绝对路径
            
        Raises:
            ValueError: 未指定工作区或未知的工作区标识符
        """
        if not workspace:
            available = list(cls.WORKSPACES.keys())
            raise ValueError(f"必须指定 workspace 参数，可用工作区: {available}")
        ws_config = cls.WORKSPACES.get(workspace)
        if not ws_config:
            available = list(cls.WORKSPACES.keys())
            raise ValueError(f"未知工作区: {workspace}，可用工作区: {available}")
        return os.path.abspath(ws_config["root"])
    
    @classmethod
    def list_workspaces(cls) -> list[WorkspaceInfo]:
        """列出所有配置的工作区。
        
        Returns:
            工作区信息列表
        """
        return [
            WorkspaceInfo(key=k, **v)
            for k, v in cls.WORKSPACES.items()
        ]
    
    @classmethod
    def get_workspace_description(cls) -> str:
        """生成工作区描述文本，用于 Agent System Prompt。"""
        lines = []
        for key, ws in cls.WORKSPACES.items():
            lines.append(f"  - `{key}`: {ws['name']} - {ws['description']}")
        return "\n".join(lines)
    
    @classmethod
    def get_available_workspace_keys(cls) -> list[str]:
        """获取所有可用的工作区标识符列表。"""
        return list(cls.WORKSPACES.keys())
