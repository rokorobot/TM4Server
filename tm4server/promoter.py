from __future__ import annotations
from pathlib import Path
from .config import PROMOTIONS_DIR
from .state import atomic_write_json, append_jsonl, utc_now_iso, get_system_actor, read_json_safe

class PromotionManager:
    def __init__(self, promotions_dir: Path = PROMOTIONS_DIR):
        self.root = promotions_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def get_promotion_path(self, task: str) -> Path:
        return self.root / f"{task}.json"

    def get_history_path(self, task: str) -> Path:
        return self.root / f"{task}.jsonl"

    def get_active_promotion(self, task: str) -> dict | None:
        """Returns the current active promotion for a task."""
        path = self.get_promotion_path(task)
        if not path.exists():
            return None
        return read_json_safe(path, {})

    def promote(self, task: str, decision: dict, actor: str) -> dict:
        """
        Promotes a winner to active default.
        Records the event in the audit trail.
        """
        active_path = self.get_promotion_path(task)
        history_path = self.get_history_path(task)
        
        prior = self.get_active_promotion(task)
        prior_model = prior.get("winner_model") if prior else None
        
        promotion = {
            "task": task,
            "winner_model": decision.get("winner_model"),
            "promoted_at": utc_now_iso(),
            "decision_artifact": decision.get("decision_path"),
            "actor": actor,
            "system_actor": get_system_actor(),
            "decision_version": decision.get("decision_version", "v1")
        }
        
        atomic_write_json(active_path, promotion)
        
        # Append to audit history
        event = {
            "ts_utc": utc_now_iso(),
            "task": task,
            "action": "PROMOTE_TO_DEFAULT",
            "actor": actor,
            "system_actor": get_system_actor(),
            "winner_model": promotion["winner_model"],
            "prior_model": prior_model,
            "decision_path": promotion["decision_artifact"]
        }
        append_jsonl(history_path, event)
        
        return promotion

    def revoke(self, task: str, actor: str) -> dict:
        """
        Revokes an active promotion.
        """
        active_path = self.get_promotion_path(task)
        history_path = self.get_history_path(task)
        
        prior = self.get_active_promotion(task)
        prior_model = prior.get("winner_model") if prior else None
        
        if active_path.exists():
            active_path.unlink()
            
        event = {
            "ts_utc": utc_now_iso(),
            "task": task,
            "action": "REVOKE_PROMOTION",
            "actor": actor,
            "system_actor": get_system_actor(),
            "prior_model": prior_model,
            "reason": "operator_revocation"
        }
        append_jsonl(history_path, event)
        
        return {"ok": True, "task": task, "action": "revoked"}

    def get_history(self, task: str) -> list[dict]:
        """Returns the promotion history for a task."""
        path = self.get_history_path(task)
        if not path.exists():
            return []
        
        history = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    import json
                    history.append(json.loads(line))
        return list(reversed(history))
