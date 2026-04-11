import json
from pathlib import Path

run_id = "RUN-TEST-20260411"
mock_dir = Path("mock_runs") / run_id
mock_dir.mkdir(parents=True, exist_ok=True)

(mock_dir / "run_manifest.json").write_text(json.dumps({
    "run_id": run_id,
    "exp_id": "EXP-MOCK-001",
    "workload_type": "verification-test",
    "requested_by": "antigravity-verifier"
}))

(mock_dir / "status.json").write_text(json.dumps({
    "instance_id": "vps-test-node-1",
    "status": "idle"
}))

(mock_dir / "run_summary.json").write_text(json.dumps({
    "run_id": run_id,
    "status": "completed",
    "duration_s": 42,
    "exit_code": 0,
    "provenance": {
        "summary_generated_at": "2026-04-11T21:05:00Z"
    }
}))

(mock_dir / "stdout.log").write_text("line 1\nline 2\nline 3\n" + "\n".join([f"log line {i}" for i in range(100)]))
(mock_dir / "stderr.log").write_text("No errors found in this mock run.")

print(f"Mock run directory created at {mock_dir}")
