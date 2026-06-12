from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.domain import IntegrationJob, ExecutionLog
from app.core.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

jobs = db.query(IntegrationJob).order_by(IntegrationJob.created_at.desc()).limit(5).all()

for job in jobs:
    print(f"\nJob: {job.id}")
    logs = db.query(ExecutionLog).filter(ExecutionLog.job_id == job.id).order_by(ExecutionLog.start_time.asc()).all()
    print("Execution Path:")
    if not logs:
        print(" (no logs)")
    else:
        for log in logs:
            print(f" - {log.node_name}")
