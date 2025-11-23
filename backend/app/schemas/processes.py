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
