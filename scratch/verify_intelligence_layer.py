import os
import json
import shutil
import re
from pathlib import Path
from tm4server.execution.record import RunRecordBuilder, tail_log
from tm4server.execution.ledger import ExperimentLedger
from tm4server.execution.artifacts import write_manifest, write_status, write_summary, utc_now_z

def test_log_tailing():
    print("\n--- Testing Log Tailing (Dual-Constraint) ---")
    log_path = Path("test_tail.log")
    lines = [f"Line {i:03d}: " + "X" * 200 + "\n" for i in range(100)]
    log_path.write_text("".join(lines), encoding="utf-8")
    
    res = tail_log(log_path, max_lines=80, max_bytes=16384)
    print(f"Result (80 lines/16KB): Lines={res['lines']}, Bytes={res['bytes']}, Truncated={res['truncated_by']}")
    assert res["truncated_by"] == "bytes"
    log_path.unlink()

def test_intelligence_classification():
    print("\n--- Testing Failure Intelligence (Golden Fixtures) ---")
    mock_root = Path("mock_intel_fixtures")
    if mock_root.exists(): shutil.rmtree(mock_root)
    mock_root.mkdir()
    
    builder = RunRecordBuilder(mock_root)
    now = utc_now_z()

    # Case 1: OOM (Infra Error via Exit Code)
    run_dir = mock_root / "RUN-OOM"
    run_dir.mkdir()
    write_manifest(run_dir, {
        "run_id": "RUN-OOM", 
        "exp_id": "EXP-1", 
        "created_at": now,
        "workload_type": "fixture",
        "requested_by": "tester"
    })
    write_status(run_dir, {"run_id": "RUN-OOM", "status": "failed", "started_at": now})
    write_summary(run_dir, {"run_id": "RUN-OOM", "status": "failed", "started_at": now, "completed_at": now, "exit_code": 137})
    
    rec = builder.build_record("RUN-OOM", strict=True)
    intel = rec["intelligence"]
    print(f"OOM Test: Class={intel['failure_class']}, Source={intel['source']}, Retry={intel['retry_recommended']}")
    assert intel["failure_class"] == "infra_error"
    assert intel["source"] == "derived_v1_exitcode"
    assert intel["retry_recommended"] is True

    # Case 2: Traceback (Execution Error via Log Pattern)
    run_dir = mock_root / "RUN-TRACEBACK"
    run_dir.mkdir()
    write_manifest(run_dir, {
        "run_id": "RUN-TRACEBACK", 
        "exp_id": "EXP-1", 
        "created_at": now,
        "workload_type": "fixture",
        "requested_by": "tester"
    })
    write_status(run_dir, {"run_id": "RUN-TRACEBACK", "status": "failed", "started_at": now})
    write_summary(run_dir, {"run_id": "RUN-TRACEBACK", "status": "failed", "started_at": now, "completed_at": now, "exit_code": 1})
    (run_dir / "stderr.log").write_text("Traceback (most recent call last):\n  File 'main.py', line 10, in <module>\nValueError: Test", encoding="utf-8")
    
    rec = builder.build_record("RUN-TRACEBACK", strict=True)
    intel = rec["intelligence"]
    print(f"Traceback Test: Class={intel['failure_class']}, Source={intel['source']}, Retry={intel['retry_recommended']}")
    assert intel["failure_class"] == "execution_error"
    assert intel["source"] == "derived_v1_stderr"
    assert intel["retry_recommended"] is False

    # Case 3: Contract Failure (Missing Summary)
    run_dir = mock_root / "RUN-CONTRACT-MISSING"
    run_dir.mkdir()
    write_manifest(run_dir, {
        "run_id": "RUN-CONTRACT-MISSING", 
        "exp_id": "EXP-1", 
        "created_at": now,
        "workload_type": "fixture",
        "requested_by": "tester"
    })
    # Run is terminal (failed) but no summary file exists
    write_status(run_dir, {"run_id": "RUN-CONTRACT-MISSING", "status": "failed", "started_at": now})
    
    rec = builder.build_record("RUN-CONTRACT-MISSING", strict=False) # Use compat to check if it flags
    intel = rec["intelligence"]
    print(f"Contract Test: Class={intel['failure_class']}, Source={intel['source']}, Reason={intel['failure_reason']}")
    assert intel["failure_class"] == "contract_error"
    assert intel["source"] == "derived_v1_contract"

    # Case 4: Interrupted (Status=interrupted)
    run_dir = mock_root / "RUN-INTERRUPTED"
    run_dir.mkdir()
    write_manifest(run_dir, {
        "run_id": "RUN-INTERRUPTED", 
        "exp_id": "EXP-1", 
        "created_at": now,
        "workload_type": "fixture",
        "requested_by": "tester"
    })
    write_status(run_dir, {"run_id": "RUN-INTERRUPTED", "status": "interrupted", "started_at": now})
    
    rec = builder.build_record("RUN-INTERRUPTED", strict=True)
    intel = rec["intelligence"]
    print(f"Interrupted Test: Class={intel['failure_class']}, Source={intel['source']}, Retry={intel['retry_recommended']}")
    assert intel["failure_class"] == "interrupted"
    assert intel["retry_recommended"] is True

    shutil.rmtree(mock_root)

def test_split_brain():
    print("\n--- Testing Split-Brain Detection (Identity Consensus) ---")
    mock_root = Path("mock_intel_split")
    if mock_root.exists(): shutil.rmtree(mock_root)
    mock_root.mkdir()
    run_dir = mock_root / "RUN-SPLIT"
    run_dir.mkdir()
    now = utc_now_z()
    write_manifest(run_dir, {
        "run_id": "RUN-A", 
        "exp_id": "EXP-A", 
        "created_at": now,
        "workload_type": "fixture",
        "requested_by": "tester"
    })
    write_status(run_dir, {"run_id": "RUN-B", "status": "running", "started_at": now})
    builder = RunRecordBuilder(mock_root)
    assert builder.build_record("RUN-SPLIT", strict=True) is None
    rec = builder.build_record("RUN-SPLIT", strict=False)
    assert "run_id mismatch" in rec["governance"]["validation_errors"][0]
    shutil.rmtree(mock_root)

if __name__ == "__main__":
    try:
        test_log_tailing()
        test_intelligence_classification()
        test_split_brain()
        print("\n[SUCCESS] Phase 2D.2 Intelligence Verification Complete.")
    except Exception as e:
        print(f"\n[FAILURE] Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
