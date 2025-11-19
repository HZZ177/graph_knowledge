from typing import List, Optional

from pydantic import BaseModel


class BusinessBase(BaseModel):
    name: str
    channel: Optional[str] = None
    description: Optional[str] = None
    entrypoints: Optional[str] = None  # 逗号分隔的入口列表字符串


class BusinessCreate(BusinessBase):
    process_id: str


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
    step_type: Optional[str] = None


class StepCreate(StepBase):
    step_id: str


class StepUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    step_type: Optional[str] = None


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
    type: Optional[str] = None
    system: Optional[str] = None
    description: Optional[str] = None
    code_ref: Optional[str] = None


class ImplementationCreate(ImplementationBase):
    impl_id: str


class ImplementationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    system: Optional[str] = None
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


class StepImplementationLinkBase(BaseModel):
    step_id: str
    impl_id: str


class StepImplementationLinkCreate(StepImplementationLinkBase):
    pass


class StepImplementationLinkOut(StepImplementationLinkBase):
    id: int

    class Config:
        from_attributes = True
