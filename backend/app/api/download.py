from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.domain import Artifact
import io

router = APIRouter()

@router.get("/download/{job_id}")
def download_sdk(job_id: str, db: Session = Depends(get_db)):
    artifact = db.query(Artifact).filter(Artifact.job_id == job_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found for this job")
    
    zip_buffer = io.BytesIO(artifact.zip_data)
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename=apiforge_sdk_job_{job_id}.zip"}
    )
