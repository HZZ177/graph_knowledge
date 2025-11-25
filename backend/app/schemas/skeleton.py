"""骨架生成相关的数据结构定义"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== 请求结构 ====================

class SkeletonGenerateRequest(BaseModel):
    """骨架生成请求"""

    # 必填：业务描述
    business_name: str = Field(..., description="业务流程名称，如'C端用户开通月卡'")
    business_description: str = Field(..., description="详细的业务流程描述")
    channel: Optional[str] = Field(None, description="渠道，如 'C端'、'B端'")

    # 可选：结构化日志
    structured_logs: Optional[str] = Field(None, description="结构化日志内容")

    # 可选：抓包接口数据
    api_captures: Optional[str] = Field(None, description="抓包的HTTP接口信息，curl格式或JSON")

    # 可选：已知约束
    known_systems: Optional[List[str]] = Field(None, description="已知涉及的系统列表")
    known_data_resources: Optional[List[str]] = Field(None, description="已知涉及的数据资源")


# ==================== Agent输出结构（规范化） ====================

class BranchRef(BaseModel):
    """分支引用"""
    target_step_name: str
    condition: Optional[str] = None
    label: Optional[str] = None


class StepSkeleton(BaseModel):
    """步骤骨架"""
    name: str
    description: str = ""
    step_type: str = Field(default="process", description="start | process | decision | end")


class EdgeSkeleton(BaseModel):
    """边骨架（步骤之间的连接）"""
    from_step_name: str
    to_step_name: str
    edge_type: str = "normal"  # normal | branch
    condition: Optional[str] = None
    label: Optional[str] = None


class ImplSkeleton(BaseModel):
    """实现骨架"""
    name: str
    type: str = Field(default="http_endpoint", description="http_endpoint | rpc_method | mq_consumer | scheduled_job")
    system: str
    description: Optional[str] = None
    code_ref: Optional[str] = None
    step_name: Optional[str] = None  # 关联的步骤名称（兼容旧格式）


class DataResourceSkeleton(BaseModel):
    """数据资源骨架"""
    name: str
    type: str = "db_table"  # db_table | cache | mq | api
    system: str
    description: Optional[str] = None


class StepImplLinkSkeleton(BaseModel):
    """步骤-实现关联"""
    step_name: str
    impl_name: str


class ImplDataLinkSkeleton(BaseModel):
    """实现-数据资源关联"""
    impl_name: str
    resource_name: str
    access_type: str = "read"  # read | write | read_write
    access_pattern: Optional[str] = None


class ProcessSkeleton(BaseModel):
    """流程骨架"""
    name: str
    channel: str = ""
    description: str = ""


class SkeletonAgentOutput(BaseModel):
    """Agent最终输出的完整骨架"""
    process: ProcessSkeleton
    steps: List[StepSkeleton] = []
    edges: List[EdgeSkeleton] = []
    implementations: List[ImplSkeleton] = []
    step_impl_links: List[StepImplLinkSkeleton] = []
    data_resources: List[DataResourceSkeleton] = []
    impl_data_links: List[ImplDataLinkSkeleton] = []


# ==================== WebSocket消息结构 ====================

class AgentStreamChunk(BaseModel):
    """Agent流式输出的单个chunk"""
    type: str = "stream"  # stream | agent_start | agent_end | result | error
    agent_name: str
    agent_index: int  # 0, 1, 2 表示第几个agent
    content: Optional[str] = None  # 流式内容片段
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # agent_start 时的额外信息
    agent_description: Optional[str] = None

    # agent_end 时的额外信息
    agent_output: Optional[str] = None  # agent完整输出
    duration_ms: Optional[int] = None  # 耗时毫秒

    # result 时的最终画布数据
    canvas_data: Optional[dict] = None

    # error 时的错误信息
    error: Optional[str] = None


# ==================== 中间结果结构 ====================

class DataAnalysisResult(BaseModel):
    """数据分析Agent的输出"""
    systems: List[str] = Field(default_factory=list, description="识别到的系统列表")
    apis: List[dict] = Field(default_factory=list, description="识别到的API列表")
    data_resources: List[dict] = Field(default_factory=list, description="识别到的数据资源")
    call_sequence: List[str] = Field(default_factory=list, description="调用顺序线索")
    raw_analysis: str = Field(default="", description="原始分析文本")


class FlowDesignResult(BaseModel):
    """流程设计Agent的输出"""
    steps: List[StepSkeleton] = Field(default_factory=list)
    raw_design: str = Field(default="", description="原始设计文本")


class TechEnrichResult(BaseModel):
    """技术充实Agent的输出"""
    skeleton: Optional[SkeletonAgentOutput] = None
    raw_enrich: str = Field(default="", description="原始充实文本")
