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


class CodeWorkspaceConfig(BaseModel):
    """代码工作区配置
    
    为代码相关工具提供统一的项目根目录配置，限制工具只读访问该目录内的文件。
    使用在此处硬编码配置的项目根目录，用于访问外部代码库。
    """

    project_root: str

    @classmethod
    def load(cls) -> "CodeWorkspaceConfig":
        """从固定配置的字符串路径加载项目根目录。"""
        # 注意：这里的路径需要根据实际外部代码库位置进行配置
        # 当前默认与 AceCodeEngineMcp._default_project_root 保持一致
        fixed_root = os.path.abspath(r"D:\Vivaldi下载")
        return cls(project_root=fixed_root)

    @classmethod
    def get_project_root(cls) -> str:
        """获取项目根目录的绝对路径。"""
        return cls.load().project_root
