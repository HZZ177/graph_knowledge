from datetime import datetime

from pydantic import BaseModel, Field


class AIModelBase(BaseModel):
    name: str = Field(..., description="配置名称")
    provider: str | None = Field(None, description="提供商标识，可选")
    model_name: str = Field(..., description="模型名称")
    base_url: str | None = Field(None, description="可选 Base URL")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    max_tokens: int | None = Field(None, description="最大输出 tokens")


class AIModelCreate(AIModelBase):
    api_key: str = Field(..., description="API Key")


class AIModelUpdate(AIModelBase):
    api_key: str | None = Field(None, description="可选，若为空则不更新")


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
