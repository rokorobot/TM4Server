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
