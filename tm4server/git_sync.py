from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _run_git(
    repo_path: Path,
    args: List[str],
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
        repo_root = repo_path.resolve()
        candidate = file_path.resolve()
        rel_path = candidate.relative_to(repo_root)
        result = _run_git(repo_root, ["status", "--porcelain", "--", str(rel_path)], timeout=10)
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def sync_artifacts_to_git(
    repo_path: Path,
    file_paths: List[Path],
    commit_msg: Optional[str] = None,
    auto_push: bool = False,
) -> Dict[str, Any]:
    """
    Stages and commits a set of files to the repository.
    Returns a detailed status dictionary.
    """
    repo_root = repo_path.resolve()
    if not repo_root.exists():
        return {"ok": False, "stage": "precheck", "message": f"Repo not found: {repo_root}"}

    # 1. Filter only files that are actually inside the repo and exist (using resolve for symlink safety)
    target_files: List[Path] = []
    for fp in file_paths:
        try:
            candidate = fp.resolve()
            if candidate.exists() and candidate.is_relative_to(repo_root):
                target_files.append(candidate)
        except (ValueError, OSError):
            continue

    if not target_files:
        return {"ok": False, "stage": "precheck", "message": "No valid artifacts within repo tree to sync."}

    # 2. Check if any target file has changes
    changed = False
    for fp in target_files:
        if _has_changes(repo_root, fp):
            changed = True
            break

    if not changed:
        return {"ok": True, "stage": "check", "changed": False, "message": "No changes detected in artifacts."}

    # 3. Stage files
    rel_paths = [str(fp.relative_to(repo_root)) for fp in target_files]
    res_add = _run_git(repo_root, ["add", "--", *rel_paths])
    if res_add.returncode != 0:
        return {
            "ok": False,
            "stage": "add",
            "message": "Git add failed",
            "stderr": res_add.stderr,
        }

    # 4. Commit
    msg = commit_msg or f"Automated artifact sync: {datetime.now().isoformat()}"
    res_commit = _run_git(repo_root, ["commit", "-m", msg])
    if res_commit.returncode != 0:
        return {
            "ok": False,
            "stage": "commit",
            "message": f"Git commit failed for {len(target_files)} files",
            "stderr": res_commit.stderr,
        }

    # 5. Push (optional)
    if auto_push:
        res_push = _run_git(repo_root, ["push"])
        if res_push.returncode != 0:
            return {
                "ok": False,
                "stage": "push",
                "message": "Git push failed",
                "stderr": res_push.stderr,
            }
        return {"ok": True, "stage": "push", "changed": True, "message": f"Pushed {len(target_files)} artifacts"}

    return {"ok": True, "stage": "commit", "changed": True, "message": f"Committed {len(target_files)} local artifacts (push disabled)"}
