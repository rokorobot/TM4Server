import sys
from pathlib import Path
import json
import shutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.state import StateManager

def verify_v1_1_logic():
    print("--- Verifying Runs Explorer v1.1 Logic ---")
    
    test_runs = Path("test_runs_v1_1")
    if test_runs.exists():
        shutil.rmtree(test_runs)
    test_runs.mkdir()
    
    state = StateManager(runtime_root=Path("."))
    
    # 1. Mock a Queued Run
    q_id = "EXP-TEST-0001"
    q_dir = test_runs / q_id
    q_dir.mkdir()
    with open(q_dir / "run_manifest.json", "w") as f:
        json.dump({"exp_id": q_id, "created_at": "2026-04-10T00:00:00Z"}, f)
    with open(q_dir / "runtime_state.json", "w") as f:
        json.dump({"status": "queued"}, f)
        
    # 2. Mock a Running Run
    r_id = "EXP-TEST-0002"
    r_dir = test_runs / r_id
    r_dir.mkdir()
    with open(r_dir / "run_manifest.json", "w") as f:
        json.dump({"exp_id": r_id, "created_at": "2026-04-10T01:00:00Z"}, f)
    with open(r_dir / "runtime_state.json", "w") as f:
        json.dump({"status": "running", "worker_pid": 1234}, f)
        
    # 3. Mock a Completed Run
    c_id = "EXP-TEST-0003"
    c_dir = test_runs / c_id
    c_dir.mkdir()
    with open(c_dir / "run_manifest.json", "w") as f:
        json.dump({"exp_id": c_id, "created_at": "2026-04-10T02:00:00Z"}, f)
    with open(c_dir / "runtime_state.json", "w") as f:
        json.dump({"status": "completed"}, f)
    with open(c_dir / "run_summary.json", "w") as f:
        json.dump({"status": "completed", "ts_utc": "2026-04-10T02:30:00Z"}, f)
        
    # 4. Mock a Failed Run
    f_id = "EXP-TEST-0004"
    f_dir = test_runs / f_id
    f_dir.mkdir()
    with open(f_dir / "run_manifest.json", "w") as f:
        json.dump({"exp_id": f_id, "created_at": "2026-04-10T03:00:00Z"}, f)
    with open(f_dir / "runtime_state.json", "w") as f:
        json.dump({"status": "failed"}, f)
    with open(f_dir / "run_summary.json", "w") as f:
        json.dump({"status": "failed", "error": "test failure"}, f)

    # 5. List Runs
    runs = state.list_runs(test_runs)
    print(f"Found {len(runs)} runs.")
    
    statuses = {r['exp_id']: r['status'] for r in runs}
    print(f"Statuses: {statuses}")
    
    assert statuses[q_id] == "queued"
    assert statuses[r_id] == "running"
    assert statuses[c_id] == "completed"
    assert statuses[f_id] == "failed"
    print("Logic: Status precedence verified.")
    
    # 6. Detail Fetch
    detail = state.get_run_detail(test_runs, c_id)
    assert detail['exp_id'] == c_id
    assert detail['manifest']['exp_id'] == c_id
    assert detail['summary']['status'] == "completed"
    print("Logic: Detail inspection verified.")
    
    # Clean up
    shutil.rmtree(test_runs)
    print("--- Verification Successful ---")

if __name__ == "__main__":
    verify_v1_1_logic()
