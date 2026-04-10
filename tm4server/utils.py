from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    # utf-8-sig handles files written by PowerShell (UTF-8 BOM) and plain UTF-8
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    # Explicit UTF-8 without BOM — safe on all platforms including Windows
    content = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(content, encoding="utf-8")


def append_line(path: Path, line: str) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def safe_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def variance(data: list[float]) -> float | None:
    if len(data) < 2:
        return 0.0
    mean = sum(data) / len(data)
    sq_diff = [(x - mean) ** 2 for x in data]
    return sum(sq_diff) / len(data)


def split_early_late(data: list[float]) -> tuple[list[float], list[float]]:
    if not data:
        return [], []
    if len(data) == 1:
        return data, data
    mid = len(data) // 2
    return data[:mid], data[mid:]


def extract_fitness_series(run_data: dict[str, Any]) -> list[float]:
    """
    Best-effort fitness series extraction from a run summary dictionary.
    """
    direct_series = run_data.get("best_fitness_by_gen")
    if isinstance(direct_series, list):
        return [float(x) for x in direct_series if safe_float(x) is not None]

    generation_summaries = run_data.get("generation_summaries")
    if isinstance(generation_summaries, list):
        series: list[float] = []
        for item in generation_summaries:
            if not isinstance(item, dict):
                continue
            value = safe_float(item.get("best_fitness"))
            if value is not None:
                series.append(value)
        if series:
            return series

    return []

