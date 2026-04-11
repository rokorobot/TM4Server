from fastapi import APIRouter, HTTPException, Query, Request
import json

from ..state import StateManager, atomic_write_json, utc_now_iso, git_short_commit, read_json_strict
from ..config import TM4_RUNTIME_ROOT, TM4SERVER_REPO_ROOT, TM4CORE_REPO_ROOT, RUNS_DIR, DECISIONS_DIR
from ..analysis.classifier import ExperimentClassifier
from ..analysis.pareto_analyzer import ParetoAnalyzer
from ..analysis.decision_engine import DecisionEngine
from ..promoter import PromotionManager

router = APIRouter(tags=["Operator Console"])

# Shared StateManager instance
# In a larger app, this might be a dependency, but for v1 this is direct and safe.
state = StateManager(
    runtime_root=TM4_RUNTIME_ROOT,
    tm4server_repo=TM4SERVER_REPO_ROOT,
    tm4core_repo=TM4CORE_REPO_ROOT
)
promoter = PromotionManager()

@router.get("/status")
async def get_status():
    """Returns current runtime status, joining operator intent with execution reality."""
    try:
        status_data = state.read_status()
        
        # 1. Enrich status with live workload metrics from runs/
        workload = state.get_workload_summary(RUNS_DIR)
        status_data.update(workload)
        
        # 2. Add Execution Spine Awareness
        control_mode = state.get_control_state()
        active_run = state.get_active_run()
        
        return {
            "ok": True, 
            "status": status_data,
            "control_state": control_mode,
            "runtime_state": status_data.get("runtime_state", "busy" if active_run else "idle"),
            "active_run": active_run
        }
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
    """Sets control mode to run if the execution spine is idle."""
    try:
        active_run = state.get_active_run()
        if active_run is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "ok": False,
                    "error": {
                        "code": "RUNTIME_BUSY",
                        "message": "A run is already active. Phase 2A allows only one run at a time."
                    },
                    "active_run": active_run
                }
            )
        return _set_mode_response("run")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": {
                    "code": "RUN_REQUEST_ERROR",
                    "message": str(e)
                }
            }
        )

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
    """Queued run launch is disabled in Phase 2A. Core spine uses POST /control/run."""
    raise HTTPException(
        status_code=409,
        detail={
            "ok": False,
            "error": {
                "code": "PHASE_MISMATCH",
                "message": "Queued run launch is disabled in Phase 2A. Use POST /api/control/run for the single-run execution spine."
            }
        }
    )

@router.get("/runs")
async def get_runs(
    limit: int = Query(50, ge=1, le=500),
    mode: str = Query("strict", regex="^(strict|compat)$")
):
    """
    Returns a list of normalized run metadata.
    mode=strict (default): Only Spec v1 conformant runs.
    mode=compat: Includes legacy runs with conformance flags.
    """
    try:
        strict = (mode == "strict")
        items = state.list_runs(RUNS_DIR, limit=limit, strict=strict)
        return {"ok": True, "mode": mode, "items": items, "count": len(items)}
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

@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    mode: str = Query("strict", regex="^(strict|compat)$")
):
    """
    Returns the canonical Run Record (intent, execution, outcome, governance).
    mode=strict (default): Fails if run is non-conformant.
    """
    try:
        strict = (mode == "strict")
        record = state.get_run_detail(RUNS_DIR, run_id, strict=strict)
        return {"ok": True, "mode": mode, "run": record}
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
@router.post("/runs/{run_id}/classify")
async def classify_run(run_id: str):
    """
    Triggers scientific classification for a completed run.
    Uses tm4-core's classification engine via classifier.py.
    """
    try:
        run_dir = RUNS_DIR / run_id
        if not run_dir.exists():
             raise FileNotFoundError(f"Run directory not found: {run_id}")
             
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

