"""Chat 模块 Schema 定义

合并了所有与 Chat 相关的 Pydantic 模型，去除了重复定义。
"""

from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator


# ========== 工具调用 ==========

class ToolCall(BaseModel):
    """工具调用信息"""
    name: str
    args: dict = {}


# ========== 文件附件 ==========

class FileAttachment(BaseModel):
    """文件附件"""
    file_id: str = ""
    url: str
    type: str  # 'image' | 'document' | 'audio' | 'video' | 'unknown'
    filename: str
    content_type: str = ""


# ========== 消息 ==========

class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # 'user' | 'assistant' | 'tool'
    content: str
    tool_name: Optional[str] = None  # 仅 tool 类型
    tool_calls: Optional[List[ToolCall]] = None  # 仅 assistant 调用工具时
    attachments: Optional[List[FileAttachment]] = None  # 仅 user 类型，文件附件


# ========== 请求 ==========

class ChatRequest(BaseModel):
    """Chat 问答请求（WebSocket）"""
    question: str
    thread_id: Optional[str] = None  # 会话 ID，用于多轮对话


class LogQueryContext(BaseModel):
    """日志查询上下文（用于日志排查 Agent）"""
    businessLine: str  # 业务线（必填）
    privateServer: Optional[str] = None  # 私有化集团（可选）


class TestingContext(BaseModel):
    """测试助手上下文（智能测试 Agent 专用）"""
    project_name: str  # Coding 项目名称
    iteration_name: Optional[str] = None  # 迭代名称
    requirement_id: str  # 需求编号
    requirement_name: str  # 需求标题
    phase: str = "analysis"  # 当前阶段: analysis/plan/generate
    session_id: Optional[str] = None  # 任务 ID（三个阶段共享）


class StreamChatRequest(BaseModel):
    """流式问答 WebSocket 请求"""
    question: str
    thread_id: Optional[str] = None  # 会话 ID，为空则创建新会话
    agent_type: str = "knowledge_qa"  # Agent 类型，默认为知识问答
    log_query: Optional[LogQueryContext] = None  # 日志查询上下文（日志排查 Agent 专用）
    testing_context: Optional[TestingContext] = None  # 测试上下文（智能测试 Agent 专用）
    attachments: Optional[List[FileAttachment]] = None  # 文件附件列表（多模态支持）


# ========== 响应 ==========

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
    agent_type: Optional[str] = "knowledge_qa"
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


# ========== 文件上传响应 ==========

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    url: str
    filename: str
    size: int
    content_type: str


class FileInfoResponse(BaseModel):
    """文件信息响应"""
    file_id: str
    url: str
    filename: str
    size: int
    content_type: str
    conversation_id: str | None
    uploaded_at: str
