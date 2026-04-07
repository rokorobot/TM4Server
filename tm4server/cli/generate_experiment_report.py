from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tm4server.experiment_report import ExperimentReportGenerator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a markdown experiment report from run_summary.json"
    )
    parser.add_argument("summary_path", help="Path to run_summary.json")
    parser.add_argument(
        "--docs-root",
        default="docs/experiments",
        help="Output directory for markdown experiment reports",
    )
    parser.add_argument(
        "--deployment-path",
        default=None,
        help="Canonical TM4Server deployment path",
    )
    parser.add_argument(
        "--tm4-core-path",
        default=None,
        help="Canonical TM4 core deployment path",
    )
    parser.add_argument(
        "--runtime-root",
        default=None,
        help="Canonical runtime root",
    )

    args = parser.parse_args()

    summary_path = Path(args.summary_path)
    if not summary_path.exists() or not summary_path.is_file():
        print(f"ERROR: summary file not found: {summary_path}", file=sys.stderr)
        return 2

    deployment_path = (
        args.deployment_path
        or os.environ.get("TM4SERVER_REPO_PATH")
        or "/opt/tm4server"
    )
    tm4_core_path = (
        args.tm4_core_path
        or os.environ.get("TM4_CORE_PATH")
        or "/opt/tm4-core"
    )
    runtime_root = (
        args.runtime_root
        or os.environ.get("TM4_RUNTIME_ROOT")
        or "/var/lib/tm4"
    )

    try:
        generator = ExperimentReportGenerator(
            summary_path=summary_path,
            docs_root=Path(args.docs_root),
            deployment_path=deployment_path,
            tm4_core_path=tm4_core_path,
            runtime_root=runtime_root,
        )
        out_path = generator.write()
    except Exception as exc:
        print(f"ERROR: failed to generate experiment report: {exc}", file=sys.stderr)
        return 1

    print(str(out_path).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
