import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, LargeBinary, ForeignKey, JSON, Boolean, Integer
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("IntegrationJob", back_populates="project", cascade="all, delete-orphan")

class IntegrationJob(Base):
    __tablename__ = "integration_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    spec_content = Column(Text, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="jobs")
    logs = relationship("ExecutionLog", back_populates="job", cascade="all, delete-orphan", order_by="ExecutionLog.created_at")
    artifact = relationship("Artifact", back_populates="job", uselist=False, cascade="all, delete-orphan")

class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("integration_jobs.id"), nullable=False)
    node_name = Column(String, nullable=False)
    state_delta = Column(JSON, nullable=True)  # Store the diff of what changed
    created_at = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    job = relationship("IntegrationJob", back_populates="logs")

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("integration_jobs.id"), nullable=False, unique=True)
    zip_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("IntegrationJob", back_populates="artifact")