@router.get("/runs/{run_id}/logs")
async def get_run_logs(
    run_id: str, 
    stream: str = Query("stdout", regex="^(stdout|stderr)$"),
    tail: int = Query(100, ge=1, le=1000)
):
    """Returns the last N lines of stdout or stderr for a specific run."""
    try:
        run_dir = RUNS_DIR / run_id
        if not run_dir.exists():
             raise FileNotFoundError(f"Run directory not found: {run_id}")
             
        log_file = run_dir / f"{stream}.log"
        if not log_file.exists():
            return {
                "ok": True,
                "run_id": run_id,
                "stream": stream,
                "tail": tail,
                "content": f"--- No {stream} log available ---",
                "truncated": False
            }
            
        # Read the tail of the file
        # We read tail + 1 to accurately detect truncation
        lines = []
        with log_file.open("r", encoding="utf-8", errors="replace") as f:
            from collections import deque
            lines = list(deque(f, tail + 1))
            
        is_truncated = False
        if len(lines) > tail:
            is_truncated = True
            lines = lines[1:] # Discard the extra line
            
        return {
            "ok": True,
            "run_id": run_id,
            "stream": stream,
            "tail": tail,
            "content": "".join(lines),
            "truncated": is_truncated
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"ok": False, "error": {"code": "RUN_NOT_FOUND", "message": str(e)}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": {"code": "LOGS_READ_ERROR", "message": str(e)}}
        )

@router.get("/runs/{run_id}/classification")
async def get_run_classification(run_id: str):
    """Returns previous scientific classification artifact if it exists."""
    try:
        run_dir = RUNS_DIR / run_id
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
async def get_decisions_v2():
    """Calculates authoritative 'Triple-View' decisions (Projected, Locked, Effective) with v1.6 Promotion state."""
    try:
        from tm4server.analysis.pareto_analyzer import ParetoAnalyzer
        report = state.build_regime_index(RUNS_DIR)
        pareto = ParetoAnalyzer().analyze_report(report)
        engine = DecisionEngine()
        
        # 1. Compute Projected Decisions
        projected_map = {}
        for task, ranks in pareto.get("tasks", {}).items():
            projected_map[task] = engine.evaluate_task(task, ranks)
            
        # 2. Load Locked Decisions
        locked_map = {}
        if DECISIONS_DIR.exists():
            for f in DECISIONS_DIR.glob("*.json"):
                try:
                    locked_data = json.loads(f.read_text(encoding="utf-8"))
                    locked_map[locked_data["task"]] = locked_data
                except Exception:
                    continue
        
        # 3. Build Triple-View Report
        all_tasks = sorted(list(set(projected_map.keys()) | set(locked_map.keys())))
        tasks_report = {}
        
        for task in all_tasks:
            proj = projected_map.get(task)
            lock = locked_map.get(task)
            
            # Resolution: Locked artifacts are authoritative
            eff = lock or proj
            
            drift, d_type, d_reason = detect_drift_v2(proj, lock)
            
            # Load active promotion state
            active_promo = promoter.get_active_promotion(task)
            is_active = False
            if active_promo and lock:
                is_active = active_promo.get("winner_model") == lock.get("winner_model")

            tasks_report[task] = {
                "task": task,
                "projected": proj,
                "locked": lock,
                "effective": eff,
                "has_locked": lock is not None,
                "has_drift": drift,
                "drift_type": d_type,
                "drift_reason": d_reason,
                "is_active": is_active,
                "lock_available": proj is not None
            }
            
        return {
            "ok": True, 
            "report": {
                "version": "v1.6",
                "generated_at": utc_now_iso(),
                "tasks": tasks_report
            }
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail={"ok": False, "error": {"code": "DECISION_ERROR", "message": str(e)}})

