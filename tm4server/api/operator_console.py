from fastapi import APIRouter, HTTPException, Query
import json

from ..state import StateManager, atomic_write_json, utc_now_iso, git_short_commit, read_json_strict
from ..config import TM4_RUNTIME_ROOT, TM4SERVER_REPO_ROOT, TM4CORE_REPO_ROOT, RUNS_DIR, DECISIONS_DIR
from ..analysis.classifier import ExperimentClassifier
from ..analysis.pareto_analyzer import ParetoAnalyzer
from ..analysis.decision_engine import DecisionEngine

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
        # Enrich status with live workload metrics from runs/
        workload = state.get_workload_summary(RUNS_DIR)
        status_data.update(workload)
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

@router.post("/runs/launch")
async def launch_run():
    """Allocates a new experiment ID, creates the environment, and queues the workload."""
    try:
        exp_id = state.allocate_next_exp_id(RUNS_DIR)
        run_dir = RUNS_DIR / exp_id
        
        created_at = utc_now_iso()
        
        # 1. Immutable Launch Intent
        manifest = {
            "schema_version": 1,
            "exp_id": exp_id,
            "experiment_id": exp_id, # for backward compatibility
            "task": "autonomy",
            "model": "default",
            "created_at": created_at,
            "submitted_at": created_at,
            "requested_by": "operator_console",
            "tm4server_version": git_short_commit(TM4SERVER_REPO_ROOT) if TM4SERVER_REPO_ROOT else None,
            "status": "queued"
        }
        atomic_write_json(run_dir / "run_manifest.json", manifest)
        
        # 2. Live Execution State
        runtime_state = {
            "status": "queued",
            "created_at": created_at,
            "updated_at": created_at
        }
        atomic_write_json(run_dir / "runtime_state.json", runtime_state)
        
        # Trigger an immediate status update so the UI sees the new pending count
        # In a real system, we'd wait for a poll, but for a better UX we can write status now
        try:
            current_status = state.read_status()
            workload = state.get_workload_summary(RUNS_DIR)
            current_status.update(workload)
            state.write_status(
                runtime_state=current_status.get("runtime_state", "idle"),
                current_exp_id=current_status.get("current_exp_id"),
                queue_depth=workload.get("pending", 0),
                last_completed_exp_id=current_status.get("last_completed_exp_id"),
                extra=current_status.get("extra")
            )
        except Exception:
            pass # Non-critical if pre-emptive status update fails

        return {
            "ok": True,
            "status": "queued",
            "exp_id": exp_id,
            "run_dir": str(run_dir)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "LAUNCH_FAILURE",
                    "message": str(e)
                }
            }
        )

@router.get("/runs")
async def get_runs(limit: int = Query(50, ge=1, le=500)):
    """Returns a list of normalized run metadata from the runs/ directory."""
    try:
        items = state.list_runs(RUNS_DIR, limit=limit)
        return {"ok": True, "items": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "RUNS_LIST_ERROR",
                    "message": str(e)
                }
            }
        )

@router.get("/runs/{exp_id}")
async def get_run_detail(exp_id: str):
    """Returns raw JSON payloads (manifest, state, summary) for a specific run."""
    try:
        detail = state.get_run_detail(RUNS_DIR, exp_id)
        return {"ok": True, "detail": detail}
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": {
                    "code": "RUN_NOT_FOUND",
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
                    "code": "RUN_DETAIL_ERROR",
                    "message": str(e)
                }
            }
        )
@router.post("/runs/{exp_id}/classify")
async def classify_run(exp_id: str):
    """Triggers deterministic semantic interpretation of a run based on terminal evidence."""
    try:
        run_dir = RUNS_DIR / exp_id
        if not run_dir.exists():
             raise FileNotFoundError(f"Run directory not found: {exp_id}")
             
        summary_path = run_dir / "run_summary.json"
        if not summary_path.exists():
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "error": {
                        "code": "MISSING_EVIDENCE",
                        "message": "Scientific classification requires a terminal run_summary.json"
                    }
                }
            )
            
        summary = read_json_strict(summary_path)
        
        # Initialize engine and interpret
        classifier = ExperimentClassifier()
        result = classifier.classify(summary)
        
        # Save structurally self-describing artifact
        atomic_write_json(run_dir / "classification.json", result)
        
        return {"ok": True, "classification": result.get("classification")}
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"ok": False, "error": {"code": "RUN_NOT_FOUND", "message": str(e)}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": {"code": "CLASSIFY_ERROR", "message": str(e)}}
        )

@router.get("/runs/{exp_id}/classification")
async def get_run_classification(exp_id: str):
    """Returns previous scientific classification artifact if it exists."""
    try:
        run_dir = RUNS_DIR / exp_id
        path = run_dir / "classification.json"
        
        if not path.exists():
             return {
                 "ok": True, 
                 "classification": None, 
                 "message": "Run not yet classified."
             }
             
        data = read_json_strict(path)
        return {"ok": True, "classification": data.get("classification")}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": {"code": "CLASSIFICATION_FETCH_ERROR", "message": str(e)}}
        )

@router.get("/analysis/gradients")
async def get_gradient_analysis():
    """Returns on-demand research-grade insights by aggregating all classified runs."""
    try:
        report = state.build_regime_index(RUNS_DIR)
        return {"ok": True, "report": report}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "ANALYSIS_ERROR",
                    "message": f"Failed to compute gradient index: {str(e)}"
                }
            }
        )

@router.get("/analysis/pareto")
async def get_pareto_analysis():
    """Returns cross-model comparisons (leaderboards) per task using governance-weighted scoring."""
    try:
        from tm4server.analysis.pareto_analyzer import ParetoAnalyzer
        report = state.build_regime_index(RUNS_DIR)
        analyzer = ParetoAnalyzer()
        pareto_report = analyzer.analyze_report(report)
        return {"ok": True, "report": pareto_report}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "PARETO_ERROR",
                    "message": f"Failed to compute model Pareto rankings: {str(e)}"
                }
            }
        )

@router.get("/analysis/decisions")
async def get_projected_decisions():
    """Calculates current 'Projected Decisions' for all tasks without persisting."""
    try:
        report = state.build_regime_index(RUNS_DIR)
        pareto = ParetoAnalyzer().analyze_report(report)
        engine = DecisionEngine()
        
        decisions = {}
        for task, ranks in pareto.get("tasks", {}).items():
            decisions[task] = engine.evaluate_task(task, ranks)
            
        return {
            "ok": True, 
            "report": {
                "version": engine.VERSION,
                "decisions": decisions
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": {"code": "DECISION_ERROR", "message": str(e)}}
        )

@router.post("/tasks/{task}/decide")
async def lock_task_decision(task: str):
    """Computes and PERSISTS a formal governance decision for a task."""
    try:
        # 1. Compute current projected decision
        report = state.build_regime_index(RUNS_DIR)
        pareto = ParetoAnalyzer().analyze_report(report)
        ranks = pareto.get("tasks", {}).get(task)
        
        if not ranks:
            raise ValueError(f"No evidence found for task '{task}'")
            
        engine = DecisionEngine()
        decision = engine.evaluate_task(task, ranks)
        
        # 2. Persist to decisions/{task}.json
        decision_path = DECISIONS_DIR / f"{task}.json"
        atomic_write_json(decision_path, decision)
        
        return {"ok": True, "decision": decision, "path": str(decision_path)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": {"code": "DECISION_LOCK_ERROR", "message": str(e)}}
        )
