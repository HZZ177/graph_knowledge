"""LLM 实例工厂

统一的 LLM 实例创建入口：
- get_crewai_llm: 创建 CrewAI LLM 实例
- get_langchain_llm: 创建 LangChain ChatOpenAI 实例
- get_lite_task_llm: 创建轻量任务 LLM 实例（低温度，用于工具内部快速调用）
"""

from typing import Union, Optional

from sqlalchemy.orm import Session
from crewai import LLM, BaseLLM

from backend.app.services.ai_model_service import AIModelService
from backend.app.llm.adapters.crewai_gateway import CustomGatewayLLM
from backend.app.llm.adapters.langchain_patched import PatchedChatOpenAI
from backend.app.llm.config import get_provider_base_url
from backend.app.core.logger import logger



def get_langchain_llm(db: Session) -> PatchedChatOpenAI:
    """基于当前激活的 AIModel 构造 LangChain ChatOpenAI 实例
    
    使用 PatchedChatOpenAI 修复流式响应中 tool_call index 字段错误的问题。
    某些 API 网关返回的 index 全为 0，会导致多个工具调用被错误合并。
    
    Args:
        db: 数据库会话
        
    Returns:
        PatchedChatOpenAI 实例
    """
    config = AIModelService.get_active_llm_config(db)
    
    # 自定义网关模式
    if config.provider_type == "custom_gateway" and config.gateway_endpoint:
        base_url = config.gateway_endpoint.rstrip("/")
        # ChatOpenAI 会自动追加 /chat/completions，因此如果 endpoint 已经包含了该路径，需要移除
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-17]  # len("/chat/completions") == 17
        elif base_url.endswith("/chat/completions/"):
            base_url = base_url[:-18]
        
        # 确保 base_url 以 /v1 结尾
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        
        logger.info(f"[LangChainLLM] 自定义网关模式: model={config.model_name}, base={base_url}")
        return PatchedChatOpenAI(
            model=config.model_name,
            api_key=config.api_key,
            base_url=base_url,
            temperature=config.temperature,
            streaming=True,
        )
    
    # 标准模式：使用 provider 的 base_url
    base_url = config.base_url
    if not base_url and config.provider:
        base_url = get_provider_base_url(config.provider)
    
    logger.info(f"[LangChainLLM] 标准模式: model={config.model_name}, base={base_url}")
    
    return PatchedChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=base_url,
        temperature=config.temperature,
        streaming=True,
    )


def get_crewai_llm(db: Session) -> Union[LLM, BaseLLM]:
    """基于当前激活的 AIModel 构造 CrewAI LLM 实例
    
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


def get_lite_task_llm(db: Session) -> PatchedChatOpenAI:
    """基于小任务模型配置构造轻量 LLM 实例
    
    用于工具内部快速调用（如实体选择器），固定低温度保证输出稳定。
    未设置小任务模型时自动 fallback 到主力模型。
    
    Args:
        db: 数据库会话
        
    Returns:
        PatchedChatOpenAI 实例（temperature=0.1, max_tokens=2000）
    """
    config = AIModelService.get_task_llm_config(db)
    
    # 自定义网关模式
    if config.provider_type == "custom_gateway" and config.gateway_endpoint:
        base_url = config.gateway_endpoint.rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-17]
        elif base_url.endswith("/chat/completions/"):
            base_url = base_url[:-18]
        
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        
        logger.debug(f"[LiteTaskLLM] 自定义网关模式: model={config.model_name}, base={base_url}")
        return PatchedChatOpenAI(
            model=config.model_name,
            api_key=config.api_key,
            base_url=base_url,
            temperature=0.1,
            max_tokens=2000,
            streaming=False,
        )
    
    # 标准模式
    base_url = config.base_url
    if not base_url and config.provider:
        base_url = get_provider_base_url(config.provider)
    
    logger.debug(f"[LiteTaskLLM] 标准模式: model={config.model_name}, base={base_url}")
    
    return PatchedChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=base_url,
        temperature=0.1,
        max_tokens=2000,
        streaming=False,
    )
