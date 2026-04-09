#!/usr/bin/env python3
"""
TM4 Server Inventory Exporter

Collects a production-facing snapshot of TM4 deployment state from the server itself.

Outputs:
- JSON inventory:  /var/lib/tm4/inventory/server_inventory_<timestamp>.json
- Markdown report: /var/lib/tm4/inventory/server_inventory_<timestamp>.md

Default inspected paths:
- /opt/tm4server
- /opt/tm4-core
- /var/lib/tm4
- /var/log/tm4
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TM4SERVER = Path("/opt/tm4server")
DEFAULT_TM4CORE = Path("/opt/tm4-core")
DEFAULT_RUNTIME = Path("/var/lib/tm4")
DEFAULT_LOGS = Path("/var/log/tm4")
DEFAULT_OUTPUT = DEFAULT_RUNTIME / "inventory"

KEY_FILES = [
    "server/dashboard.py",
    "server/api/operator_console.py",
    "server/api/__init__.py",
    "scripts/export_server_inventory.py",
    "docs/operator-console-v1.md",
    "docs/README.md",
    "docs/runtime-orchestration.md",
    "docs/ledger.md",
    "docs/aggregation.md",
]

SYSTEMD_CANDIDATES = [
    "tm4",
    "tm4server",
    "tm4-dashboard",
    "tm4-api",
    "nginx",
    "caddy",
    "uvicorn",
]


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(slots=True)
class GitInfo:
    path: str
    exists: bool
    is_repo: bool
    branch: str | None = None
    commit: str | None = None
    short_commit: str | None = None
    status_short: str | None = None
    remotes: str | None = None
    dirty: bool | None = None
    error: str | None = None


@dataclass(slots=True)
class FilePresence:
    relative_path: str
    exists: bool
    size_bytes: int | None = None
    modified_utc: str | None = None


@dataclass(slots=True)
class DirectoryTreeItem:
    path: str
    type: str
    size_bytes: int | None = None


@dataclass(slots=True)
class ServiceInfo:
    name: str
    available: bool
    active_state: str | None = None
    sub_state: str | None = None
    enabled: str | None = None
    error: str | None = None


@dataclass(slots=True)
class PortInfo:
    raw: str


@dataclass(slots=True)
class RunArtifactInfo:
    exp_id: str
    path: str
    modified_utc: str | None
    files: list[str] = field(default_factory=list)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def run_command(command: list[str], cwd: Path | None = None, timeout: int = 20) -> CommandResult:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
        )
    except Exception as exc:
        return CommandResult(
            command=command,
            returncode=999,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )


def which_or_none(name: str) -> str | None:
    return shutil.which(name)


def get_git_info(repo_path: Path) -> GitInfo:
    info = GitInfo(path=str(repo_path), exists=repo_path.exists(), is_repo=False)
    if not repo_path.exists():
        info.error = "Path does not exist."
        return info

    probe = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    if probe.returncode != 0 or probe.stdout.strip().lower() != "true":
        info.error = probe.stderr or "Not a git repository."
        return info

    info.is_repo = True
    branch = run_command(["git", "branch", "--show-current"], cwd=repo_path)
    commit = run_command(["git", "rev-parse", "HEAD"], cwd=repo_path)
    short_commit = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path)
    status = run_command(["git", "status", "--short"], cwd=repo_path)
    remotes = run_command(["git", "remote", "-v"], cwd=repo_path)

    info.branch = branch.stdout or None
    info.commit = commit.stdout or None
    info.short_commit = short_commit.stdout or None
    info.status_short = status.stdout or ""
    info.remotes = remotes.stdout or ""
    info.dirty = bool((status.stdout or "").strip())
    return info


def safe_stat(path: Path):
    try:
        return path.stat()
    except Exception:
        return None


def list_key_files(base_path: Path, relative_paths: list[str]) -> list[FilePresence]:
    result = []
    for rel in relative_paths:
        p = base_path / rel
        st = safe_stat(p)
        result.append(
            FilePresence(
                relative_path=rel,
                exists=p.exists(),
                size_bytes=st.st_size if st else None,
                modified_utc=isoformat_utc(st.st_mtime) if st else None,
            )
        )
    return result


def build_tree(root: Path, max_depth: int = 3, max_entries: int = 300) -> list[DirectoryTreeItem]:
    items = []
    if not root.exists():
        return items

    root_depth = len(root.parts)
    for path in sorted(root.rglob("*")):
        if len(items) >= max_entries:
            break
        depth = len(path.parts) - root_depth
        if depth > max_depth:
            continue
        try:
            st = path.stat()
            items.append(
                DirectoryTreeItem(
                    path=str(path),
                    type="dir" if path.is_dir() else "file",
                    size_bytes=None if path.is_dir() else st.st_size,
                )
            )
        except Exception:
            items.append(DirectoryTreeItem(path=str(path), type="unknown", size_bytes=None))
    return items


def get_systemd_services(names: list[str]) -> list[ServiceInfo]:
    if which_or_none("systemctl") is None:
        return [ServiceInfo(name=n, available=False, error="systemctl not available") for n in names]

    output = []
    for name in names:
        show = run_command(
            ["systemctl", "show", name, "--no-page", "--property=LoadState,ActiveState,SubState,UnitFileState"],
            timeout=15,
        )
        if show.returncode != 0:
            output.append(ServiceInfo(name=name, available=False, error=show.stderr or "Not found"))
            continue

        kv = {}
        for line in show.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k] = v

        load_state = kv.get("LoadState", "")
        output.append(
            ServiceInfo(
                name=name,
                available=load_state == "loaded",
                active_state=kv.get("ActiveState"),
                sub_state=kv.get("SubState"),
                enabled=kv.get("UnitFileState"),
                error=None if load_state == "loaded" else f"LoadState={load_state}",
            )
        )
    return output


def get_listening_ports() -> list[PortInfo]:
    commands = []
    if which_or_none("ss"):
        commands.append(["ss", "-ltnp"])
    if which_or_none("netstat"):
        commands.append(["netstat", "-ltnp"])

    for cmd in commands:
        res = run_command(cmd, timeout=15)
        if res.returncode == 0 and res.stdout:
            lines = [line for line in res.stdout.splitlines() if line.strip()]
            return [PortInfo(raw=line) for line in lines[:200]]
    return [PortInfo(raw="No port inventory available (ss/netstat missing or failed).")]


def get_ps_snapshot() -> str:
    if which_or_none("ps") is None:
        return "ps not available"
    res = run_command(["ps", "-eo", "pid,ppid,etime,%cpu,%mem,cmd", "--sort=-%cpu"], timeout=20)
    return res.stdout or res.stderr or "ps returned no output"


def find_latest_run_artifacts(runtime_root: Path, max_runs: int = 10) -> list[RunArtifactInfo]:
    runs_root = runtime_root / "runs"
    if not runs_root.exists():
        return []

    candidates = []
    for child in runs_root.iterdir():
        if child.is_dir():
            st = safe_stat(child)
            candidates.append((st.st_mtime if st else 0.0, child))

    candidates.sort(key=lambda x: x[0], reverse=True)
    output = []
    interesting = [
        "run_summary.json",
        "run_manifest.json",
        "report.md",
        "classification.json",
        "generation_meta.json",
    ]

    for _, run_dir in candidates[:max_runs]:
        files_present = [name for name in interesting if (run_dir / name).exists()]
        st = safe_stat(run_dir)
        output.append(
            RunArtifactInfo(
                exp_id=run_dir.name,
                path=str(run_dir),
                modified_utc=isoformat_utc(st.st_mtime) if st else None,
                files=files_present,
            )
        )
    return output


def get_python_info() -> dict[str, Any]:
    return {
        "executable": sys.executable,
        "version": sys.version.replace("\n", " "),
    }


def get_host_info() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["-"] * len(headers)]
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(x).replace("\n", "<br>") for x in row) + " |")
    return "\n".join(out)


def render_markdown(data: dict[str, Any]) -> str:
    repo_rows = []
    for key in ("tm4server", "tm4core"):
        repo = data["git"].get(key, {})
        repo_rows.append([
            key,
            repo.get("path", "-"),
            str(repo.get("is_repo", False)),
            repo.get("branch") or "-",
            repo.get("short_commit") or "-",
            str(repo.get("dirty")),
        ])

    key_file_rows = []
    for group_name, files in data["key_files"].items():
        for item in files:
            key_file_rows.append([
                group_name,
                item["relative_path"],
                str(item["exists"]),
                str(item.get("size_bytes") or "-"),
                item.get("modified_utc") or "-",
            ])

    service_rows = []
    for svc in data["services"]:
        service_rows.append([
            svc["name"],
            str(svc["available"]),
            svc.get("active_state") or "-",
            svc.get("sub_state") or "-",
            svc.get("enabled") or "-",
            svc.get("error") or "-",
        ])

    run_rows = []
    for run in data["latest_runs"]:
        run_rows.append([
            run["exp_id"],
            run["modified_utc"] or "-",
            ", ".join(run["files"]) if run["files"] else "-",
            run["path"],
        ])

    port_lines = "\n".join(f"- `{item['raw']}`" for item in data["ports"][:50])
    status_excerpt = "\n".join("    " + line for line in data["processes"].splitlines()[:40])

    return f"""# TM4 Server Inventory

