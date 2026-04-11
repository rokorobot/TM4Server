from pathlib import Path
import os

# TM4_BASE_PATH defaults to /var/lib/tm4 for VPS deployment.
# For local development, override this in your .env file (e.g., ./local_runtime).
TM4_BASE = Path(os.getenv("TM4_BASE_PATH", "/var/lib/tm4"))

QUEUE_DIR = TM4_BASE / "queue"
RUNS_DIR = TM4_BASE / "runs"
STATE_DIR = TM4_BASE / "state"
ARTIFACTS_DIR = TM4_BASE / "artifacts"
LOGS_DIR = TM4_BASE / "logs"
DECISIONS_DIR = TM4_BASE / "decisions"
PROMOTIONS_DIR = TM4_BASE / "promotions"

QUEUED_DIR = QUEUE_DIR / "queued"
RUNNING_DIR = QUEUE_DIR / "running"
COMPLETED_DIR = QUEUE_DIR / "completed"
FAILED_DIR = QUEUE_DIR / "failed"

# State Layer Configuration
TM4_RUNTIME_ROOT = TM4_BASE
TM4_STATE_ROOT = STATE_DIR
TM4_STATUS_FILE = TM4_STATE_ROOT / "status.json"
TM4_CONTROL_FILE = TM4_STATE_ROOT / "control.json"
TM4_CONTROL_HISTORY_FILE = TM4_STATE_ROOT / "control_history.jsonl"
CURRENT_RUN_FILE = STATE_DIR / "current_run.json"

# API Configuration
API_HOST = os.getenv("TM4_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("TM4_API_PORT", "8000"))

APP_NAME = "tm4server"
POLL_INTERVAL_S = int(os.getenv("TM4_POLL_INTERVAL_S", "3"))

# TM4 Core Integration - VPS Defaults
TM4_CORE_PATH = Path(os.getenv("TM4_CORE_PATH", "/opt/tm4-core"))
TM4CORE_REPO_ROOT = TM4_CORE_PATH
TM4_AUTONOMY_SCRIPT = Path(
    os.getenv("TM4_AUTONOMY_SCRIPT", str(TM4_CORE_PATH / "mvp" / "scripts" / "run_autonomy_loop.py"))
)
TM4_PYTHON_BIN = os.getenv("TM4_PYTHON_BIN", "python")

# Flexible CLI arguments for the autonomy script
TM4_AUTONOMY_EXTRA_ARGS = []  # Extend this if required arguments are found later

# Reporting Configuration
TM4SERVER_REPO_ROOT = Path(__file__).parent.parent
TM4_DOCS_ROOT = Path(os.getenv("TM4_DOCS_ROOT", str(TM4SERVER_REPO_ROOT / "docs" / "experiments")))

# Git Sync Configuration
TM4_AUTO_PUSH_REPORTS = os.getenv("TM4_AUTO_PUSH_REPORTS", "0") == "1"
