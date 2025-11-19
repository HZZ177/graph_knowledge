from typing import List, Optional

from pydantic import BaseModel


class DataResourceBase(BaseModel):
    resource_id: str
    name: str
    type: Optional[str] = None
    system: Optional[str] = None
    location: Optional[str] = None
    entity_id: Optional[str] = None
    description: Optional[str] = None


class DataResourceCreate(DataResourceBase):
    pass


class DataResourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    system: Optional[str] = None
    location: Optional[str] = None
    entity_id: Optional[str] = None
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
