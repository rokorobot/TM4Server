import os
from pathlib import Path
from tm4server.execution import artifacts

run_id = "RUN-VALID-V1"
mock_dir = Path("mock_runs") / run_id
os.makedirs(mock_dir, exist_ok=True)

# 1. Manifest
artifacts.write_manifest(mock_dir, {
    "run_id": run_id,
    "exp_id": "EXP-V1-TEST",
    "workload_type": "contract-validation",
    "requested_by": "test-suite",
    "created_at": artifacts.utc_now_z()
})

# 2. Status
artifacts.write_status(mock_dir, {
    "status": "running",
    "started_at": artifacts.utc_now_z()
})

# 3. Summary
artifacts.write_summary(mock_dir, {
    "status": "success",
    "started_at": artifacts.utc_now_z(),
    "completed_at": artifacts.utc_now_z()
})

print(f"Generated valid spec-v1 run at {mock_dir}")
