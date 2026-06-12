from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.domain import Project, IntegrationJob, ExecutionLog

router = APIRouter()

@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [{"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at} for p in projects]

@router.get("/projects/{project_id}/jobs")
def list_jobs(project_id: str, db: Session = Depends(get_db)):
    jobs = db.query(IntegrationJob).filter(IntegrationJob.project_id == project_id).order_by(IntegrationJob.created_at.desc()).all()
    return [{"id": j.id, "status": j.status, "created_at": j.created_at, "completed_at": j.completed_at} for j in jobs]

@router.get("/jobs/{job_id}/timeline")
def get_job_timeline(job_id: str, db: Session = Depends(get_db)):
    job = db.query(IntegrationJob).filter(IntegrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    logs = db.query(ExecutionLog).filter(ExecutionLog.job_id == job_id).order_by(ExecutionLog.created_at.asc()).all()
    
    return {
        "job_id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "logs": [{"id": l.id, "node_name": l.node_name, "state_delta": l.state_delta, "created_at": l.created_at, "start_time": l.start_time, "end_time": l.end_time, "duration_ms": l.duration_ms} for l in logs]
    }
