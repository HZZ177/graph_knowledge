from typing import List, Optional, Literal

from pydantic import BaseModel

from backend.app.schemas.resource_nodes import DataResourceTypeEnum, SystemEnum


class DataResourceBase(BaseModel):
    resource_id: str
    name: str
    type: Optional[DataResourceTypeEnum] = None
    system: Optional[SystemEnum] = None
    location: Optional[str] = None
    description: Optional[str] = None


class DataResourceCreate(BaseModel):
    name: str
    type: Optional[DataResourceTypeEnum] = None
    system: Optional[SystemEnum] = None
    location: Optional[str] = None
    description: Optional[str] = None


class DataResourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[DataResourceTypeEnum] = None
    system: Optional[SystemEnum] = None
    location: Optional[str] = None
    description: Optional[str] = None


class DataResourceOut(DataResourceBase):
    class Config:
        from_attributes = True

class PaginatedDataResources(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[DataResourceOut]


class BusinessSimple(BaseModel):
    process_id: str
    name: str


class StepSimple(BaseModel):
    step_id: str
    name: str
    process_id: Optional[str] = None
    process_name: Optional[str] = None


class DataResourceIdRequest(BaseModel):
    resource_id: str


class DataResourceUpdatePayload(DataResourceUpdate):
    resource_id: str


class ResourceAccessor(BaseModel):
    impl_id: str
    impl_name: str
    impl_system: Optional[str] = None
    access_type: Optional[str] = None
    access_pattern: Optional[str] = None
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    process_id: Optional[str] = None
    process_name: Optional[str] = None


class ImplementationDataLinkBase(BaseModel):
    impl_id: str
    resource_id: str
    access_type: Optional[str] = None
    access_pattern: Optional[str] = None


class ImplementationDataLinkCreate(ImplementationDataLinkBase):
    pass


class ImplementationDataLinkUpdate(BaseModel):
    access_type: Optional[str] = None
    access_pattern: Optional[str] = None


class ImplementationDataLinkIdRequest(BaseModel):
    link_id: int


class ImplementationDataLinkUpdatePayload(ImplementationDataLinkUpdate):
    link_id: int


class ImplementationDataLinkOut(ImplementationDataLinkBase):
    id: int

    class Config:
        from_attributes = True


class ResourceWithAccessors(BaseModel):
    resource: DataResourceOut
    accessors: List[ResourceAccessor]


class AccessChainItem(BaseModel):
    """Generic access relationship chain from any node perspective.

    Represents one logical chain: Business -> Step -> Implementation -> DataResource.
    Some parts can be missing (e.g. no Business/Step), so most fields are optional.
    """

    resource_id: str
    resource_name: str
    impl_id: Optional[str] = None
    impl_name: Optional[str] = None
    impl_system: Optional[str] = None
    access_type: Optional[str] = None
    access_pattern: Optional[str] = None
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    process_id: Optional[str] = None
    process_name: Optional[str] = None
