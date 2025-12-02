from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator


class ToolCall(BaseModel):
    """工具调用信息"""
    name: str
    args: dict = {}


class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # 'user' | 'assistant' | 'tool'
    content: str
    tool_name: Optional[str] = None  # 仅 tool 类型
    tool_calls: Optional[List[ToolCall]] = None  # 仅 assistant 调用工具时


class ChatRequest(BaseModel):
    """Chat 问答请求（WebSocket）"""
    question: str
    thread_id: Optional[str] = None  # 会话 ID，用于多轮对话


class StreamChatRequest(BaseModel):
    """流式问答 WebSocket 请求"""
    question: str
    thread_id: Optional[str] = None  # 会话 ID，为空则创建新会话
    agent_type: str = "knowledge_qa"  # Agent 类型，默认为知识问答


class AgentTypeOut(BaseModel):
    """Agent 类型信息（用于前端展示）"""
    agent_type: str
    name: str
    description: str
    tags: List[str]


class ChatResponse(BaseModel):
    """Chat 响应"""
    thread_id: str
    content: str
    tool_calls: Optional[List[dict]] = None


class ConversationHistoryResponse(BaseModel):
    """会话历史响应"""
    thread_id: str
    messages: List[ChatMessage]


class ConversationOut(BaseModel):
    """会话元数据"""
    id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

    @field_validator("created_at", "updated_at")
    @classmethod
    def set_utc_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
