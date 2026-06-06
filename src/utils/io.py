from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pandas as pd


def read_csv_flexible(path: Path) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "big5", "gbk", "latin1"]
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:  # pragma: no cover - exercised only for bad encodings
            last_error = exc
    raise RuntimeError(f"Failed to read CSV {path}: {last_error}")


def extract_zip(zip_path: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
    return list(destination.rglob("*.csv"))


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: OSError | None = None
    for attempt in range(6):
        try:
            df.to_parquet(path, index=False)
            return
        except OSError as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(0.25 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed to write parquet: {path}")


def read_parquet(path: Path) -> pd.DataFrame:
    last_error: OSError | None = None
    for attempt in range(6):
        try:
            return pd.read_parquet(path)
        except OSError as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(0.25 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed to read parquet: {path}")
