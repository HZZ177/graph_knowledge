"""SQLite 数据访问层 - 负责所有 SQLite 数据库操作"""

from typing import Any, Dict, List, Optional, Set, Sequence
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.resource_graph import (
    Business,
    DataResource,
    Implementation,
    ImplementationDataResource,
    ProcessStepEdge,
    Step,
    StepImplementation,
    ImplementationLink,
)


class SQLiteRepository:
    """SQLite 数据库仓储类，封装所有 SQLite 数据访问操作"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Business 相关 ====================
    
    def get_business(self, process_id: str) -> Optional[Business]:
        """获取业务流程"""
        return (
            self.db.query(Business)
            .filter(Business.process_id == process_id)
            .first()
        )

    def create_or_update_business(
        self, 
        process_id: str, 
        name: Optional[str] = None,
        channel: Optional[str] = None,
        description: Optional[str] = None,
        entrypoints: Optional[str] = None,
        canvas_node_ids: Optional[str] = None,
    ) -> Business:
        """创建或更新业务流程"""
        business = self.get_business(process_id)
        if business is None:
            business = Business(process_id=process_id)
            self.db.add(business)
        
        if name is not None:
            business.name = name
        if channel is not None:
            business.channel = channel
        if description is not None:
            business.description = description
        if entrypoints is not None:
            business.entrypoints = entrypoints
        if canvas_node_ids is not None:
            business.canvas_node_ids = canvas_node_ids
        
        return business

    # ==================== Step 相关 ====================
    
    def get_steps_by_ids(self, step_ids: Set[str]) -> List[Step]:
        """批量获取步骤"""
        if not step_ids:
            return []
        return (
            self.db.query(Step)
            .filter(Step.step_id.in_(step_ids))
            .order_by(Step.step_id)
            .all()
        )

    def create_or_update_step(
        self,
        step_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        step_type: Optional[str] = None,
    ) -> Step:
        """创建或更新步骤"""
        step = self.db.query(Step).filter(Step.step_id == step_id).first()
        if step is None:
            step = Step(step_id=step_id)
            self.db.add(step)
        
        if name is not None:
            step.name = name
        if description is not None:
            step.description = description
        if step_type is not None:
            step.step_type = step_type
        
        return step

    # ==================== ProcessStepEdge 相关 ====================
    
    def get_process_edges(self, process_id: str) -> List[ProcessStepEdge]:
        """获取流程的所有边"""
        return (
            self.db.query(ProcessStepEdge)
            .filter(ProcessStepEdge.process_id == process_id)
            .order_by(ProcessStepEdge.id)
            .all()
        )

    def delete_process_edges(self, process_id: str) -> None:
        """删除流程的所有边"""
        self.db.query(ProcessStepEdge).filter(
            ProcessStepEdge.process_id == process_id
        ).delete(synchronize_session=False)

    def create_edge(
        self,
        process_id: str,
        from_step_id: str,
        to_step_id: str,
        from_handle: Optional[str] = None,
        to_handle: Optional[str] = None,
        edge_type: Optional[str] = None,
        condition: Optional[str] = None,
        label: Optional[str] = None,
    ) -> ProcessStepEdge:
        """创建流程边"""
        edge = ProcessStepEdge(
            process_id=process_id,
            from_step_id=from_step_id,
            to_step_id=to_step_id,
            from_handle=from_handle,
            to_handle=to_handle,
            edge_type=edge_type,
            condition=condition,
            label=label,
        )
        self.db.add(edge)
        return edge

    # ==================== Implementation 相关 ====================
    
    def get_implementations_by_ids(self, impl_ids: Set[str]) -> List[Implementation]:
        """批量获取实现"""
        if not impl_ids:
            return []
        return (
            self.db.query(Implementation)
            .filter(Implementation.impl_id.in_(impl_ids))
            .order_by(Implementation.impl_id)
            .all()
        )

    def create_or_update_implementation(
        self,
        impl_id: str,
        name: Optional[str] = None,
        type_: Optional[str] = None,
        system: Optional[str] = None,
        description: Optional[str] = None,
        code_ref: Optional[str] = None,
    ) -> Implementation:
        """创建或更新实现"""
        impl = (
            self.db.query(Implementation)
            .filter(Implementation.impl_id == impl_id)
            .first()
        )
        if impl is None:
            impl = Implementation(impl_id=impl_id)
            self.db.add(impl)
        
        if name is not None:
            impl.name = name
        if type_ is not None:
            impl.type = type_
        if system is not None:
            impl.system = system
        if description is not None:
            impl.description = description
        if code_ref is not None:
            impl.code_ref = code_ref
        
        return impl

    def get_implementations_by_names(self, names: List[str]) -> List[Implementation]:
        """按名称批量查询实现"""
        if not names:
            return []
        return (
            self.db.query(Implementation)
            .filter(Implementation.name.in_(names))
            .all()
        )

    def get_data_resources_by_names(self, names: List[str]) -> List[DataResource]:
        """按名称批量查询数据资源"""
        if not names:
            return []
        return (
            self.db.query(DataResource)
            .filter(DataResource.name.in_(names))
            .all()
        )

    def get_steps_by_names(self, names: List[str]) -> List[Step]:
        """按名称批量查询步骤"""
        if not names:
            return []
        return (
            self.db.query(Step)
            .filter(Step.name.in_(names))
            .all()
        )
    
    def get_business_by_name(self, name: str) -> Optional[Business]:
        """按名称查询业务流程"""
        return self.db.query(Business).filter(Business.name == name).first()

    # ==================== StepImplementation 相关 ====================
    
    def get_step_implementations(self, step_ids: Set[str]) -> Sequence[StepImplementation]:
        """获取步骤-实现关联"""
        if not step_ids:
            return []
        return (
            self.db.query(StepImplementation)
            .filter(StepImplementation.step_id.in_(step_ids))
            .order_by(StepImplementation.id)
            .all()
        )
    
    def get_step_implementations_by_process(self, process_id: str, step_ids: Set[str]) -> List[StepImplementation]:
        """获取指定流程的步骤-实现关联"""
        if not step_ids:
            return []
        return (
            self.db.query(StepImplementation)
            .filter(
                StepImplementation.process_id == process_id,
                StepImplementation.step_id.in_(step_ids)
            )
            .order_by(StepImplementation.id)
            .all()
        )

    def delete_step_implementations(self, process_id: str, step_ids: Set[str]) -> None:
        """删除指定流程的步骤-实现关联"""
        if not step_ids:
            return
        self.db.query(StepImplementation).filter(
            StepImplementation.process_id == process_id,
            StepImplementation.step_id.in_(step_ids)
        ).delete(synchronize_session=False)

    def create_step_implementation(
        self,
        process_id: str,
        step_id: str,
        impl_id: str,
        step_handle: Optional[str] = None,
        impl_handle: Optional[str] = None,
    ) -> StepImplementation:
        """创建步骤-实现关联"""
        link = StepImplementation(
            process_id=process_id,
            step_id=step_id,
            impl_id=impl_id,
            step_handle=step_handle,
            impl_handle=impl_handle,
        )
        self.db.add(link)
        return link

    # ==================== ImplementationLink 相关 ====================

    def get_implementation_links_by_process(
        self,
        process_id: str,
        impl_ids: Set[str],
    ) -> List[ImplementationLink]:
        """获取指定流程的实现-实现关联"""
        if not impl_ids:
            return []
        return (
            self.db.query(ImplementationLink)
            .filter(
                ImplementationLink.process_id == process_id,
                or_(
                    ImplementationLink.from_impl_id.in_(impl_ids),
                    ImplementationLink.to_impl_id.in_(impl_ids),
                ),
            )
            .order_by(ImplementationLink.id)
            .all()
        )

    def delete_implementation_links(self, process_id: str, impl_ids: Set[str]) -> None:
        """删除指定流程的实现-实现关联"""
        if not impl_ids:
            return
        self.db.query(ImplementationLink).filter(
            ImplementationLink.process_id == process_id,
            or_(
                ImplementationLink.from_impl_id.in_(impl_ids),
                ImplementationLink.to_impl_id.in_(impl_ids),
            ),
        ).delete(synchronize_session=False)

    def create_implementation_link(
        self,
        process_id: str,
        from_impl_id: str,
        to_impl_id: str,
        from_handle: Optional[str] = None,
        to_handle: Optional[str] = None,
        edge_type: Optional[str] = None,
        condition: Optional[str] = None,
        label: Optional[str] = None,
    ) -> ImplementationLink:
        """创建实现-实现关联"""
        link = ImplementationLink(
            process_id=process_id,
            from_impl_id=from_impl_id,
            to_impl_id=to_impl_id,
            from_handle=from_handle,
            to_handle=to_handle,
            edge_type=edge_type,
            condition=condition,
            label=label,
        )
        self.db.add(link)
        return link

    # ==================== DataResource 相关 ====================
    
    def get_data_resources_by_ids(self, resource_ids: Set[str]) -> List[DataResource]:
        """批量获取数据资源"""
        if not resource_ids:
            return []
        return (
            self.db.query(DataResource)
            .filter(DataResource.resource_id.in_(resource_ids))
            .order_by(DataResource.resource_id)
            .all()
        )

    def create_or_update_data_resource(
        self,
        resource_id: str,
        name: Optional[str] = None,
        type_: Optional[str] = None,
        system: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DataResource:
        """创建或更新数据资源"""
        resource = (
            self.db.query(DataResource)
            .filter(DataResource.resource_id == resource_id)
            .first()
        )
        if resource is None:
            resource = DataResource(resource_id=resource_id)
            self.db.add(resource)
        
        if name is not None:
            resource.name = name
        if type_ is not None:
            resource.type = type_
        if system is not None:
            resource.system = system
        if location is not None:
            resource.location = location
        if description is not None:
            resource.description = description
        
        return resource

    # ==================== ImplementationDataResource 相关 ====================
    
    def get_implementation_data_resources(
        self, impl_ids: Set[str]
    ) -> Sequence[ImplementationDataResource]:
        """获取实现-数据资源关联"""
        if not impl_ids:
            return []
        return (
            self.db.query(ImplementationDataResource)
            .filter(ImplementationDataResource.impl_id.in_(impl_ids))
            .order_by(ImplementationDataResource.id)
            .all()
        )
    
    def get_implementation_data_resources_by_process(
        self, process_id: str, impl_ids: Set[str]
    ) -> List[ImplementationDataResource]:
        """获取指定流程的实现-数据资源关联"""
        if not impl_ids:
            return []
        return (
            self.db.query(ImplementationDataResource)
            .filter(
                ImplementationDataResource.process_id == process_id,
                ImplementationDataResource.impl_id.in_(impl_ids)
            )
            .order_by(ImplementationDataResource.id)
            .all()
        )

    def delete_implementation_data_resources(self, process_id: str, impl_ids: Set[str]) -> None:
        """删除指定流程的实现-数据资源关联"""
        if not impl_ids:
            return
        self.db.query(ImplementationDataResource).filter(
            ImplementationDataResource.process_id == process_id,
            ImplementationDataResource.impl_id.in_(impl_ids)
        ).delete(synchronize_session=False)

    def create_implementation_data_resource(
        self,
        process_id: str,
        impl_id: str,
        resource_id: str,
        impl_handle: Optional[str] = None,
        resource_handle: Optional[str] = None,
        access_type: Optional[str] = None,
        access_pattern: Optional[str] = None,
    ) -> ImplementationDataResource:
        """创建实现-数据资源关联"""
        link = ImplementationDataResource(
            process_id=process_id,
            impl_id=impl_id,
            resource_id=resource_id,
            impl_handle=impl_handle,
            resource_handle=resource_handle,
            access_type=access_type,
            access_pattern=access_pattern,
        )
        self.db.add(link)
        return link

    # ==================== 事务管理 ====================
    
    def commit(self) -> None:
        """提交事务"""
        self.db.commit()

    def rollback(self) -> None:
        """回滚事务"""
        self.db.rollback()
