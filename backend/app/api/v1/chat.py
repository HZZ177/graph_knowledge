from fastapi import APIRouter
from pydantic import BaseModel

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
    answer = f"这是一个占位回答。你问了: {req.question}"
    return ChatResponse(answer=answer, process_id=req.process_id)
