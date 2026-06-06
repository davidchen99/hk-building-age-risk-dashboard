from __future__ import annotations

import json

import pandas as pd

from src.utils.config import BUILDINGS_PARQUET, DISTRICT_METRICS_PARQUET, MANIFEST_PATH, REGULATORY_NOTICES_PARQUET
from src.utils.io import read_parquet


def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    buildings = read_parquet(BUILDINGS_PARQUET) if BUILDINGS_PARQUET.exists() else pd.DataFrame()
    districts = read_parquet(DISTRICT_METRICS_PARQUET) if DISTRICT_METRICS_PARQUET.exists() else pd.DataFrame()
    notices = read_parquet(REGULATORY_NOTICES_PARQUET) if REGULATORY_NOTICES_PARQUET.exists() else pd.DataFrame()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    return buildings, districts, notices, manifest


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    result = df.copy()
    for column, values in filters.items():
        if values and column in result.columns:
            result = result[result[column].isin(values)]
    return result
