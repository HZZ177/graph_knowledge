"""Chat 模块数据模型

合并了 Conversation 和 FileUpload 两个与 Chat 相关的模型。
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, Index

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


class FileUpload(Base):
    """文件上传记录表"""
    __tablename__ = "file_uploads"
    
    # 主键
    id = Column(String(36), primary_key=True)  # UUID
    
    # 文件信息
    file_key = Column(String(512), unique=True, nullable=False, index=True)  # OSS Key
    filename = Column(String(255), nullable=False)  # 原始文件名
    content_type = Column(String(100), nullable=False)  # MIME 类型
    size = Column(Integer, nullable=False)  # 文件大小（字节）
    
    # 访问 URL（永久有效，简化设计）
    url = Column(Text, nullable=False)  # 永久访问 URL
    
    # 会话关联
    conversation_id = Column(String(36), nullable=True, index=True)  # 关联的对话 ID
    
    # 元信息
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 创建索引（优化查询性能）
    __table_args__ = (
        Index('idx_conversation_id', 'conversation_id'),
        Index('idx_uploaded_at', 'uploaded_at'),
    )
    
    def __repr__(self):
        return f"<FileUpload(id={self.id}, filename={self.filename}, size={self.size})>"
