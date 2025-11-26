from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AIModelBase(BaseModel):
    """AI 模型配置基类
    
    支持两种模式：
    - litellm: 使用 LiteLLM 内置支持（需要 provider）
    - custom_gateway: 使用自定义网关如 NewAPI（需要 gateway_endpoint）
    """
    name: str = Field(..., description="配置名称")
    provider_type: Literal["litellm", "custom_gateway"] = Field(
        "litellm", 
        description="提供商类型: litellm（使用LiteLLM）或 custom_gateway（自定义网关）"
    )
    provider: str | None = Field(None, description="提供商标识（litellm模式），如 openai、anthropic")
    model_name: str = Field(..., description="模型名称")
    base_url: str | None = Field(None, description="Base URL（litellm模式，可选代理地址）")
    gateway_endpoint: str | None = Field(
        None, 
        description="网关端点URL（custom_gateway模式），如 https://your-newapi.com/v1/chat/completions"
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    max_tokens: int | None = Field(None, description="最大输出 tokens")
    timeout: int = Field(120, ge=10, le=600, description="请求超时（秒）")
    
    @model_validator(mode='after')
    def validate_provider_config(self):
        """验证不同模式下的必填字段"""
        if self.provider_type == "custom_gateway":
            if not self.gateway_endpoint:
                raise ValueError("custom_gateway 模式下必须提供 gateway_endpoint")
        return self


class AIModelCreate(AIModelBase):
    api_key: str = Field(..., description="API Key")


class AIModelUpdate(BaseModel):
    """更新模型配置，所有字段可选"""
    name: str | None = Field(None, description="配置名称")
    provider_type: Literal["litellm", "custom_gateway"] | None = Field(None, description="提供商类型")
    provider: str | None = Field(None, description="提供商标识")
    model_name: str | None = Field(None, description="模型名称")
    base_url: str | None = Field(None, description="Base URL")
    gateway_endpoint: str | None = Field(None, description="网关端点URL")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="温度")
    max_tokens: int | None = Field(None, description="最大输出 tokens")
    timeout: int | None = Field(None, ge=10, le=600, description="请求超时（秒）")
    api_key: str | None = Field(None, description="API Key，为空则不更新")


class AIModelOut(AIModelBase):
    id: int
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class ActivateAIModelRequest(BaseModel):
    id: int


class AIModelTestRequest(AIModelBase):
    """用于测试模型连通性的请求体，不会写入数据库。"""
    api_key: str = Field(..., description="用于测试的 API Key")
