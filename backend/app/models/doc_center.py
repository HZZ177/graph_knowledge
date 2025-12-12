"""
文档中心数据模型

用于管理从帮助中心同步的文档及其 LightRAG 索引状态
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db.sqlite import Base


class DocCenterFolder(Base):
    """文档中心-目录记录（从帮助中心同步）"""
    __tablename__ = "doc_center_folders"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: uuid4().hex,
        comment="本地目录唯一标识"
    )

    # === 来源信息 ===
    source_menu_id = Column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="帮助中心的 menuId"
    )
    source_parent_id = Column(
        String(64),
        default="0",
        comment="帮助中心的父目录 menuId，0表示根目录"
    )
    source_project_id = Column(
        Integer,
        default=55,
        comment="帮助中心的 projectId"
    )

    # === 目录信息 ===
    title = Column(String(255), nullable=False, comment="目录名称")
    sort_order = Column(Integer, default=0, comment="排序")

    # === 时间戳 ===
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )


class DocCenterDocument(Base):
    """文档中心-文档记录"""
    __tablename__ = "doc_center_documents"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: uuid4().hex,
        comment="本地文档唯一标识"
    )

    # === 来源信息 ===
    source_doc_id = Column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="帮助中心的 docId"
    )
    source_project_id = Column(
        Integer,
        default=55,
        comment="帮助中心的 projectId"
    )
    source_parent_id = Column(
        String(64),
        nullable=True,
        comment="帮助中心的父目录 menuId"
    )

    # === 文档基本信息 ===
    title = Column(String(255), nullable=False, comment="文档标题")
    path = Column(String(512), nullable=True, comment="完整路径，如 /产品文档/功能说明")

    # === 同步状态 ===
    # pending: 未同步, syncing: 同步中, synced: 已同步, failed: 同步失败
    sync_status = Column(
        String(20),
        default="pending",
        comment="同步状态: pending|syncing|synced|failed"
    )
    sync_error = Column(Text, nullable=True, comment="同步错误信息")
    synced_at = Column(DateTime, nullable=True, comment="最后同步时间")

    # === 本地存储 ===
    local_path = Column(String(512), nullable=True, comment="本地文件路径")
    content_hash = Column(String(32), nullable=True, comment="内容MD5哈希")
    image_count = Column(Integer, default=0, comment="文档中的图片数量")

    # === LightRAG 索引状态 ===
    # pending: 未索引, queued: 已排队, indexing: 索引中, indexed: 已索引, failed: 索引失败
    index_status = Column(
        String(20),
        default="pending",
        comment="索引状态: pending|queued|indexing|indexed|failed"
    )
    index_progress = Column(Integer, default=0, comment="索引进度 0-100")
    index_phase = Column(String(50), nullable=True, comment="当前索引阶段")
    index_phase_detail = Column(String(255), nullable=True, comment="阶段详情")
    index_error = Column(Text, nullable=True, comment="索引错误信息")
    index_started_at = Column(DateTime, nullable=True, comment="索引开始时间")
    index_finished_at = Column(DateTime, nullable=True, comment="索引完成时间")

    # === LightRAG 统计信息 ===
    chunk_count = Column(Integer, default=0, comment="分块数量")
    entity_count = Column(Integer, default=0, comment="实体数量")
    relation_count = Column(Integer, default=0, comment="关系数量")

    # === 时间戳 ===
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )

    # 关联的索引任务
    index_tasks = relationship("DocCenterIndexTask", back_populates="document")


class DocCenterIndexTask(Base):
    """文档索引任务队列"""
    __tablename__ = "doc_center_index_tasks"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: uuid4().hex,
        comment="任务唯一标识"
    )
    document_id = Column(
        String(36),
        ForeignKey("doc_center_documents.id"),
        nullable=False,
        index=True,
        comment="关联的文档ID"
    )

    # === 任务状态 ===
    # pending: 待处理, running: 运行中, completed: 已完成, failed: 失败, cancelled: 已取消
    status = Column(
        String(20),
        default="pending",
        comment="任务状态: pending|running|completed|failed|cancelled"
    )
    priority = Column(Integer, default=0, comment="优先级，数字越大越优先")

    # === 进度信息 ===
    current_phase = Column(String(50), nullable=True, comment="当前阶段")
    phase_progress = Column(Integer, default=0, comment="当前阶段进度 0-100")
    overall_progress = Column(Integer, default=0, comment="总体进度 0-100")

    # === 统计信息 ===
    total_chunks = Column(Integer, default=0, comment="总分块数")
    processed_chunks = Column(Integer, default=0, comment="已处理分块数")
    total_entities = Column(Integer, default=0, comment="总实体数")
    extracted_entities = Column(Integer, default=0, comment="已提取实体数")

    # === 时间信息 ===
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="完成时间")

    # === 错误信息 ===
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")

    # === 时间戳 ===
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )

    # 关联的文档
    document = relationship("DocCenterDocument", back_populates="index_tasks")
