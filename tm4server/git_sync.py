from __future__ import annotations

import subprocess
from datetime import datetime
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
    try:
        rel_path = str(file_path.relative_to(repo_path))
        result = _run_git(repo_path, ["status", "--porcelain", "--", rel_path], timeout=10)
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def sync_report_to_git(
    repo_path: Path,
    file_paths: list[Path],
    commit_msg: Optional[str] = None,
    auto_push: bool = False,
) -> bool:
    """
    Stages and commits a set of files to the repository.
    Optionally pushes to the configured remote.
    """
    if not repo_path.exists():
        return False

    # 1. Filter only files that are actually inside the repo and exist
    target_files = []
    for fp in file_paths:
        try:
            if fp.exists() and fp.resolve().is_relative_to(repo_path.resolve()):
                target_files.append(fp)
        except (ValueError, OSError):
            continue

    if not target_files:
        return False

    # 2. Check if any target file has changes
    changed = False
    for fp in target_files:
        if _has_changes(repo_path, fp):
            changed = True
            break

    if not changed:
        return True  # No changes to sync, report success

    # 3. Stage files
    rel_paths = [str(fp.absolute().relative_to(repo_path.absolute())) for fp in target_files]
    res_add = _run_git(repo_path, ["add", "--", *rel_paths])
    if res_add.returncode != 0:
        return False

    # 4. Commit
    msg = commit_msg or f"Automated artifact sync: {datetime.now().isoformat()}"
    res_commit = _run_git(repo_path, ["commit", "-m", msg])
    if res_commit.returncode != 0:
        return False

    # 5. Push (optional)
    if auto_push:
        res_push = _run_git(repo_path, ["push"])
        return res_push.returncode == 0

    return True