@router.post("/tasks/{task}/decide")
async def lock_task_decision(task: str, request: Request, force: bool = Query(False)):
    """Authoritatively locks a decision for a task. Requires ?force=true to overwrite."""
    try:
        body = await request.json()
        actor = body.get("actor", "manual_operator")
        
        from ..state import get_system_actor, atomic_write_json
        target_path = DECISIONS_DIR / f"{task}.json"
        existing_locked = None
        
        if target_path.exists():
            if not force:
                raise HTTPException(
                    status_code=409,
                    detail={"ok": False, "error": {"code": "DECISION_ALREADY_LOCKED", "message": f"Task '{task}' is already locked. Use force=true to overwrite."}}
                )
            # Preserve lineage
            try:
                existing_locked = json.loads(target_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 1. Compute current projection
        report = state.build_regime_index(RUNS_DIR)
        pareto = ParetoAnalyzer().analyze_report(report)
        ranks = pareto.get("tasks", {}).get(task)
        
        if not ranks:
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "error": {"code": "INSUFFICIENT_EVIDENCE", "message": f"No evidence found for task '{task}' to lock a decision."}}
            )
            
        engine = DecisionEngine()
        decision = engine.evaluate_task(task, ranks)
        
        # 2. Upgrade to Authoritative Locked Artifact
        decision["locked"] = True
        decision["locked_at"] = utc_now_iso()
        decision["decision_path"] = str(target_path)
        decision["actor"] = actor
        decision["system_actor"] = get_system_actor()
        
        if existing_locked:
            decision["previous_locked_at"] = existing_locked.get("locked_at")
            decision["supersedes_decision_path"] = str(target_path) # same path, but logically a new generation
            
        atomic_write_json(target_path, decision)
        
        return {"ok": True, "decision": decision}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"ok": False, "error": {"code": "LOCK_ERROR", "message": str(e)}})

@router.post("/tasks/{task}/promote")
async def promote_task_default(task: str, request: Request):
    """Promotes a locked winner to system default mapping."""
    try:
        body = await request.json()
        actor = body.get("actor", "manual_operator")
        
        target_path = DECISIONS_DIR / f"{task}.json"
        
        if not target_path.exists():
             raise HTTPException(
                status_code=404,
                detail={"ok": False, "error": {"code": "DECISION_NOT_FOUND", "message": f"No locked decision found for task '{task}'. Lock a decision first."}}
            )
             
        decision = json.loads(target_path.read_text(encoding="utf-8"))
        promotion = promoter.promote(task, decision, actor)
        
        return {"ok": True, "promotion": promotion}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"ok": False, "error": {"code": "PROMOTION_ERROR", "message": str(e)}})

@router.post("/tasks/{task}/revoke")
async def revoke_task_promotion(task: str, request: Request):
    """Revokes an active model promotion for a task."""
    try:
        body = await request.json()
        actor = body.get("actor", "manual_operator")
        
        result = promoter.revoke(task, actor)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={"ok": False, "error": {"code": "REVOKE_ERROR", "message": str(e)}})

@router.get("/tasks/{task}/promotion-history")
async def get_promotion_history(task: str):
    """Returns the immutable audit log for task promotions."""
    try:
        history = promoter.get_history(task)
        return {"ok": True, "task": task, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"ok": False, "error": {"code": "HISTORY_ERROR", "message": str(e)}})
def detect_drift_v2(projected: dict | None, locked: dict | None) -> tuple[bool, str, str | None]:
    """Detects tier-based governance drift between live evidence and locked decisions."""
    if not locked:
        return False, "NO_DRIFT", None
    
    if not projected:
        # A locked decision exists but current evidence is too thin to project anything.
        return True, "GATES_DEGRADED", "Current evidence is insufficient to sustain a projection."

    # Tier 1: Winner Changed
    if projected.get("winner_model") != locked.get("winner_model"):
        return True, "WINNER_CHANGED", f"Projected winner {projected.get('winner_model')} differs from locked."
    
    # Tier 2: Status Changed
    if projected.get("promotion_status") != locked.get("promotion_status"):
        return True, "STATUS_CHANGED", f"Projected status {projected.get('promotion_status')} differs from locked."
    
    # Tier 3: Individual Gate Degradation
    p_checks = projected.get("checks", {})
    l_checks = locked.get("checks", {})
    
    for gate in ["reliability_pass", "stability_pass", "margin_pass", "governance_clear"]:
        if l_checks.get(gate) and not p_checks.get(gate):
            return True, "GATES_DEGRADED", f"Gate {gate} no longer passing in live evidence."
            
        if not l_checks.get(gate) and p_checks.get(gate):
            return True, "GATES_IMPROVED", f"Gate {gate} now passing in live evidence."

    return False, "NO_DRIFT", None
