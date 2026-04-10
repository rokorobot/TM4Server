from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, Field


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


RuntimeState = Literal["idle", "running", "paused", "halted"]
HealthState = Literal["ok", "degraded", "down"]
RunStatus = Literal["queued", "running", "success", "failed", "cancelled"]
RunClass = Literal[
    "FAILED_EXECUTION",
    "SATURATED",
    "NO_GRADIENT",
    "CONVERGENT",
    "UNSTABLE",
    "UNCLASSIFIED",
]


class HealthSummary(BaseModel):
    runtime: HealthState = "ok"
    ledger: HealthState = "ok"
    classifier: HealthState = "ok"


class EventItem(BaseModel):
    ts: str
    level: Literal["info", "warning", "error"] = "info"
    message: str


class StatusResponse(BaseModel):
    runtime_state: RuntimeState = "idle"
    current_exp_id: str | None = None
    queue_depth: int = 0
    last_completed_exp: str | None = None
    last_aggregation_at: str | None = None
    last_classification_at: str | None = None
    instance_id: str = "tm4-dev-01"
    tm4_version: str = "dev"
    tm4server_version: str = "dev"
    uptime_s: int = 0
    health: HealthSummary = Field(default_factory=HealthSummary)
    recent_events: list[EventItem] = Field(default_factory=list)


class RunRow(BaseModel):
    exp_id: str
    status: RunStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_s: int | None = None
    fitness_max: float | None = None
    ttc: int | None = None
    violations: int = 0
    classification: RunClass = "UNCLASSIFIED"
    execution_mode: str | None = None
    benchmark_family: str | None = None
    model: str | None = None
    anchor_regime: str | None = None


class RunArtifactLinks(BaseModel):
    root: str
    summary: str | None = None
    report_md: str | None = None
    manifest: str | None = None


class RunMetrics(BaseModel):
    fitness_max: float | None = None
    ttc: int | None = None
    violations: int = 0
    generations: int | None = None


class RunDetailResponse(BaseModel):
    exp_id: str
    status: RunStatus
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    artifacts: RunArtifactLinks
    classification: RunClass = "UNCLASSIFIED"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunsListResponse(BaseModel):
    items: list[RunRow]
    total: int


class ClassificationSummaryResponse(BaseModel):
    counts: dict[RunClass, int]
    confidence_distribution: dict[str, int]


class ClassificationDetailResponse(BaseModel):
    exp_id: str
    classification: RunClass
    confidence: float
    reason: str
    triggered_rules: list[str]
    thresholds: dict[str, float] = Field(default_factory=dict)


class ClassificationRunsResponse(BaseModel):
    items: list[ClassificationDetailResponse]
    total: int


class GradientSummaryResponse(BaseModel):
    ttc_distribution: list[int] = Field(default_factory=list)
    convergence_rate: float = 0.0
    instability_rate: float = 0.0
    saturation_rate: float = 0.0
    no_gradient_rate: float = 0.0
    class_distribution_over_time: list[dict[str, Any]] = Field(default_factory=list)


class ControlActionResponse(BaseModel):
    ok: bool = True
    action: str
    ts: str
    result: Literal["success", "noop", "failed"] = "success"
    message: str


class ControlStateResponse(BaseModel):
    mode: RuntimeState = "idle"
    last_action: dict[str, Any] | None = None


class ControlHistoryItem(BaseModel):
    ts: str
    action: str
    operator: str = "user"
    result: Literal["success", "noop", "failed"] = "success"
    detail: str | None = None


class ControlHistoryResponse(BaseModel):
    items: list[ControlHistoryItem]
    total: int


router = APIRouter(prefix="/api", tags=["tm4-operator-console"])


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    return StatusResponse(
        runtime_state="idle",
        queue_depth=0,
        last_aggregation_at=now_utc(),
        last_classification_at=now_utc(),
        uptime_s=1234,
        recent_events=[
            EventItem(ts=now_utc(), message="Operator console backend stub online."),
            EventItem(ts=now_utc(), message="No active experiment."),
        ],
    )


@router.get("/runs", response_model=RunsListResponse)
def get_runs() -> RunsListResponse:
    rows = [
        RunRow(
            exp_id="EXP-AUT-SERVER-0001",
            status="success",
            started_at=now_utc(),
            completed_at=now_utc(),
            duration_s=78,
            fitness_max=100,
            ttc=1,
            violations=0,
            classification="CONVERGENT",
            execution_mode="VPS",
            benchmark_family="identity_anchor",
            model="qwen2.5:3b",
            anchor_regime="A0_STRICT_IDENTITY",
        )
    ]
    return RunsListResponse(items=rows, total=len(rows))


