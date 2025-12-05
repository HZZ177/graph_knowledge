from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime

from backend.app.db.sqlite import Base


class Business(Base):
    __tablename__ = "businesses"

    process_id = Column(
        String,
        primary_key=True,
        index=True,
        default=lambda: uuid4().hex,
        comment="业务流程唯一标识",
    )
    name = Column(String, nullable=False, unique=True, comment="业务名称")
    channel = Column(String, nullable=True, comment="业务所属渠道（如 APP、H5 等）")
    description = Column(Text, nullable=True, comment="业务描述")
    entrypoints = Column(Text, nullable=True, comment="可存 JSON 字符串")
    canvas_node_ids = Column(Text, nullable=True, comment="画布节点ID列表，JSON格式: {step_ids: [], impl_ids: [], resource_ids: []}")
    
    # 同步状态字段
    sync_status = Column(
        String, 
        nullable=True, 
        default="never_synced",
        comment="Neo4j同步状态: never_synced, syncing, synced, failed"
    )
    last_sync_at = Column(DateTime, nullable=True, comment="最后同步时间")
    sync_error = Column(Text, nullable=True, comment="同步错误信息")

    edges = relationship("ProcessStepEdge", back_populates="business")  # 业务内步骤之间的边（流程连线）集合


class Step(Base):
    __tablename__ = "steps"

    step_id = Column(
        String,
        primary_key=True,
        index=True,
        default=lambda: uuid4().hex,
        comment="步骤唯一标识",
    )
    name = Column(String, nullable=False, unique=True, comment="步骤名称")
    description = Column(Text, nullable=True, comment="步骤说明")
    step_type = Column(String, nullable=True, comment="步骤类型，如开始、普通、结束等")

    implementations = relationship("StepImplementation", back_populates="step")  # 与该步骤关联的实现列表


class ProcessStepEdge(Base):
    __tablename__ = "process_step_edges"

    id = Column(Integer, primary_key=True, index=True, comment="边记录主键")
    process_id = Column(String, ForeignKey("businesses.process_id"), nullable=False, index=True, comment="所属业务流程 ID")
    from_step_id = Column(String, ForeignKey("steps.step_id"), nullable=False, index=True, comment="起始步骤 ID")
    to_step_id = Column(String, ForeignKey("steps.step_id"), nullable=False, index=True, comment="目标步骤 ID")
    from_handle = Column(String, nullable=True, comment="起始步骤节点的连接点 ID（如 t-out, r-out 等）")
    to_handle = Column(String, nullable=True, comment="目标步骤节点的连接点 ID（如 t-in, l-in 等）")
    edge_type = Column(String, nullable=True, comment="边类型（如顺序、条件等）")
    condition = Column(Text, nullable=True, comment="触发该边的条件表达式")
    label = Column(String, nullable=True, comment="边上的展示文案/标签")

    __table_args__ = (
        UniqueConstraint(
            "process_id",
            "from_step_id",
            "to_step_id",
            "edge_type",
            "condition",
            name="uq_process_step_edges_process_from_to_type_cond",
        ),
    )

    business = relationship("Business", back_populates="edges")  # 所属业务实体
    from_step = relationship("Step", foreign_keys=[from_step_id])  # 起始步骤实体
    to_step = relationship("Step", foreign_keys=[to_step_id])  # 目标步骤实体


class Implementation(Base):
    __tablename__ = "implementations"

    impl_id = Column(
        String,
        primary_key=True,
        index=True,
        default=lambda: uuid4().hex,
        comment="实现唯一标识",
    )
    name = Column(String, nullable=False, unique=True, comment="实现名称")
    type = Column(String, nullable=True, comment="实现类型（如 API、脚本等）")
    system = Column(String, nullable=True, comment="所属系统")
    description = Column(Text, nullable=True, comment="实现说明")
    code_ref = Column(Text, nullable=True, comment="代码或配置引用信息")

    step_links = relationship("StepImplementation", back_populates="implementation")  # 该实现关联的步骤关系
    data_resources = relationship(
        "ImplementationDataResource", back_populates="implementation"
    )  # 该实现访问的数据资源集合


class DataResource(Base):
    __tablename__ = "data_resources"

    resource_id = Column(
        String,
        primary_key=True,
        index=True,
        default=lambda: uuid4().hex,
        comment="数据资源唯一标识",
    )
    name = Column(String, nullable=False, unique=True, comment="数据资源名称")
    type = Column(String, nullable=True, comment="数据资源类型（如表、接口、文件等）")
    system = Column(String, nullable=True, comment="数据资源所在系统")
    location = Column(String, nullable=True, comment="物理或逻辑位置标识")
    description = Column(Text, nullable=True, comment="数据资源说明")
    ddl = Column(Text, nullable=True, comment="库表 DDL 结构定义（CREATE TABLE 语句）")

    implementations = relationship(
        "ImplementationDataResource", back_populates="data_resource"
    )  # 使用该数据资源的实现关系集合


