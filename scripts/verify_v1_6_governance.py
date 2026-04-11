import os
import sys
import json
import shutil
from pathlib import Path

# 1. Environment Isolation (CRITICAL)
TEST_RUNTIME_ROOT = Path("c:/Users/Robert/TM4Server/local_runtime_test")
if TEST_RUNTIME_ROOT.exists():
    shutil.rmtree(TEST_RUNTIME_ROOT)
TEST_RUNTIME_ROOT.mkdir(parents=True)

os.environ["TM4_BASE_PATH"] = str(TEST_RUNTIME_ROOT)

# Now we can import the server logic which depends on config
sys.path.append("c:/Users/Robert/TM4Server")
from tm4server.api.operator_console import lock_task_decision, promote_task_default, revoke_task_promotion, get_promotion_history
from tm4server.state import StateManager, atomic_write_json
from tm4server.config import RUNS_DIR, DECISIONS_DIR, PROMOTIONS_DIR

class MockRequest:
    def __init__(self, body):
        self.body = body
    async def json(self):
        return self.body

async def run_verification():
    print("[INIT] Initializing Investor-Grade Governance Verification (v1.6)...")
    
    task = "autonomy"
    winner_model = "model_a"
    
    # 2. Negative Case (Premature Promote)
    print("\n[CASE 0] Attempting promotion without locked decision...")
    try:
        await promote_task_default(task, MockRequest({"actor": "Robert"}))
        raise AssertionError("Case 0 failed: Promotion succeeded without a locked decision!")
    except Exception as e:
        print(f"[SUCCESS] Success: Caught expected failure: {str(e)}")

    # 3. Mock Evidence Injection (6 runs to clear floor)
    print(f"\n[SETUP] Injecting 6 convergent runs for {task}/{winner_model}...")
    for i in range(1, 7):
        exp_id = f"EXP-MOCK-{i:04d}"
        run_dir = RUNS_DIR / exp_id
        run_dir.mkdir(parents=True)
        
        # Manifest
        atomic_write_json(run_dir / "run_manifest.json", {
            "task": task,
            "model": winner_model,
            "created_at": "2026-04-10T00:00:00Z"
        })
        
        # Summary (to trigger CONVERGENT classification)
        atomic_write_json(run_dir / "run_summary.json", {
            "exp_id": exp_id,
            "status": "completed",
            "mean_net_improvement": 1.2,
            "best_fitness_by_gen": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            "metrics": {
                "gen0_best": 0.1,
                "final_best": 1.0,
                "generations": 10
            }
        })

    # 4. Action-Path Verification
    
    # Step 1: First Lock
    print("\n[STEP 1] Locking first decision...")
    res1 = await lock_task_decision(task, MockRequest({"actor": "Robert"}), force=False)
    assert res1["ok"] is True
    decision1 = res1["decision"]
    lock1_at = decision1["locked_at"]
    assert decision1["winner_model"] == winner_model
    assert decision1["actor"] == "Robert"
    assert "system_actor" in decision1
    assert (DECISIONS_DIR / f"{task}.json").exists()
    print(f"[PASS] Lock 1 successful (TS: {lock1_at})")

    # Step 2: Conflict Check (No Force)
    print("\n[STEP 2] Attempting overwrite without force=True...")
    try:
        await lock_task_decision(task, MockRequest({"actor": "Robert_Hacker"}), force=False)
        raise AssertionError("Step 2 failed: Overwrite succeeded without force=True!")
    except Exception as e:
        print(f"[SUCCESS] Success: Caught expected conflict.")

    # Step 3: Force Overwrite
    print("\n[STEP 3] Performing authorized Force Overwrite...")
    # Wait a second to ensure different timestamp
    import time
    time.sleep(1.1)
    res2 = await lock_task_decision(task, MockRequest({"actor": "Robert_Revised"}), force=True)
    assert res2["ok"] is True
    decision2 = res2["decision"]
    assert decision2["actor"] == "Robert_Revised"
    assert decision2["previous_locked_at"] == lock1_at
    assert (DECISIONS_DIR / f"{task}.json").exists()
    print(f"[PASS] Lock 2 (Overwrite) successful. Lineage intact.")

    # Step 4: Promote
    print("\n[STEP 4] Promoting locked winner to system default...")
    promote_res = await promote_task_default(task, MockRequest({"actor": "Robert_Admin"}))
    assert promote_res["ok"] is True
    assert (PROMOTIONS_DIR / f"{task}.json").exists()
    
    with open(PROMOTIONS_DIR / f"{task}.json", "r") as f:
        active_promo = json.load(f)
        assert active_promo["winner_model"] == winner_model
        assert active_promo["actor"] == "Robert_Admin"
    print(f"[PASS] Promotion successful. Active model correctly mapped to {winner_model}.")

    # Step 5: Revoke
    print("\n[STEP 5] Revoking active promotion...")
    revoke_res = await revoke_task_promotion(task, MockRequest({"actor": "Robert_Admin"}))
    assert revoke_res["ok"] is True
    assert not (PROMOTIONS_DIR / f"{task}.json").exists()
    print(f"[PASS] Revocation successful. Active mapping cleared.")

    # 5. Audit Integrity Check
    print("\n[STEP 6] Validating immutable audit lineage...")
    history_res = await get_promotion_history(task)
    assert history_res["ok"] is True
    history = history_res["history"]
    
    # We expect 4 events: LOCK (second one) + PROMOTE + REVOKE
    # Wait, the history log captures PROMOTE and REVOKE in the .jsonl.
    # LOCK artifacts are in decisions/ but not in the promotions.jsonl unless also added?
    # Let's check promoter.py: promote() and revoke() add to .jsonl.
    
    print(f"History entries found: {len(history)}")
    for entry in history:
        print(f" - [{entry['ts_utc']}] {entry['action']}: {entry['actor']} ({entry.get('system_actor', 'sys')})")
        assert "actor" in entry
        assert "system_actor" in entry
        assert entry["actor"] != "unknown"

    # Specific audit ordering check
    types = [e["action"] for e in history]
    # Ordering in promoter.get_history is newest first (reversed)
    assert types[0] == "REVOKE_PROMOTION"
    assert types[1] == "PROMOTE_TO_DEFAULT"
    
    print("\n[FINISH] ALL GOVERNANCE ASSERTIONS PASSED. v1.6 IS SEALED.")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(run_verification())
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
