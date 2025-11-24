from typing import List, Optional

from pydantic import BaseModel


class CanvasProcess(BaseModel):
    process_id: str
    name: Optional[str] = None
    channel: Optional[str] = None
    description: Optional[str] = None
    entrypoints: Optional[List[str]] = None


class CanvasStep(BaseModel):
    step_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    step_type: Optional[str] = None


class CanvasEdge(BaseModel):
    id: Optional[int] = None
    from_step_id: str
    to_step_id: str
    edge_type: Optional[str] = None
    condition: Optional[str] = None
    label: Optional[str] = None
    from_handle: Optional[str] = None
    to_handle: Optional[str] = None


class CanvasImplementation(BaseModel):
    impl_id: str
    name: Optional[str] = None
    type: Optional[str] = None
    system: Optional[str] = None
    description: Optional[str] = None
    code_ref: Optional[str] = None


class CanvasStepImplLink(BaseModel):
    id: Optional[int] = None
    step_id: str
    impl_id: str
    step_handle: Optional[str] = None
    impl_handle: Optional[str] = None


class CanvasDataResource(BaseModel):
    resource_id: str
    name: Optional[str] = None
    type: Optional[str] = None
    system: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class CanvasImplDataLink(BaseModel):
    id: Optional[int] = None
    impl_id: str
    resource_id: str
    impl_handle: Optional[str] = None
    resource_handle: Optional[str] = None
    access_type: Optional[str] = None
    access_pattern: Optional[str] = None


class CanvasImplLink(BaseModel):
    id: Optional[int] = None
    from_impl_id: str
    to_impl_id: str
    from_handle: Optional[str] = None
    to_handle: Optional[str] = None
    edge_type: Optional[str] = None
    condition: Optional[str] = None
    label: Optional[str] = None


class SaveProcessCanvasRequest(BaseModel):
    process_id: str
    process: CanvasProcess
    steps: List[CanvasStep] = []
    edges: List[CanvasEdge] = []
    implementations: List[CanvasImplementation] = []
    step_impl_links: List[CanvasStepImplLink] = []
    data_resources: List[CanvasDataResource] = []
    impl_data_links: List[CanvasImplDataLink] = []
    impl_links: List[CanvasImplLink] = []
