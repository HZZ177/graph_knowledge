from typing import List

from pydantic import BaseModel


class ProcessBase(BaseModel):
    name: str
    channel: str | None = None
    description: str | None = None
    entrypoints: List[str] | None = None


class ProcessCreate(ProcessBase):
    process_id: str


class ProcessUpdate(ProcessBase):
    pass


class ProcessStep(BaseModel):
    step_id: int
    process_id: str
    order_no: int
    name: str | None = None
    capability_id: str | None = None


class ProcessEdgeBase(BaseModel):
    from_step_id: str
    to_step_id: str
    edge_type: str | None = None
    condition: str | None = None
    label: str | None = None


class ProcessEdgeCreate(ProcessEdgeBase):
    pass


class ProcessEdgeUpdate(BaseModel):
    from_step_id: str | None = None
    to_step_id: str | None = None
    edge_type: str | None = None
    condition: str | None = None
    label: str | None = None


class ProcessEdgeOut(ProcessEdgeBase):
    id: int

    class Config:
        from_attributes = True


class ProcessIdRequest(BaseModel):
    """通用的流程 ID 请求体。"""

    process_id: str


class ProcessUpdatePayload(ProcessUpdate):
    """更新流程时使用的请求体，包含流程 ID 及可更新字段。"""

    process_id: str


class SaveProcessStepsRequest(BaseModel):
    """保存流程步骤列表的请求体。"""

    process_id: str
    steps: List[ProcessStep]


class DeleteProcessStepRequest(BaseModel):
    """删除单个流程步骤的请求体。"""

    process_id: str
    step_id: int


class CreateProcessEdgeRequest(ProcessEdgeCreate):
    """在流程中创建边的请求体。"""

    process_id: str


class UpdateProcessEdgeRequest(ProcessEdgeUpdate):
    """更新流程边属性的请求体。"""

    process_id: str
    edge_id: int


class DeleteProcessEdgeRequest(BaseModel):
    """删除流程边的请求体。"""

    process_id: str
    edge_id: int

