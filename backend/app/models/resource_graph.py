from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db.sqlite import Base


class Business(Base):
    __tablename__ = "businesses"

    process_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    entrypoints = Column(Text, nullable=True)  # 可存 JSON 字符串

    edges = relationship("ProcessStepEdge", back_populates="business")


class Step(Base):
    __tablename__ = "steps"

    step_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    step_type = Column(String, nullable=True)

    implementations = relationship("StepImplementation", back_populates="step")


class ProcessStepEdge(Base):
    __tablename__ = "process_step_edges"

    id = Column(Integer, primary_key=True, index=True)
    process_id = Column(String, ForeignKey("businesses.process_id"), nullable=False, index=True)
    from_step_id = Column(String, ForeignKey("steps.step_id"), nullable=False, index=True)
    to_step_id = Column(String, ForeignKey("steps.step_id"), nullable=False, index=True)
    edge_type = Column(String, nullable=True)
    condition = Column(Text, nullable=True)
    label = Column(String, nullable=True)

    business = relationship("Business", back_populates="edges")
    from_step = relationship("Step", foreign_keys=[from_step_id])
    to_step = relationship("Step", foreign_keys=[to_step_id])


class Implementation(Base):
    __tablename__ = "implementations"

    impl_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    system = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    code_ref = Column(Text, nullable=True)

    step_links = relationship("StepImplementation", back_populates="implementation")
    data_resources = relationship(
        "ImplementationDataResource", back_populates="implementation"
    )


class DataResource(Base):
    __tablename__ = "data_resources"

    resource_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    system = Column(String, nullable=True)
    location = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    implementations = relationship(
        "ImplementationDataResource", back_populates="data_resource"
    )


class StepImplementation(Base):
    __tablename__ = "step_implementations"

    id = Column(Integer, primary_key=True, index=True)
    step_id = Column(String, ForeignKey("steps.step_id"), nullable=False)
    impl_id = Column(String, ForeignKey("implementations.impl_id"), nullable=False)

    step = relationship("Step", back_populates="implementations")
    implementation = relationship("Implementation", back_populates="step_links")


class ImplementationDataResource(Base):
    __tablename__ = "implementation_data_resources"

    id = Column(Integer, primary_key=True, index=True)
    impl_id = Column(
        String, ForeignKey("implementations.impl_id"), nullable=False, index=True
    )
    resource_id = Column(
        String, ForeignKey("data_resources.resource_id"), nullable=False, index=True
    )
    access_type = Column(String, nullable=True)
    access_pattern = Column(String, nullable=True)

    implementation = relationship("Implementation", back_populates="data_resources")
    data_resource = relationship("DataResource", back_populates="implementations")
