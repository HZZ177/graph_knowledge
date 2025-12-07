"""文件上传记录表"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from datetime import datetime, timezone

from backend.app.db.sqlite import Base


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
