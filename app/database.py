from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, unique=True, index=True)
    status = Column(String)
    conclusion = Column(String)
    commit_sha = Column(String)
    branch = Column(String)
    logs = Column(Text, nullable=True)
    diagnosis = Column(JSON, nullable=True)
    fix_plan = Column(JSON, nullable=True)
    approval_status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

class FixKnowledge(Base):
    __tablename__ = "fix_knowledge"
    id = Column(Integer, primary_key=True)
    problem_signature = Column(String, unique=True)
    solution = Column(Text)
    success_count = Column(Integer, default=1)

Base.metadata.create_all(bind=engine)