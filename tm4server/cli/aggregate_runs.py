from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tm4server.aggregate_runs import RunAggregator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate TM4 run_summary.json files into a CSV ledger"
    )
    parser.add_argument(
        "runs_root",
        nargs="?",
        default=os.environ.get("TM4_RUNS_ROOT", "/var/lib/tm4/runs"),
        help="Root directory containing run subdirectories",
    )
    parser.add_argument(
        "--output-csv",
        default="docs/experiments/results.csv",
        help="Path to output CSV ledger",
    )
    parser.add_argument(
        "--output-json",
        default="docs/experiments/results.json",
        help="Optional path to output JSON ledger",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON aggregate output",
    )

    args = parser.parse_args()

    output_json = None if args.no_json else Path(args.output_json)

    try:
        result = RunAggregator(
            runs_root=Path(args.runs_root),
            output_csv=Path(args.output_csv),
            output_json=output_json,
        ).aggregate()
    except Exception as exc:
        print(f"ERROR: failed to aggregate runs: {exc}", file=sys.stderr)
        return 1

    print(f"CSV: {result.output_csv}")
    if result.output_json:
        print(f"JSON: {result.output_json}")
    print(f"Rows written: {result.rows_written}")
    print(f"Failed files: {result.failed_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
