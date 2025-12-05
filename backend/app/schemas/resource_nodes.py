from typing import List, Optional, Literal

from pydantic import BaseModel, field_validator


# 枚举类型定义
StepTypeEnum = Literal["inner", "outer"]
ImplementationTypeEnum = Literal["api", "function", "job"]
DataResourceTypeEnum = Literal["table", "redis"]
# 实现单元的系统枚举（微服务名称）
ImplSystemEnum = Literal["admin-vehicle-owner", "owner-center", "vehicle-pay-center"]
# 数据资源的系统枚举（业务线分类）
DataResourceSystemEnum = Literal["C端", "B端", "路侧", "封闭"]


class BusinessBase(BaseModel):
    name: str
    channel: Optional[str] = None
    description: Optional[str] = None
    entrypoints: Optional[str] = None  # 逗号分隔的入口列表字符串


class BusinessCreate(BusinessBase):
    pass


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    description: Optional[str] = None
    entrypoints: Optional[str] = None


class BusinessOut(BusinessBase):
    process_id: str

    class Config:
        from_attributes = True


class PaginatedBusinesses(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[BusinessOut]


class StepBase(BaseModel):
    name: str
    description: Optional[str] = None
    step_type: Optional[StepTypeEnum] = None


class StepCreate(StepBase):
    pass


class StepUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    step_type: Optional[StepTypeEnum] = None


class StepOut(StepBase):
    step_id: str

    class Config:
        from_attributes = True


class PaginatedSteps(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[StepOut]


class ImplementationBase(BaseModel):
    name: str
    type: Optional[ImplementationTypeEnum] = None
    system: Optional[ImplSystemEnum] = None
    description: Optional[str] = None
    code_ref: Optional[str] = None


class ImplementationCreate(ImplementationBase):
    pass


class ImplementationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[ImplementationTypeEnum] = None
    system: Optional[ImplSystemEnum] = None
    description: Optional[str] = None
    code_ref: Optional[str] = None


class ImplementationOut(ImplementationBase):
    impl_id: str

    class Config:
        from_attributes = True


class PaginatedImplementations(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[ImplementationOut]


class ImplementationBatchCreate(BaseModel):
    """批量创建实现单元的请求"""
    items: List[ImplementationCreate]


class ImplementationBatchCreateResult(BaseModel):
    """批量创建结果"""
    success_count: int
    skip_count: int  # 已存在跳过的数量
    failed_count: int
    created_items: List[ImplementationOut]
    skipped_names: List[str]  # 跳过的名称列表
    failed_items: List[dict]  # 失败的项及原因


class StepImplementationLinkBase(BaseModel):
    step_id: str
    impl_id: str


class StepImplementationLinkCreate(StepImplementationLinkBase):
    pass


class StepImplementationLinkOut(StepImplementationLinkBase):
    id: int

    class Config:
        from_attributes = True


class BusinessIdRequest(BaseModel):
    process_id: str


class BusinessUpdatePayload(BusinessUpdate):
    process_id: str


class StepIdRequest(BaseModel):
    step_id: str


class StepUpdatePayload(StepUpdate):
    step_id: str


class ImplementationIdRequest(BaseModel):
    impl_id: str


class ImplementationUpdatePayload(ImplementationUpdate):
    impl_id: str


class StepImplementationLinkIdRequest(BaseModel):
    link_id: int


# ---- 分组统计响应 ----


class GroupCount(BaseModel):
    """单个分组的统计信息"""
    value: Optional[str] = None  # 分组值，None 表示"其他"
    count: int


class BusinessGroupStats(BaseModel):
    """业务流程分组统计"""
    by_channel: List[GroupCount]
    total: int


class StepGroupStats(BaseModel):
    """步骤分组统计"""
    by_step_type: List[GroupCount]
    total: int


class ImplementationGroupStats(BaseModel):
    """实现分组统计 - 两级分组"""
    by_system: List[GroupCount]
    by_type: List[GroupCount]
    total: int


class DataResourceGroupStats(BaseModel):
    """数据资源分组统计 - 两级分组"""
    by_system: List[GroupCount]
    by_type: List[GroupCount]
    total: int
