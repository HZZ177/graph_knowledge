from sqlalchemy.orm import Session
from crewai import LLM

from backend.app.services.ai_model_service import AIModelService


def get_crewai_llm(db: Session) -> LLM:
    """基于当前激活的 AIModel 构造一个 crewai.LLM 实例。"""

    config = AIModelService.get_active_llm_config(db)

    # 仅在 provider 非空且 model_name 未自带前缀时拼接
    model_full_name = f"{config.provider}/{config.model_name}"

    llm = LLM(
        model=model_full_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    return llm