@router.get("/runs/{exp_id}", response_model=RunDetailResponse)
def get_run_detail(exp_id: str) -> RunDetailResponse:
    return RunDetailResponse(
        exp_id=exp_id,
        status="success",
        metrics=RunMetrics(fitness_max=100, ttc=1, violations=0, generations=1),
        artifacts=RunArtifactLinks(
            root=f"/var/lib/tm4/runs/{exp_id}",
            summary=f"/var/lib/tm4/runs/{exp_id}/run_summary.json",
            report_md=f"/var/lib/tm4/runs/{exp_id}/report.md",
            manifest=f"/var/lib/tm4/runs/{exp_id}/run_manifest.json",
        ),
        classification="CONVERGENT",
        metadata={"instance_id": "tm4-dev-01", "execution_mode": "VPS"},
    )


@router.get("/classification/summary", response_model=ClassificationSummaryResponse)
def get_classification_summary() -> ClassificationSummaryResponse:
    return ClassificationSummaryResponse(
        counts={
            "FAILED_EXECUTION": 0,
            "SATURATED": 2,
            "NO_GRADIENT": 1,
            "CONVERGENT": 4,
            "UNSTABLE": 0,
            "UNCLASSIFIED": 1,
        },
        confidence_distribution={"high": 4, "medium": 3, "low": 1},
    )


@router.get("/classification/runs", response_model=ClassificationRunsResponse)
def get_classification_runs() -> ClassificationRunsResponse:
    items = [
        ClassificationDetailResponse(
            exp_id="EXP-AUT-SERVER-0001",
            classification="CONVERGENT",
            confidence=0.92,
            reason="Fast convergence with no violations and stable metrics.",
            triggered_rules=["ttc_fast", "violations_zero", "variance_low"],
            thresholds={"late_stage_variance_max": 0.01},
        )
    ]
    return ClassificationRunsResponse(items=items, total=len(items))


@router.get("/gradients/summary", response_model=GradientSummaryResponse)
def get_gradients_summary() -> GradientSummaryResponse:
    return GradientSummaryResponse(
        ttc_distribution=[1, 1, 2, 3, 5],
        convergence_rate=0.62,
        instability_rate=0.08,
        saturation_rate=0.22,
        no_gradient_rate=0.11,
        class_distribution_over_time=[
            {"date": "2026-04-01", "CONVERGENT": 2, "SATURATED": 1, "NO_GRADIENT": 0},
            {"date": "2026-04-02", "CONVERGENT": 1, "SATURATED": 0, "NO_GRADIENT": 1},
        ],
    )


def _control_response(action: str, message: str) -> ControlActionResponse:
    return ControlActionResponse(action=action, ts=now_utc(), message=message)


@router.post("/control/pause", response_model=ControlActionResponse)
def pause_runtime() -> ControlActionResponse:
    return _control_response("pause", "Runtime pause requested.")


@router.post("/control/resume", response_model=ControlActionResponse)
def resume_runtime() -> ControlActionResponse:
    return _control_response("resume", "Runtime resume requested.")


@router.post("/control/halt", response_model=ControlActionResponse)
def halt_runtime() -> ControlActionResponse:
    return _control_response("halt", "Runtime halt requested.")


@router.post("/control/aggregate", response_model=ControlActionResponse)
def trigger_aggregate() -> ControlActionResponse:
    return _control_response("aggregate", "Aggregation requested.")


@router.post("/control/classify", response_model=ControlActionResponse)
def trigger_classify_all() -> ControlActionResponse:
    return _control_response("classify_all", "Classification requested for all eligible runs.")


@router.post("/control/classify/{exp_id}", response_model=ControlActionResponse)
def trigger_classify_one(exp_id: str) -> ControlActionResponse:
    return _control_response("classify_one", f"Classification requested for {exp_id}.")


@router.post("/control/refresh", response_model=ControlActionResponse)
def refresh_ledger() -> ControlActionResponse:
    return _control_response("refresh", "Ledger refresh requested.")


@router.get("/control/state", response_model=ControlStateResponse)
def get_control_state() -> ControlStateResponse:
    return ControlStateResponse(
        mode="idle",
        last_action={"type": "aggregate", "timestamp": now_utc(), "operator": "user"},
    )


@router.get("/control/history", response_model=ControlHistoryResponse)
def get_control_history() -> ControlHistoryResponse:
    items = [
        ControlHistoryItem(
            ts=now_utc(),
            action="aggregate",
            operator="user",
            result="success",
            detail="Manual aggregation from operator console.",
        )
    ]
    return ControlHistoryResponse(items=items, total=len(items))


app = FastAPI(title="TM4 Operator Console API", version="0.1.0")
app.include_router(router)
