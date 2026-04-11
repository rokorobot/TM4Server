import json
from pathlib import Path

run_id = "RUN-FALLBACK"
mock_dir = Path("mock_runs") / run_id
mock_dir.mkdir(parents=True, exist_ok=True)

# Manifest exists
(mock_dir / "run_manifest.json").write_text(json.dumps({
    "run_id": run_id,
    "exp_id": "EXP-FALLBACK-001",
    "workload_type": "fallback-test"
}))

# Status exists (Truth for status and instance_id)
(mock_dir / "status.json").write_text(json.dumps({
    "instance_id": "vps-fallback-node",
    "status": "busy"
}))

# Summary is MALFORMED
(mock_dir / "run_summary.json").write_text("{ \"status\": \"interrupted\", \"corrupt\": ")

print(f"Mock fallback directory created at {mock_dir}")
