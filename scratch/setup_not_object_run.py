import json
from pathlib import Path

run_id = "RUN-NOT-OBJECT"
mock_dir = Path("mock_runs") / run_id
mock_dir.mkdir(parents=True, exist_ok=True)

# Manifest exists
(mock_dir / "run_manifest.json").write_text(json.dumps({
    "run_id": run_id,
    "exp_id": "EXP-NOT-OBJECT",
    "workload_type": "object-test"
}))

# Status is NOT AN OBJECT (list)
(mock_dir / "status.json").write_text(json.dumps(["this", "is", "not", "an", "object"]))

# Summary exists
(mock_dir / "run_summary.json").write_text(json.dumps({
    "run_id": run_id,
    "status": "completed"
}))

print(f"Mock not-object directory created at {mock_dir}")
