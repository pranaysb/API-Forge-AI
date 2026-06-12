import uvicorn
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

@app.get("/api/v1/secure-data")
def get_secure_data(authorization: str = Header(None)):
    if not authorization or authorization != "Bearer VALID_TOKEN":
        raise HTTPException(
            status_code=401, 
            detail="Unauthorized. Missing or invalid Authorization header. Expected format: 'Authorization: Bearer VALID_TOKEN'"
        )
    return {"data": "This is highly secure data", "status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
