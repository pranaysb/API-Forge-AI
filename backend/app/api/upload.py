from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.domain import Project, IntegrationJob
from app.services.openapi_parser import parse_spec_content, extract_endpoints

router = APIRouter()

@router.post("/upload")
async def upload_spec(file: UploadFile = File(...), project_name: str = "Demo Project", db: Session = Depends(get_db)):
    content = await file.read()
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
