from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def _run_git(
    repo_path: Path,
    args: list[str],
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _has_changes(repo_path: Path, file_path: Path) -> bool:
    rel_path = str(file_path.relative_to(repo_path))
    result = _run_git(repo_path, ["status", "--porcelain", "--", rel_path], timeout=10)
    return result.returncode == 0 and bool(result.stdout.strip())


def sync_report_to_git(
    repo_path: Path,
    report_path: Path,
    exp_id: str,
    branch: Optional[str] = None,
) -> dict[str, object]:
    """
    Best-effort Git sync for a generated experiment report.

    Safety properties:
    - never raises
    - only stages the target report file
    - skips commit if file has no changes
    - push is attempted only after a successful commit
    - all failures are returned as structured status
    """
    try:
        repo_path = repo_path.resolve()
        report_path = report_path.resolve()

        if not repo_path.exists() or not repo_path.is_dir():
            return {
                "ok": False,
                "stage": "precheck",
                "message": f"Repository path does not exist: {repo_path}",
            }

        if not report_path.exists() or not report_path.is_file():
            return {
                "ok": False,
                "stage": "precheck",
                "message": f"Report path does not exist: {report_path}",
            }

        try:
            report_path.relative_to(repo_path)
        except ValueError:
            return {
                "ok": False,
                "stage": "precheck",
                "message": f"Report path is not inside repository: {report_path}",
            }

        git_dir_check = _run_git(repo_path, ["rev-parse", "--is-inside-work-tree"], timeout=10)
        if git_dir_check.returncode != 0 or git_dir_check.stdout.strip() != "true":
            return {
                "ok": False,
                "stage": "precheck",
                "message": f"Not a Git repository: {repo_path}",
                "stderr": git_dir_check.stderr.strip(),
            }

        if not _has_changes(repo_path, report_path):
            return {
                "ok": True,
                "stage": "noop",
                "message": "No report changes to commit",
            }

        rel_report = str(report_path.relative_to(repo_path))

        add_result = _run_git(repo_path, ["add", "--", rel_report], timeout=15)
        if add_result.returncode != 0:
            return {
                "ok": False,
                "stage": "add",
                "message": "git add failed",
                "stderr": add_result.stderr.strip(),
            }

        commit_message = f"Add experiment report {exp_id}"
        commit_result = _run_git(repo_path, ["commit", "-m", commit_message], timeout=20)

        if commit_result.returncode != 0:
            combined = f"{commit_result.stdout}\n{commit_result.stderr}".strip()
            if "nothing to commit" in combined.lower():
                return {
                    "ok": True,
                    "stage": "noop",
                    "message": "Nothing to commit after staging",
                }
            return {
                "ok": False,
                "stage": "commit",
                "message": "git commit failed",
                "stderr": commit_result.stderr.strip(),
                "stdout": commit_result.stdout.strip(),
            }

        push_args = ["push"]
        if branch:
            push_args.extend(["origin", branch])

        push_result = _run_git(repo_path, push_args, timeout=45)
        if push_result.returncode != 0:
            return {
                "ok": False,
                "stage": "push",
                "message": "git push failed",
                "stderr": push_result.stderr.strip(),
                "stdout": push_result.stdout.strip(),
            }

        return {
            "ok": True,
            "stage": "push",
            "message": "Report committed and pushed",
            "commit_message": commit_message,
            "report_path": str(report_path),
        }

    except Exception as exc:
        return {
            "ok": False,
            "stage": "exception",
            "message": f"Unexpected git sync error: {exc}",
        }
