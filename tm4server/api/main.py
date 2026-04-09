from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from .operator_console import router as operator_router
import os
from pathlib import Path

app = FastAPI(title="TM4Server API")

# Optional environment-guarded CORS for local UI development
# Enable with TM4_API_CORS_ALLOWED=true
if os.getenv("TM4_API_CORS_ALLOWED", "").lower() == "true":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Enforces uniform error envelope for all HTTP exceptions."""
    detail = exc.detail
    # If the handler already provided a structured error, use it directly
    if isinstance(detail, dict) and "error" in detail:
        # Ensure 'ok' is present
        if "ok" not in detail:
            detail["ok"] = False
        return JSONResponse(status_code=exc.status_code, content=detail)
    
    # Map standard FastAPI/Starlette errors (404, 405, etc.) to uniform envelope
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(detail)
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Enforces uniform error envelope for FastAPI validation errors (422)."""
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Fallback for unexpected internal errors, hiding implementation details."""
    # Note: In production, log 'exc' here.
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected server error occurred."
            }
        }
    )

@app.get("/healthz", tags=["System"])
async def healthz():
    """Basic health check for the API process."""
    return {"ok": True}

# 📡 API Routing
app.include_router(operator_router, prefix="/api")

# 🖥️ Operator Console UI
STATIC_DIR = Path(__file__).parent / "static"

@app.get("/operator")
async def get_operator():
    """Serves the Operator Console entrypoint."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(
            status_code=404, 
            content={
                "ok": False, 
                "error": {
                    "code": "UI_NOT_BUILT", 
                    "message": "Operator Console UI has not been built. Run 'npm run build' in /ui."
                }
            }
        )
    return FileResponse(index_file)

# Mount static assets (JS/CSS) at /static prefix if built
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn
    from tm4server.config import API_HOST, API_PORT
    uvicorn.run("tm4server.api.main:app", host=API_HOST, port=API_PORT)
