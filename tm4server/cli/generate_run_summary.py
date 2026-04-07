from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tm4server.run_summary import RunSummaryExtractor


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate run_summary.json for a TM4 run directory")
    parser.add_argument("run_dir", help="Path to run artifact directory")
    parser.add_argument("--tm4-core-repo", default=None, help="Path to TM4 core repo")
    parser.add_argument("--tm4server-repo", default=None, help="Path to TM4Server repo")
    parser.add_argument("--output", default="run_summary.json", help="Output filename inside run_dir")

    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"ERROR: run_dir does not exist or is not a directory: {run_dir}", file=sys.stderr)
        return 2

    # Use default relative paths if not provided
    tm4_core_repo = Path(args.tm4_core_repo) if args.tm4_core_repo else Path("C:/Users/Robert/TM4")
    tm4server_repo = Path(args.tm4server_repo) if args.tm4server_repo else Path(__file__).parent.parent.parent

    extractor = RunSummaryExtractor(
        run_dir=run_dir,
        tm4_core_repo=tm4_core_repo,
        tm4server_repo=tm4server_repo,
    )
    out_path = extractor.write(filename=args.output)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
