from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_DIR = DATA_DIR / "sample"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
FIGURES_DIR = OUTPUTS_DIR / "figures"
EXPORTS_DIR = OUTPUTS_DIR / "exports"
EXPORT_PACKAGE_ZIP = EXPORTS_DIR / "export_package.zip"

BUILDINGS_PARQUET = PROCESSED_DIR / "buildings.parquet"
DISTRICT_METRICS_PARQUET = PROCESSED_DIR / "district_metrics.parquet"
REGULATORY_NOTICES_PARQUET = PROCESSED_DIR / "regulatory_notices.parquet"
DATA_QUALITY_ISSUES_PARQUET = PROCESSED_DIR / "data_quality_issues.parquet"
MANIFEST_PATH = CACHE_DIR / "source_manifest.json"
PIPELINE_LOG_PATH = CACHE_DIR / "pipeline_run.log"


def ensure_dirs() -> None:
    for path in [
        RAW_DIR,
        PROCESSED_DIR,
        CACHE_DIR,
        SAMPLE_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        EXPORTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_manifest(manifest: dict[str, Any]) -> None:
    ensure_dirs()
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


def update_manifest(key: str, payload: dict[str, Any]) -> None:
    manifest = load_manifest()
    manifest[key] = {**manifest.get(key, {}), **payload, "updated_at": now_iso()}
    save_manifest(manifest)


def log(message: str) -> None:
    ensure_dirs()
    line = f"[{now_iso()}] {message}"
    print(line)
    for attempt in range(3):
        try:
            with PIPELINE_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return
        except OSError:
            if attempt == 2:
                return
            time.sleep(0.05)


def resolve_path(path: str | Path | None, default: Path) -> Path:
    if path is None:
        return default
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate
