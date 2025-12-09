"""Chat 模块数据模型

合并了 Conversation 和 FileUpload 两个与 Chat 相关的模型。
新增测试助手相关模型：TestSessionAnalysis。
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, Index, Float

from backend.app.db.sqlite import Base


def utc_now():
    return datetime.now(timezone.utc)


class Conversation(Base):
    """会话元数据表（统一存储普通对话和测试任务）
    
    普通对话：id 就是 thread_id，测试专用字段为 null
    测试任务：id 是 session_id，通过 thread_id_* 关联三个阶段的消息
    """
    __tablename__ = "conversations"
    
    # ========== 通用字段（原有）==========
    id = Column(String, primary_key=True, comment="普通对话=thread_id，测试任务=session_id")
    title = Column(String, nullable=True, default="新对话", comment="会话标题")
    agent_type = Column(String, nullable=True, default="knowledge_qa", comment="Agent 类型")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # ========== 测试助手专用字段（新增，其他 agent 为 null）==========
    requirement_id = Column(String, nullable=True, comment="Coding 需求 ID")
    project_name = Column(String, nullable=True, comment="Coding 项目名称")
    status = Column(String, nullable=True, comment="测试任务状态: pending/analysis/plan/generate/completed/failed")
    current_phase = Column(String, nullable=True, comment="当前阶段: analysis/plan/generate")
    thread_id_analysis = Column(String, nullable=True, comment="阶段1 需求分析 thread_id")
    thread_id_plan = Column(String, nullable=True, comment="阶段2 方案生成 thread_id")
    thread_id_generate = Column(String, nullable=True, comment="阶段3 用例生成 thread_id")


class TestSessionAnalysis(Base):
    """测试会话分析缓存表
    
    存储阶段间传递的摘要内容，用于分阶段 Token 压缩。
    """
    __tablename__ = "test_session_analysis"
    
    id = Column(String, primary_key=True, comment="UUID")
    session_id = Column(String, nullable=False, index=True, comment="对应 conversations.id（测试任务的 session_id）")
    phase = Column(String, nullable=False, comment="阶段: analysis / plan / generate")
    analysis_type = Column(String, nullable=False, comment="摘要类型: requirement_summary / test_plan / test_cases")
    content = Column(Text, nullable=False, comment="JSON 格式的摘要内容")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        Index('idx_test_session_analysis_session', 'session_id'),
        Index('idx_test_session_analysis_session_phase', 'session_id', 'phase'),
        Index('idx_test_session_analysis_session_type', 'session_id', 'analysis_type', unique=True),
    )


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
