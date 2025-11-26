from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    process_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    process_id: str | None = None


class StreamChatRequest(BaseModel):
    """流式问答请求"""
    question: str
    process_id: str | None = None
