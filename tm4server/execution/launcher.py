import os
import sys
from pathlib import Path
from typing import Any

def build_tm4_command(tm4core_repo: Path, run_dir: Path) -> tuple[list[str], dict[str, str]]:
    """
    Normalizes the contract between TM4Server and TM4 core.
    Maps a run_dir into a subprocess launch specification.
    """
    # Use the current python executable if in venv, fall back to python3
    python_bin = sys.executable or "python3"
    
    # The canonical entrypoint for Phase 2A
    cmd = [
        python_bin,
        "-m",
        "mvp.scripts.run_autonomy_loop",
        "--output-dir",
        str(run_dir)
    ]
    
    # Environment contract
    env = os.environ.copy()
    env["TM4_RUN_DIR"] = str(run_dir)
    env["TM4_STATUS_FILE"] = str(run_dir / "status.json")
    
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{tm4core_repo}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(tm4core_repo)
    )
    
    return cmd, env
