import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings

from app.api import upload, download, stream, dashboard

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import os

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Agentic API Integration Platform",
    version="0.1.0"
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# NOTE on ordering: this middleware must be registered BEFORE CORSMiddleware
# below, not after. Starlette's Starlette.add_middleware() does
# self.user_middleware.insert(0, ...) — each new registration is prepended,
# so the middleware stack ends up wrapped in the REVERSE of call order: the
# LAST add_middleware() call becomes the OUTERMOST layer. Registering this
# first means CORSMiddleware ends up outside it, so a response built here
# still passes through CORSMiddleware's header injection. Get the order
# backwards and any response built here bypasses CORS entirely — the
# browser then reports a same-looking-but-opaque "Failed to fetch" instead
# of the real error. (Also can't be @app.exception_handler(Exception): that
# routes through ServerErrorMiddleware, which sits outside ALL
# add_middleware() layers regardless of order.) Both failure modes are
# covered by tests/test_error_handling.py.
@app.middleware("http")
async def unhandled_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again or check the server logs."},
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Alternate local dev port (used when 3000 is taken by another project)
        "http://localhost:3010",
        "http://127.0.0.1:3010",
        os.getenv("FRONTEND_URL", "https://apiforge.ai")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["Spec"])
app.include_router(download.router, prefix="/api", tags=["SDK"])
app.include_router(stream.router, prefix="/api", tags=["Agent"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