class StepImplementation(Base):
    __tablename__ = "step_implementations"

    id = Column(Integer, primary_key=True, index=True, comment="步骤与实现关系主键")
    process_id = Column(String, ForeignKey("businesses.process_id"), nullable=False, index=True, comment="所属业务流程 ID")
    step_id = Column(String, ForeignKey("steps.step_id"), nullable=False, comment="步骤 ID")
    impl_id = Column(String, ForeignKey("implementations.impl_id"), nullable=False, comment="实现 ID")
    step_handle = Column(String, nullable=True, comment="步骤节点上的连接点 ID（如 t-out, r-out 等）")
    impl_handle = Column(String, nullable=True, comment="实现节点上的连接点 ID（如 t-in, l-in 等）")

    __table_args__ = (
        UniqueConstraint("process_id", "step_id", "impl_id", name="uq_step_implementations_process_step_impl"),
    )

    step = relationship("Step", back_populates="implementations")  # 关联的步骤实体
    implementation = relationship("Implementation", back_populates="step_links")  # 关联的实现实体


class ImplementationDataResource(Base):
    __tablename__ = "implementation_data_resources"

    id = Column(Integer, primary_key=True, index=True, comment="实现与数据资源关系主键")
    process_id = Column(String, ForeignKey("businesses.process_id"), nullable=False, index=True, comment="所属业务流程 ID")
    impl_id = Column(
        String, ForeignKey("implementations.impl_id"), nullable=False, index=True, comment="实现 ID"
    )
    resource_id = Column(
        String, ForeignKey("data_resources.resource_id"), nullable=False, index=True, comment="数据资源 ID"
    )
    impl_handle = Column(String, nullable=True, comment="实现节点上的连接点 ID（如 t-out, r-out 等）")
    resource_handle = Column(String, nullable=True, comment="数据资源节点上的连接点 ID（如 t-in, l-in 等）")
    access_type = Column(String, nullable=True, comment="访问类型（读/写/读写等)")
    access_pattern = Column(String, nullable=True, comment="访问模式（如批量、实时等)")

    __table_args__ = (
        UniqueConstraint(
            "process_id",
            "impl_id",
            "resource_id",
            "access_type",
            "access_pattern",
            name="uq_implementation_data_resources_process_impl_res_type_pattern",
        ),
    )

    implementation = relationship("Implementation", back_populates="data_resources")  # 关联的实现实体
    data_resource = relationship("DataResource", back_populates="implementations")  # 关联的数据资源实体


class ImplementationLink(Base):
    """实现节点之间的连线关系，用于表示实现之间的调用/依赖链路。

    设计上参考 ProcessStepEdge，但起点和终点都指向 Implementation。
    """

    __tablename__ = "implementation_links"

    id = Column(Integer, primary_key=True, index=True, comment="实现-实现边记录主键")
    process_id = Column(
        String,
        ForeignKey("businesses.process_id"),
        nullable=False,
        index=True,
        comment="所属业务流程 ID",
    )
    from_impl_id = Column(
        String,
        ForeignKey("implementations.impl_id"),
        nullable=False,
        index=True,
        comment="起始实现 ID",
    )
    to_impl_id = Column(
        String,
        ForeignKey("implementations.impl_id"),
        nullable=False,
        index=True,
        comment="目标实现 ID",
    )
    from_handle = Column(
        String,
        nullable=True,
        comment="起始实现节点的连接点 ID（如 t-out, r-out 等）",
    )
    to_handle = Column(
        String,
        nullable=True,
        comment="目标实现节点的连接点 ID（如 t-in, l-in 等）",
    )
    edge_type = Column(String, nullable=True, comment="边类型（如调用、回调等）")
    condition = Column(Text, nullable=True, comment="触发该边的条件表达式")
    label = Column(String, nullable=True, comment="边上的展示文案/标签")

    __table_args__ = (
        UniqueConstraint(
            "process_id",
            "from_impl_id",
            "to_impl_id",
            "edge_type",
            "condition",
            name="uq_implementation_links_process_from_to_type_cond",
        ),
    )

    # 这里暂不定义反向 relationship，按需从实现或业务侧手动查询
