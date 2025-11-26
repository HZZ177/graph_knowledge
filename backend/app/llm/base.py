from typing import Union

from sqlalchemy.orm import Session
from crewai import LLM, BaseLLM

from backend.app.services.ai_model_service import AIModelService
from backend.app.llm.custom_llm import CustomGatewayLLM
from backend.app.llm.config import get_provider_base_url
from backend.app.core.logger import logger


def get_crewai_llm(db: Session) -> Union[LLM, BaseLLM]:
    """基于当前激活的 AIModel 构造 LLM 实例。
    
    根据 provider_type 返回不同类型的 LLM：
    - litellm: 使用 CrewAI 内置的 LLM 类（基于 LiteLLM）
    - custom_gateway: 使用自定义的 CustomGatewayLLM（支持 NewAPI 等网关）
    
    Args:
        db: 数据库会话
        
    Returns:
        LLM 实例（LLM 或 CustomGatewayLLM）
    """
    config = AIModelService.get_active_llm_config(db)
    
    if config.provider_type == "custom_gateway":
        # 自定义网关模式
        if not config.gateway_endpoint:
            raise ValueError("custom_gateway 模式下必须配置 gateway_endpoint")
        
        logger.info(f"[LLM] 创建自定义网关LLM: model={config.model_name}, endpoint={config.gateway_endpoint}")
        logger.debug(f"[LLM] temperature={config.temperature}, max_tokens={config.max_tokens}, timeout={config.timeout}")
        
        llm = CustomGatewayLLM(
            model=config.model_name,
            api_key=config.api_key,
            endpoint=config.gateway_endpoint,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        )
        
        logger.info("[LLM] 自定义网关LLM实例创建成功")
        return llm
    
    else:
        # LiteLLM 模式
        # 仅在 provider 非空时拼接前缀
        if config.provider:
            model_full_name = f"{config.provider}/{config.model_name}"
        else:
            model_full_name = config.model_name

        # 自动获取提供商的 base_url（如果用户未手动指定）
        base_url = config.base_url
        if not base_url and config.provider:
            base_url = get_provider_base_url(config.provider)

        logger.info(f"[LLM] 创建LiteLLM实例: model={model_full_name}, base_url={base_url}")
        logger.debug(f"[LLM] temperature={config.temperature}, max_tokens={config.max_tokens}")

        llm = LLM(
            model=model_full_name,
            api_key=config.api_key,
            base_url=base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            verbose=False,
        )
        
        logger.info("[LLM] LiteLLM实例创建成功")
        return llm
