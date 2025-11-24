from fastapi import APIRouter, Body

from backend.app.schemas.chat import ChatRequest, ChatResponse
from ...services.chat_service import answer_question
from backend.app.core.utils import success_response, error_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse, summary="示例问答接口")
async def chat(req: ChatRequest = Body(...)) -> dict:
    """一个最小可跑的占位问答接口。

    真实场景下，这里会：
    - 调用图谱查询服务获取 process context；
    - 调用 LLM 生成答案。
    """
    try:
        result = answer_question(req.question, req.process_id)
        data = ChatResponse(answer=result["answer"], process_id=result.get("process_id"))
        return success_response(data=data)
    except Exception as exc:
        return error_response(message=str(exc))
