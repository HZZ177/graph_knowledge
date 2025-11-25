import os
from sqlalchemy.orm import Session
from crewai import LLM

from backend.app.services.ai_model_service import AIModelService
from backend.app.core.logger import logger

# 开启CrewAI调试模式
os.environ["CREWAI_DEBUG"] = "true"


def get_crewai_llm(db: Session) -> LLM:
    """基于当前激活的 AIModel 构造一个 crewai.LLM 实例。"""

    config = AIModelService.get_active_llm_config(db)

    # 仅在 provider 非空且 model_name 未自带前缀时拼接
    model_full_name = f"{config.provider}/{config.model_name}"

    logger.info(f"[LLM] 创建LLM实例: model={model_full_name}, base_url={config.base_url}")
    logger.debug(f"[LLM] temperature={config.temperature}, max_tokens={config.max_tokens}")

    llm = LLM(
        model=model_full_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        verbose=True,  # 开启详细日志
    )
    
    logger.info(f"[LLM] LLM实例创建成功")
    return llm
