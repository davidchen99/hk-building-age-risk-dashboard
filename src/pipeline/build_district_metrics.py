from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from src.models.district_index import AGE_ONLY_PRIORITY_WEIGHTS, COMBINED_PRIORITY_WEIGHTS, apply_district_priority_index
from src.utils.config import BUILDINGS_PARQUET, DISTRICT_METRICS_PARQUET, REGULATORY_NOTICES_PARQUET, log, update_manifest
from src.utils.io import read_parquet, write_parquet


def _safe_share(mask: pd.Series, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return float(mask.sum() / denominator)


def _safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0
    return float(values.mean())


def _quality_score(group: pd.DataFrame) -> float:
    total = len(group)
    if total == 0:
        return 0.0
    missing_age_rate = group["building_age"].isna().mean()
    invalid_coordinate_rate = (~group["has_valid_coordinate"].fillna(False)).mean()
    unknown_usage_rate = (group["usage_group"] == "Unknown").mean()
    unknown_type_rate = (group["type_group"] == "Unknown").mean()
    missing_address_rate = group["address_en"].isna().mean()
    score = 100 - missing_age_rate * 40 - invalid_coordinate_rate * 25 - unknown_usage_rate * 20 - unknown_type_rate * 10 - missing_address_rate * 5
    return float(min(max(score, 0), 100))


def build_district_metrics() -> pd.DataFrame:
    buildings = read_parquet(BUILDINGS_PARQUET)
    notices = read_parquet(REGULATORY_NOTICES_PARQUET) if REGULATORY_NOTICES_PARQUET.exists() else pd.DataFrame()
    notice_counts = pd.Series(dtype=int)
    if not notices.empty and "matched_building_id" in notices.columns:
        matched_ids = set(notices.loc[notices["match_confidence"].isin(["High", "Medium"]), "matched_building_id"].astype(str))
        matched_buildings = buildings[buildings["source_object_id"].astype(str).isin(matched_ids)]
        notice_counts = matched_buildings.groupby("district_en").size()

    rows = []
    for district, group in buildings.groupby("district_en", dropna=False):
        district_name = district if pd.notna(district) else "Unknown"
        valid_age = group["building_age"].dropna()
        valid_risk = group[group["risk_level"] != "Unknown"]
        valid_age_only_risk = group[group["age_only_risk_level"] != "Unknown"] if "age_only_risk_level" in group.columns else valid_risk
        valid_combined_risk = group[group["combined_risk_level"] != "Unknown"] if "combined_risk_level" in group.columns else valid_risk
        valid_age_count = int(valid_age.count())
        age_only_high_critical_count = (
            int(group["age_only_risk_level"].isin(["High", "Critical"]).sum()) if "age_only_risk_level" in group.columns else int(group["risk_level"].isin(["High", "Critical"]).sum())
        )
        combined_high_critical_count = (
            int(group["combined_risk_level"].isin(["High", "Critical"]).sum()) if "combined_risk_level" in group.columns else int(group["risk_level"].isin(["High", "Critical"]).sum())
        )
        commercial_mask = group["usage_group"].isin(["Industrial", "Office/Commercial"])
        total = int(len(group))
        mbis_notice_count = int(notice_counts.get(district_name, 0))
        rows.append(
            {
                "district_en": district_name,
                "district_tc": group["district_tc"].dropna().iloc[0] if group["district_tc"].notna().any() else "",
                "total_buildings": total,
                "valid_age_count": valid_age_count,
                "median_age": float(valid_age.median()) if valid_age_count else 0.0,
                "mean_age": float(valid_age.mean()) if valid_age_count else 0.0,
                "p75_age": float(valid_age.quantile(0.75)) if valid_age_count else 0.0,
                "share_30_plus": _safe_share(group["building_age"] >= 30, valid_age_count),
                "share_40_plus": _safe_share(group["building_age"] >= 40, valid_age_count),
                "share_50_plus": _safe_share(group["building_age"] >= 50, valid_age_count),
                "share_60_plus": _safe_share(group["building_age"] >= 60, valid_age_count),
                "age_only_mean_risk_score": _safe_mean(group.get("age_only_risk_score", pd.Series(dtype=float))),
                "combined_mean_risk_score": _safe_mean(group.get("combined_risk_score", group.get("risk_score", pd.Series(dtype=float)))),
                "age_only_high_critical_count": age_only_high_critical_count,
                "age_only_high_critical_share": _safe_share(
                    group["age_only_risk_level"].isin(["High", "Critical"]) if "age_only_risk_level" in group.columns else group["risk_level"].isin(["High", "Critical"]),
                    len(valid_age_only_risk),
                ),
                "combined_high_critical_count": combined_high_critical_count,
                "combined_high_critical_share": _safe_share(
                    group["combined_risk_level"].isin(["High", "Critical"]) if "combined_risk_level" in group.columns else group["risk_level"].isin(["High", "Critical"]),
                    len(valid_combined_risk),
                ),
                "high_critical_count": combined_high_critical_count,
                "high_critical_share": _safe_share(group["risk_level"].isin(["High", "Critical"]), len(valid_risk)),
                "mbis_notice_count": mbis_notice_count,
                "mbis_notice_rate": float(mbis_notice_count / total * 1000) if total else 0.0,
                "industrial_or_commercial_share": float(commercial_mask.sum() / total) if total else 0.0,
                "data_quality_score": round(_quality_score(group), 2),
            }
        )
    metrics = pd.DataFrame(rows)
    metrics = apply_district_priority_index(metrics, combined=not notices.empty)
    write_parquet(metrics, DISTRICT_METRICS_PARQUET)
    update_manifest(
        "district_metrics",
        {
            "output_file": str(DISTRICT_METRICS_PARQUET),
            "district_count": int(len(metrics)),
            "record_count": int(len(buildings)),
            "priority_mode": "combined_age_regulatory" if not notices.empty else "age_only",
            "priority_weights": json.dumps(COMBINED_PRIORITY_WEIGHTS if not notices.empty else AGE_ONLY_PRIORITY_WEIGHTS, ensure_ascii=False),
        },
    )
    log(f"District metrics ready: {len(metrics)} districts")
    return metrics


def main() -> None:
    argparse.ArgumentParser().parse_args()
    build_district_metrics()


if __name__ == "__main__":
    main()
