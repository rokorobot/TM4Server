import os
import json
from pathlib import Path
from tm4server.execution import artifacts

run_id = "RUN-INVALID-V1"
mock_dir = Path("mock_runs") / run_id
os.makedirs(mock_dir, exist_ok=True)

print("\n--- Testing Strict Manifest Validation (forbidden fields) ---")
try:
    artifacts.write_manifest(mock_dir, {
        "run_id": run_id,
        "exp_id": "EXP-FORBIDDEN",
        "workload_type": "contract-validation",
        "requested_by": "test-suite",
        "created_at": artifacts.utc_now_z(),
        "started_at": artifacts.utc_now_z() # FORBIDDEN
    })
    print("[X] FAILED: Allowed manifest with forbidden fields")
except ValueError as e:
    print(f"[OK] Caught expected error: {e}")

print("--- Testing Immutability Violation ---")
artifacts.write_manifest(mock_dir, {
    "run_id": run_id,
    "exp_id": "EXP-V1-FAIL",
    "workload_type": "contract-validation",
    "requested_by": "test-suite",
    "created_at": artifacts.utc_now_z()
})

try:
    artifacts.write_manifest(mock_dir, {"run_id": "OVERWRITE"})
    print("[X] FAILED: Allowed manifest overwrite")
except FileExistsError as e:
    print(f"[OK] Caught expected error: {e}")

print("\n--- Testing started_at Requirement Violation ---")
try:
    # No existing file, no started_at provided
    status_path = mock_dir / "status.json"
    if status_path.exists(): os.remove(status_path)
    artifacts.write_status(mock_dir, {"status": "queued"})
    print("[X] FAILED: Allowed status write without started_at")
except ValueError as e:
    print(f"[OK] Caught expected error: {e}")

print("\n--- Testing Timestamp Format Violation (status) ---")
try:
    artifacts.write_status(mock_dir, {
        "status": "running",
        "started_at": "INVALID_TS"
    })
    print("[X] FAILED: Allowed invalid started_at format")
except ValueError as e:
    print(f"[OK] Caught expected error: {e}")

print("\n--- Testing Schema Violation (status enum) ---")
try:
    artifacts.write_status(mock_dir, {
        "status": "INVALID_STATUS",
        "started_at": artifacts.utc_now_z()
    })
    print("[X] FAILED: Allowed invalid status enum")
except ValueError as e:
    print(f"[OK] Caught expected error: {e}")

print("\n--- Testing Schema Violation (summary) ---")
try:
    artifacts.write_summary(mock_dir, {"status": "running"})
    print("[X] FAILED: Allowed non-terminal summary")
except ValueError as e:
    print(f"[OK] Caught expected error: {e}")

# Create a manually mangled artifact for the validator to catch
print("\n--- Creating mangled artifact for script validator ---")
(mock_dir / "status.json").write_text("not-json") 

print("\n--- Creating drift artifact for script validator ---")
drift_dir = Path("mock_runs") / "RUN-DRIFT"
os.makedirs(drift_dir, exist_ok=True)
artifacts.write_manifest(drift_dir, {
    "run_id": "RUN-DRIFT",
    "exp_id": "EXP-CONSISTENT",
    "workload_type": "drift-test",
    "requested_by": "test-suite",
    "created_at": artifacts.utc_now_z()
})
# Manually write status with drifting exp_id
status_drift = {
    "schema_version": "v1",
    "run_id": "RUN-DRIFT",
    "status": "running",
    "instance_id": "executor-1",
    "worker_pid": 1234,
    "started_at": artifacts.utc_now_z(),
    "updated_at": artifacts.utc_now_z(),
    "exp_id": "EXP-DRIFTED" # DRIFT!
}
(drift_dir / "status.json").write_text(json.dumps(status_drift))

print(f"Invalid mock setup complete at {mock_dir}")