Generated at: {data["generated_at"]}
Host: {data["host"]["hostname"]}

## Host
- Platform: `{data["host"]["platform"]}`
- Python: `{data["python"]["version"]}`
- Executable: `{data["python"]["executable"]}`

## Paths
- TM4Server: `{data["paths"]["tm4server"]}`
- TM4 Core: `{data["paths"]["tm4core"]}`
- Runtime: `{data["paths"]["runtime"]}`
- Logs: `{data["paths"]["logs"]}`

## Git Inventory
{markdown_table(["Repo", "Path", "Is Repo", "Branch", "Short Commit", "Dirty"], repo_rows)}

## Key Files
{markdown_table(["Group", "Relative Path", "Exists", "Size", "Modified UTC"], key_file_rows)}

## Services
{markdown_table(["Service", "Available", "Active", "Sub", "Enabled", "Error"], service_rows)}

## Latest Run Artifacts
{markdown_table(["exp_id", "Modified UTC", "Files", "Path"], run_rows)}

## Listening Ports
{port_lines or "- No listening ports captured."}

## Process Snapshot (top excerpt)
```text
{status_excerpt}
```

## Notes
- This report reflects **server deployment truth**, not local repository state.
- A checked-out commit does not guarantee the running process was restarted after deployment.
- Runtime artifacts in `/var/lib/tm4` may reflect older runs than the currently checked-out code.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export TM4 server inventory.")
    parser.add_argument("--tm4server", type=Path, default=DEFAULT_TM4SERVER)
    parser.add_argument("--tm4core", type=Path, default=DEFAULT_TM4CORE)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-tree-entries", type=int, default=300)
    parser.add_argument("--max-runs", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inventory = {
        "generated_at": now_utc().isoformat(),
        "host": get_host_info(),
        "python": get_python_info(),
        "paths": {
            "tm4server": str(args.tm4server),
            "tm4core": str(args.tm4core),
            "runtime": str(args.runtime),
            "logs": str(args.logs),
        },
        "git": {
            "tm4server": asdict(get_git_info(args.tm4server)),
            "tm4core": asdict(get_git_info(args.tm4core)),
        },
        "key_files": {
            "tm4server": [asdict(x) for x in list_key_files(args.tm4server, KEY_FILES)],
            "runtime": [asdict(x) for x in list_key_files(args.runtime, [
                "control.json",
                "control_history.jsonl",
                "status.json",
                "results_classified.json",
                "ledger.json",
            ])],
        },
        "trees": {
            "tm4server": [asdict(x) for x in build_tree(args.tm4server, args.max_depth, args.max_tree_entries)],
            "tm4core": [asdict(x) for x in build_tree(args.tm4core, args.max_depth, args.max_tree_entries)],
            "runtime": [asdict(x) for x in build_tree(args.runtime, args.max_depth, args.max_tree_entries)],
        },
        "services": [asdict(x) for x in get_systemd_services(SYSTEMD_CANDIDATES)],
        "ports": [asdict(x) for x in get_listening_ports()],
        "processes": get_ps_snapshot(),
        "latest_runs": [asdict(x) for x in find_latest_run_artifacts(args.runtime, args.max_runs)],
    }

    json_path = args.output_dir / f"server_inventory_{stamp}.json"
    md_path = args.output_dir / f"server_inventory_{stamp}.md"
    json_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(inventory), encoding="utf-8")

    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
