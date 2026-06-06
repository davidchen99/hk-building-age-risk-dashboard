from __future__ import annotations

import argparse
import json

import pandas as pd

from src.utils.config import BUILDINGS_PARQUET, DATA_QUALITY_ISSUES_PARQUET, DISTRICT_METRICS_PARQUET, MANIFEST_PATH, REGULATORY_NOTICES_PARQUET, log
from src.utils.io import read_parquet

REQUIRED_BUILDING_FIELDS = {
    "source_object_id",
    "source_dataset",
    "address_en",
    "district_en",
    "territory_en",
    "occupation_permit_date",
    "occupation_permit_year",
    "building_age",
    "age_band",
    "usage_group",
    "type_group",
    "latitude",
    "longitude",
    "has_valid_coordinate",
    "age_only_risk_score",
    "age_only_risk_level",
    "contextual_risk_score",
    "combined_risk_score",
    "combined_risk_level",
    "risk_score",
    "risk_level",
    "risk_model_mode",
    "risk_reason",
    "data_quality_flags",
}

VALID_RISK_LEVELS = {"Low", "Medium", "High", "Critical", "Unknown"}
REQUIRED_DISTRICT_FIELDS = {
    "age_only_mean_risk_score",
    "combined_mean_risk_score",
    "age_only_high_critical_share",
    "combined_high_critical_share",
    "priority_median_age_component",
    "priority_share_50_plus_component",
    "priority_high_critical_component",
    "priority_mbis_notice_component",
    "priority_usage_mix_component",
    "district_priority_mode",
}


def validate_outputs(strict: bool = False) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if not BUILDINGS_PARQUET.exists():
        errors.append(f"Missing {BUILDINGS_PARQUET}")
        raise RuntimeError("; ".join(errors))
    buildings = read_parquet(BUILDINGS_PARQUET)
    missing = REQUIRED_BUILDING_FIELDS - set(buildings.columns)
    if missing:
        errors.append(f"Missing building fields: {sorted(missing)}")
    if buildings.empty:
        errors.append("buildings.parquet is empty")
    risk_levels = set(buildings["risk_level"].dropna().unique())
    if not risk_levels <= VALID_RISK_LEVELS:
        errors.append(f"Invalid risk levels: {sorted(risk_levels - VALID_RISK_LEVELS)}")
    risk_scores = pd.to_numeric(buildings["risk_score"], errors="coerce").dropna()
    if not risk_scores.between(0, 100).all():
        errors.append("risk_score contains values outside 0-100")
    age_parse_rate = float(buildings["building_age"].notna().mean()) if len(buildings) else 0
    coordinate_valid_rate = float(buildings["has_valid_coordinate"].fillna(False).mean()) if len(buildings) else 0
    if age_parse_rate < 0.90:
        (errors if strict else warnings).append(f"Age parse rate below 90%: {age_parse_rate:.2%}")
    if coordinate_valid_rate < 0.80:
        (errors if strict else warnings).append(f"Coordinate valid rate below 80%: {coordinate_valid_rate:.2%}")
    if not DISTRICT_METRICS_PARQUET.exists():
        errors.append(f"Missing {DISTRICT_METRICS_PARQUET}")
    else:
        metrics = read_parquet(DISTRICT_METRICS_PARQUET)
        if metrics.empty:
            errors.append("district_metrics.parquet is empty")
        missing_district = REQUIRED_DISTRICT_FIELDS - set(metrics.columns)
        if missing_district:
            errors.append(f"Missing district metric fields: {sorted(missing_district)}")
    if not REGULATORY_NOTICES_PARQUET.exists():
        warnings.append(f"Missing {REGULATORY_NOTICES_PARQUET}; regulatory signals are not available")
    if DATA_QUALITY_ISSUES_PARQUET.exists():
        issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET)
        if "issue_flags" not in issues.columns:
            errors.append("data_quality_issues.parquet missing issue_flags")
    else:
        warnings.append(f"Missing {DATA_QUALITY_ISSUES_PARQUET}; data quality issue export is not available")
    if not MANIFEST_PATH.exists():
        errors.append(f"Missing {MANIFEST_PATH}")
    summary = {
        "record_count": int(len(buildings)),
        "age_parse_rate": age_parse_rate,
        "coordinate_valid_rate": coordinate_valid_rate,
        "data_quality_issue_count": int(len(issues)) if DATA_QUALITY_ISSUES_PARQUET.exists() else None,
        "risk_levels": sorted(risk_levels),
        "errors": errors,
        "warnings": warnings,
    }
    log(json.dumps(summary, ensure_ascii=False))
    if errors:
        raise RuntimeError("; ".join(errors))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    validate_outputs(strict=args.strict)


if __name__ == "__main__":
    main()
