from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class RunManifest:
    run_id: str
    exp_id: str
    workload_type: str
    created_at: str
    started_at: Optional[str]
    status: str
    runtime_root: str
    requested_by: str = "operator"
    trigger_source: str = "control_api"

@dataclass(slots=True)
class RunStatus:
    run_id: str
    status: str
    phase: str
    started_at: str
    updated_at: str
    pid: Optional[int] = None

@dataclass(slots=True)
class RunSummary:
    run_id: str
    exp_id: str
    status: str # "success" or "failed"
    started_at: str
    completed_at: str
    duration_s: int
    exit_code: int
    artifact_root: str
    error: Optional[str] = None
