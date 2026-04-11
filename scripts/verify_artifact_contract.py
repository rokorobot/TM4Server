#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

ALLOWED_STATUSES = {"queued", "running", "success", "failed", "interrupted", "unknown"}
TERMINAL_STATUSES = {"success", "failed", "interrupted"}


def validate_iso8601(ts: str) -> bool:
    if not isinstance(ts, str) or not ts.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def check_artifact(path: Path, required_fields: list[str], name: str):
    if not path.exists():
        print(f"[!] {name} is missing")
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            print(f"[X] {name} is NOT A JSON OBJECT")
            return None

        # Check schema version
        if data.get("schema_version") != "v1":
            print(f"[X] {name} has invalid or missing schema_version (expected v1)")

        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"[X] {name} is missing required fields: {missing}")
            return None

        # Check timestamps
        for k, v in data.items():
            if k.endswith("_at") and v:
                if not validate_iso8601(v):
                    print(f"[X] {name} has invalid timestamp format for '{k}': {v}")

        return data
    except Exception as e:
        print(f"[X] {name} could not be parsed: {e}")
        return None


def validate_run(run_dir_str: str):
    run_dir = Path(run_dir_str).resolve()
    print(f"--- Validating Run: {run_dir.name} ---")

    if not run_dir.exists():
        print(f"[X] Directory {run_dir} does not exist.")
        return False

    # 1. run_manifest.json (Required)
    man_req = ["schema_version", "run_id", "exp_id", "workload_type", "requested_by", "created_at"]
    man = check_artifact(run_dir / "run_manifest.json", man_req, "run_manifest.json")

    # 2. status.json (Required)
    sta_req = ["schema_version", "run_id", "status", "instance_id", "worker_pid", "started_at", "updated_at"]
    sta = check_artifact(run_dir / "status.json", sta_req, "status.json")

    # 3. run_summary.json (Required if terminal)
    sum_req = ["schema_version", "run_id", "status", "duration_s", "provenance"]
    summary = check_artifact(run_dir / "run_summary.json", sum_req, "run_summary.json")

    success = True
    if not man or not sta:
        success = False

    # Status Validation
    if sta:
        if sta["status"] not in ALLOWED_STATUSES:
            print(f"[X] status.json has invalid status: {sta['status']}")
            success = False

    if summary:
        if summary["status"] not in TERMINAL_STATUSES:
            print(f"[X] run_summary.json has NON-TERMINAL status: {summary['status']}")
            success = False
        
        prov = summary.get("provenance", {})
        if "summary_generated_at" not in prov:
            print("[X] run_summary.json is missing provenance.summary_generated_at")
            success = False
        elif not validate_iso8601(prov["summary_generated_at"]):
            print(f"[X] run_summary.json has invalid summary_generated_at: {prov['summary_generated_at']}")
            success = False

    # Consistency checks: run_id, exp_id, instance_id
    check_keys = [("run_id", True), ("exp_id", False), ("instance_id", False)]
    
    for key, required_everywhere in check_keys:
        values = []
        if man and man.get(key): values.append(("manifest", man.get(key)))
        if sta and sta.get(key): values.append(("status", sta.get(key)))
        if summary and summary.get(key): values.append(("summary", summary.get(key)))

        if not values:
            continue
            
        first_val = values[0][1]
        for src, val in values:
            if val != first_val:
                print(f"[X] Consistency drift detected for '{key}'! {src} has '{val}' vs manifest/first '{first_val}'")
                success = False

    if man and man.get("run_id") != run_dir.name:
        print(f"[!] Warning: Directory name '{run_dir.name}' does not match run_id '{man.get('run_id')}'")

    if (run_dir / "tm4_runtime_status.json").exists():
        print(f"[*] Info: Found auxiliary TM4 runtime status (tm4_runtime_status.json)")

    if success:
        print(f"--- [OK] {run_dir.name} is spec-v1 CONFORMANT ---")
    else:
        print(f"--- [FAIL] {run_dir.name} is NON-CONFORMANT ---")
    
    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_artifact_contract.py <run_dir>")
        sys.exit(1)
    
    if not validate_run(sys.argv[1]):
        sys.exit(1)
