from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tm4server.experiment_report import ExperimentReportGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate experiment report from run artifacts")
    parser.add_argument("path", help="Path to run directory, run_summary.json, or a parent directory of multiple runs")
    parser.add_argument("--docs-root", help="Directory where reports will be saved", default="docs/experiments")
    parser.add_argument("--deployment-path", help="VPS deployment path", default=os.environ.get("TM4SERVER_REPO_PATH", "/opt/tm4server"))
    parser.add_argument("--tm4-core-path", help="TM4 core path", default=os.environ.get("TM4_CORE_PATH", "/opt/tm4-core"))
    parser.add_argument("--runtime-root", help="Runtime root", default=os.environ.get("TM4_RUNTIME_ROOT", "/var/lib/tm4"))

    args = parser.parse_args()

    # Determine targets
    input_path = Path(args.path)
    summaries = []

    if input_path.is_file():
        # Case 1: Direct file link
        if input_path.name == "run_summary.json":
            summaries.append(input_path)
        else:
            print(f"Error: {input_path} is not run_summary.json")
            sys.exit(1)
    elif input_path.is_dir():
        # Case 2: Run directory OR Parent directory
        if (input_path / "run_summary.json").exists():
            # It's a single run directory
            summaries.append(input_path / "run_summary.json")
        else:
            # It's likely a parent directory; look for run subdirectories
            print(f"Scanning parent directory for runs: {input_path}")
            # Step 1a hardening: Sort iteration for deterministic behavior
            for run_dir in sorted(input_path.iterdir()):
                if run_dir.is_dir():
                    summary_file = run_dir / "run_summary.json"
                    if summary_file.exists():
                        summaries.append(summary_file)
    
    if not summaries:
        print(f"No run_summary.json files found at {input_path}")
        sys.exit(0)

    print(f"Planning to generate {len(summaries)} reports...")
    
    success_count = 0
    fail_count = 0

    for summary_path in summaries:
        try:
            generator = ExperimentReportGenerator(
                summary_path=summary_path,
                docs_root=Path(args.docs_root),
                deployment_path=args.deployment_path,
                tm4_core_path=args.tm4_core_path,
                runtime_root=args.runtime_root,
            )
            out_file = generator.write()
            print(f"Generated report: {out_file}")
            success_count += 1
        except Exception as exc:
            # Phase 2B.1: Fail-soft in bulk mode
            print(f"[!] Warning: Failed to generate report for {summary_path.parent.name}: {exc}")
            fail_count += 1
    
    print(f"\nFinal Status: {success_count} success, {fail_count} failed.")


if __name__ == "__main__":
    main()
