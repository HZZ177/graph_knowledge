from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float

from backend.app.db.sqlite import Base


class AIModel(Base):
    """LLM 模型配置表，对应 ai_models。

    所有大模型调用所需的 provider / model_name / api_key / base_url / 温度 等信息
    都存储在本表中，通过 Service + LLMConfig 暴露给上层使用。
    """

    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, comment="模型配置名称")
    provider = Column(String, nullable=False, comment="提供商标识，如 openai、anthropic 等")
    model_name = Column(String, nullable=False, comment="模型名称，如 gpt-4.1-mini")
    api_key = Column(Text, nullable=False, comment="API Key")
    base_url = Column(Text, nullable=True, comment="可选，自定义 Base URL")
    temperature = Column(Float, nullable=False, default=0.7, comment="默认温度")
    max_tokens = Column(Integer, nullable=True, comment="最大输出 token 数，可为空")
    is_active = Column(Boolean, nullable=False, default=False, comment="是否为当前激活模型")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
