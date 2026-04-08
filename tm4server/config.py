from pathlib import Path
import os

# TM4_BASE_PATH defaults to ./local_runtime for local development.
# On the server, set this to /var/lib/tm4 via environment variable.
TM4_BASE = Path(os.getenv("TM4_BASE_PATH", "./local_runtime"))

QUEUE_DIR = TM4_BASE / "queue"
RUNS_DIR = TM4_BASE / "runs"
STATE_DIR = TM4_BASE / "state"
ARTIFACTS_DIR = TM4_BASE / "artifacts"
LOGS_DIR = TM4_BASE / "logs"

QUEUED_DIR = QUEUE_DIR / "queued"
RUNNING_DIR = QUEUE_DIR / "running"
COMPLETED_DIR = QUEUE_DIR / "completed"
FAILED_DIR = QUEUE_DIR / "failed"

STATUS_FILE = STATE_DIR / "status.json"
CURRENT_RUN_FILE = STATE_DIR / "current_run.json"

APP_NAME = "tm4server"
POLL_INTERVAL_S = int(os.getenv("TM4_POLL_INTERVAL_S", "3"))

# TM4 Core Integration
TM4_CORE_PATH = Path(os.getenv("TM4_CORE_PATH", r"C:\Users\Robert\TM4"))
TM4_AUTONOMY_SCRIPT = Path(
    os.getenv("TM4_AUTONOMY_SCRIPT", str(TM4_CORE_PATH / "mvp" / "scripts" / "run_autonomy_loop.py"))
)
TM4_PYTHON_BIN = os.getenv("TM4_PYTHON_BIN", "python")

# Flexible CLI arguments for the autonomy script
TM4_AUTONOMY_EXTRA_ARGS = []  # Extend this if required arguments are found later

# Git Sync Configuration
TM4_AUTO_PUSH_REPORTS = os.getenv("TM4_AUTO_PUSH_REPORTS", "0") == "1"
