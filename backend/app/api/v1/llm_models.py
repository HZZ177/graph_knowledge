from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session
from crewai import LLM, Agent, Task, Crew, Process

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

    try:
        if "/" in payload.model_name or not payload.provider:
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

        tester = Agent(
            role="LLM Connectivity Tester",
            goal="验证模型是否可以正常返回简单回答",
            backstory="专门用于测试 LLM 配置是否可用的助手。",
            llm=llm,
        )

        task = Task(
            description="请用极短的中文回答：ok。",
            agent=tester,
            expected_output="一个非常短的回答，例如：ok。",
        )

        crew = Crew(
            agents=[tester],
            tasks=[task],
            process=Process.sequential,
            llm=llm,
        )

        result = crew.kickoff()
        return success_response(
            data={"ok": True, "result": str(result)},
            message="测试成功",
        )
    except Exception as exc:
        return error_response(
            message=f"模型测试失败: {exc}",
            data={"ok": False},
        )
