from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session
from crewai import LLM

from backend.app.db.sqlite import get_db
from backend.app.schemas.ai_models import (
    AIModelCreate,
    AIModelUpdate,
    AIModelOut,
    ActivateAIModelRequest,
    AIModelTestRequest,
)
from backend.app.services.ai_model_service import AIModelService
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/llm-models", tags=["llm-models"])


@router.get("/list", response_model=list[AIModelOut])
async def list_llm_models(db: Session = Depends(get_db)) -> dict:
    models = AIModelService.list_models(db)
    data = [AIModelOut.from_orm(m) for m in models]
    return success_response(data=data)


@router.post("/create", response_model=AIModelOut)
async def create_llm_model(
    payload: AIModelCreate = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        obj = AIModelService.create_model(db, payload)
    except ValueError as exc:
        return error_response(message=str(exc))
    return success_response(data=AIModelOut.from_orm(obj))


@router.post("/update", response_model=AIModelOut)
async def update_llm_model(
    model_id: int = Query(...),
    payload: AIModelUpdate = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    obj = AIModelService.update_model(db, model_id, payload)
    if not obj:
        return error_response(message="Not found")
    return success_response(data=AIModelOut.from_orm(obj))


@router.post("/delete")
async def delete_llm_model(
    model_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict:
    try:
        ok = AIModelService.delete_model(db, model_id)
    except ValueError as exc:
        return error_response(message=str(exc))
    if not ok:
        return error_response(message="Not found")
    return success_response(message="删除模型成功")


@router.post("/activate")
async def activate_llm_model(
    payload: ActivateAIModelRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    obj = AIModelService.set_active_model(db, payload.id)
    if not obj:
        return error_response(message="Not found")
    return success_response(message="激活模型成功")


@router.post("/test")
async def test_llm_model(
    payload: AIModelTestRequest = Body(...),
) -> dict:
    """测试给定模型配置是否可用，不写入数据库。"""

    model_full_name = payload.model_name
    safe_payload = {
        "name": payload.name,
        "provider": payload.provider,
        "model_name": payload.model_name,
        "base_url": payload.base_url,
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }
    logger.info(f"开始测试 LLM 模型配置: {safe_payload}")

    try:
        if not payload.provider:
            model_full_name = payload.model_name
        else:
            model_full_name = f"{payload.provider}/{payload.model_name}"

        llm = LLM(
            model=model_full_name,
            api_key=payload.api_key,
            base_url=payload.base_url,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )

        # 直接用 LLM 发起一次最简单的对话，验证连通性
        prompt = "请用极短的中文回答：ok。"
        result = llm.call(prompt)

        logger.info(f"模型测试成功 model={model_full_name}")
        return success_response(
            data={"ok": True, "result": str(result)},
            message="测试成功",
        )
    except Exception as exc:
        logger.error(f"模型测试失败 model={model_full_name}, error={exc}")
        return error_response(
            message=f"模型测试失败: {exc}",
            data={"ok": False},
        )


@router.post("/test-by-id")
async def test_llm_model_by_id(
    model_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict:
    """基于已保存的配置（数据库）测试模型连通性。"""

    logger.info(f"开始测试已保存的 LLM 模型配置 id={model_id}")

    obj = AIModelService.get_model_by_id(db, model_id)
    if not obj:
        logger.warning(f"测试模型失败，配置不存在 id={model_id}")
        return error_response(
            message="Not found",
            data={"ok": False},
        )

    if not obj.provider:
        model_full_name = obj.model_name
    else:
        model_full_name = f"{obj.provider}/{obj.model_name}"

    try:
        llm = LLM(
            model=model_full_name,
            api_key=obj.api_key,
            base_url=obj.base_url,
            temperature=obj.temperature,
            max_tokens=obj.max_tokens,
        )

        prompt = "请用极短的中文回答：ok。"
        result = llm.call(prompt)

        logger.info(f"模型测试成功（已保存配置） id={model_id}, model={model_full_name}")
        return success_response(
            data={"ok": True, "result": str(result)},
            message="测试成功",
        )
    except Exception as exc:
        logger.error(
            f"模型测试失败（已保存配置） id={model_id}, model={model_full_name}, error={exc}"
        )
        return error_response(
            message=f"模型测试失败: {exc}",
            data={"ok": False},
        )
