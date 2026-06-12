import sys
import zipfile
import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.domain import Artifact

engine = create_engine("postgresql://pranaysb@localhost:5432/apiforge")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

artifact = db.query(Artifact).order_by(Artifact.created_at.desc()).first()

if not artifact:
    print("No artifact found.")
    sys.exit(1)

print(f"Inspecting artifact from job {artifact.job_id}")
with zipfile.ZipFile(io.BytesIO(artifact.zip_data)) as z:
    for filename in z.namelist():
        print(f"\n========== {filename} ==========\n")
        print(z.read(filename).decode('utf-8'))
