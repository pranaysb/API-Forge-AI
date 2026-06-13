from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.domain import Project, IntegrationJob
from app.services.openapi_parser import parse_spec_content, extract_endpoints
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/upload")
@limiter.limit("5/minute")
async def upload_spec(request: Request, file: UploadFile = File(...), project_name: str = "Demo Project", db: Session = Depends(get_db)):
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10MB.")
    
    content = await file.read()
    
    # Also verify if file.size was missing
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10MB.")
        
    try:
        content_str = content.decode("utf-8")
        parsed_json = parse_spec_content(content_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    endpoints_data = extract_endpoints(parsed_json)
    
    # Check if project exists or create new
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        project = Project(name=project_name, description="A demonstration project")
        db.add(project)
        db.commit()
        db.refresh(project)

    job = IntegrationJob(
        project_id=project.id,
        spec_content=content_str,
        status="PENDING"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "message": "Spec uploaded and Job created successfully", 
        "project_id": project.id,
        "job_id": job.id, 
        "endpoints_count": len(endpoints_data)
    }
