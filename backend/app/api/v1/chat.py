from fastapi import APIRouter
from pydantic import BaseModel

from ...services.chat_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    process_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    process_id: str | None = None


@router.post("", response_model=ChatResponse, summary="示例问答接口")
async def chat(req: ChatRequest) -> ChatResponse:
    """一个最小可跑的占位问答接口。

    真实场景下，这里会：
    - 调用图谱查询服务获取 process context；
    - 调用 LLM 生成答案。
    """
    result = answer_question(req.question, req.process_id)
    return ChatResponse(answer=result["answer"], process_id=result.get("process_id"))
