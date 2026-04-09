from fastapi import APIRouter, HTTPException, Query
import json

from ..state import StateManager
from ..config import TM4_RUNTIME_ROOT, TM4SERVER_REPO_ROOT, TM4CORE_REPO_ROOT

router = APIRouter(tags=["Operator Console"])

# Shared StateManager instance
# In a larger app, this might be a dependency, but for v1 this is direct and safe.
state = StateManager(
    runtime_root=TM4_RUNTIME_ROOT,
    tm4server_repo=TM4SERVER_REPO_ROOT,
    tm4core_repo=TM4CORE_REPO_ROOT
)

@router.get("/status")
async def get_status():
    """Returns current runtime status."""
    try:
        status_data = state.read_status()
        return {"ok": True, "status": status_data}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail={
                "ok": False,
                "error": {
                    "code": "MALFORMED_STATE_FILE", 
                    "message": "status.json could not be parsed"
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "STATUS_READ_ERROR",
                    "message": str(e)
                }
            }
        )

@router.get("/control/state")
async def get_control_state():
    """Returns current control mode."""
    try:
        mode = state.read_control_mode()
        return {"ok": True, "control": {"mode": mode}}
    except (json.JSONDecodeError, ValueError) as e:
         raise HTTPException(
            status_code=500, 
            detail={
                "ok": False,
                "error": {
                    "code": "INVALID_CONTROL_STATE", 
                    "message": f"control.json is corrupted or invalid: {str(e)}"
                }
            }
        )

@router.get("/control/history")
async def get_control_history(limit: int = Query(50, ge=1, le=500)):
    """Returns recent control history entries."""
    try:
        history = state.read_history(limit=limit)
        return {"ok": True, "items": history, "count": len(history)}
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "AUDIT_LOG_CORRUPTION",
                    "message": f"control_history.jsonl is malformed: {str(e)}"
                }
            }
        )

def _set_mode_response(mode: str, source: str = "api"):
    try:
        state.set_control_mode(mode, source=source)
        return {
            "ok": True, 
            "requested_mode": mode, 
            "control": {"mode": mode}
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail={
                "ok": False,
                "error": {
                    "code": "INVALID_MODE_REQUEST",
                    "message": str(e)
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
        )

@router.post("/control/run")
async def set_mode_run():
    """Sets control mode to run."""
    return _set_mode_response("run")

@router.post("/control/pause")
async def set_mode_pause():
    """Sets control mode to pause."""
    return _set_mode_response("pause")

@router.post("/control/halt")
async def set_mode_halt():
    """Sets control mode to halt."""
    return _set_mode_response("halt")

@router.get("/system/version")
async def get_version():
    """Returns system and API version info.
    Resilient metadata endpoint: degrades gracefully if status.json is unreadable.
    """
    try:
        status = state.read_status()
    except Exception:
        status = {}
        
    return {
        "ok": True,
        "api_version": "v1",
        "tm4server_version": status.get("tm4server_version", "unknown"),
        "tm4core_version": status.get("tm4core_version", "unknown"),
        "instance_id": status.get("instance_id", "unknown"),
        "runtime_root": str(TM4_RUNTIME_ROOT)
    }
