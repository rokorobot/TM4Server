from __future__ import annotations
import argparse
from pathlib import Path

from .config import QUEUED_DIR
from .utils import ensure_dir, write_json, utc_now_iso


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-id", required=True)
    parser.add_argument("--task", default="demo_task")
    parser.add_argument("--model", default="demo-model")
    args = parser.parse_args()

    ensure_dir(QUEUED_DIR)

    manifest = {
        "experiment_id": args.exp_id,
        "task": args.task,
        "model": args.model,
        "submitted_at": utc_now_iso(),
        "code_version": "bootstrap-v1",
    }

    out = QUEUED_DIR / f"{args.exp_id}.json"
    write_json(out, manifest)
    print(f"Queued: {out}")


if __name__ == "__main__":
    main()
