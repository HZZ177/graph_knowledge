from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text

from backend.app.db.sqlite import Base


def utc_now():
    return datetime.now(timezone.utc)


class Conversation(Base):
    """会话元数据表
    
    存储对话的标题、创建时间等元数据。
    实际的对话消息内容存储在 LangGraph Checkpoint 中。
    """
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, comment="Thread ID")
    title = Column(String, nullable=True, default="新对话", comment="会话标题")
    agent_type = Column(String, nullable=True, default="knowledge_qa", comment="Agent 类型")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
