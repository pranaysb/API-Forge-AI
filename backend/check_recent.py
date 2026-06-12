from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.domain import IntegrationJob
from app.core.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

jobs = db.query(IntegrationJob).order_by(IntegrationJob.created_at.desc()).limit(10).all()

print("Recent Jobs:")
for job in jobs:
    print(f"- {job.id} at {job.created_at} status {job.status}")
