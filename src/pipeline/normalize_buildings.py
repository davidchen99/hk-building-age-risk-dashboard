from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data_sources.fetch_bdbiar import fetch_bdbiar
from src.models.risk_rules import apply_risk_scores
from src.utils.config import BUILDINGS_PARQUET, DATA_QUALITY_ISSUES_PARQUET, ensure_dirs, load_manifest, log, update_manifest
from src.utils.io import read_csv_flexible, write_parquet

FIELD_MAP = {
    "OBJECTID": "source_object_id",
    "DATASET_E": "source_dataset",
    "ADDRESS_E": "address_en",
    "ADDRESS_C": "address_tc",
    "SEARCH1_E": "district_en",
    "SEARCH1_C": "district_tc",
    "SEARCH2_E": "territory_en",
    "SEARCH2_C": "territory_tc",
    "NSEARCH1_E": "block_id",
    "NSEARCH2_E": "occupation_permit_no",
    "NSEARCH3_E": "occupation_permit_date",
    "NSEARCH4_E": "building_type",
    "NSEARCH5_E": "building_usage",
    "LATITUDE": "source_latitude",
    "LONGITUDE": "source_longitude",
    "GeometryLongitude": "geometry_longitude",
    "GeometryLatitude": "geometry_latitude",
}

COMPATIBLE_ALIASES = {
    "OBJECTID": ["OBJECTID", "building_id", "id", "bldg_id", "building_code"],
    "DATASET_E": ["DATASET_E", "source_dataset"],
    "DATASET_C": ["DATASET_C"],
    "ADDRESS_E": ["ADDRESS_E", "address_en", "address", "english_address"],
    "ADDRESS_C": ["ADDRESS_C", "address_tc", "chinese_address"],
    "SEARCH1_E": ["SEARCH1_E", "district_en", "district", "area", "region", "district_name"],
    "SEARCH1_C": ["SEARCH1_C", "district_tc"],
    "SEARCH2_E": ["SEARCH2_E", "territory_en", "territory"],
    "SEARCH2_C": ["SEARCH2_C", "territory_tc"],
    "NSEARCH1_E": ["NSEARCH1_E", "block_id"],
    "NSEARCH1_C": ["NSEARCH1_C", "block_id"],
    "NSEARCH2_E": ["NSEARCH2_E", "occupation_permit_no", "op_no"],
    "NSEARCH2_C": ["NSEARCH2_C", "occupation_permit_no", "op_no"],
    "NSEARCH3_E": ["NSEARCH3_E", "occupation_permit_date", "op_date", "completion_date", "completion_year", "year_built", "built_year", "year"],
    "NSEARCH3_C": ["NSEARCH3_C", "occupation_permit_date", "op_date", "completion_date", "completion_year", "year_built", "built_year", "year"],
    "NSEARCH4_E": ["NSEARCH4_E", "building_type", "type", "type_group"],
    "NSEARCH4_C": ["NSEARCH4_C", "building_type_tc"],
    "NSEARCH5_E": ["NSEARCH5_E", "building_usage", "usage_group", "building_use", "use", "usage", "property_type"],
    "NSEARCH5_C": ["NSEARCH5_C", "building_usage_tc"],
    "LATITUDE": ["LATITUDE", "latitude", "lat", "y"],
    "LONGITUDE": ["LONGITUDE", "longitude", "lon", "lng", "x"],
    "GeometryLongitude": ["GeometryLongitude", "geometry_longitude", "longitude", "lon", "lng", "x"],
    "GeometryLatitude": ["GeometryLatitude", "geometry_latitude", "latitude", "lat", "y"],
}

TEXT_FIELDS = [
    "source_object_id",
    "source_dataset",
    "address_en",
    "address_tc",
    "district_en",
    "district_tc",
    "territory_en",
    "territory_tc",
    "block_id",
    "occupation_permit_no",
    "building_type",
    "building_usage",
]

USAGE_VALUES = {"Residential/Composite", "Office/Commercial", "Industrial", "Others"}
TYPE_VALUES = {"Tower", "Podium"}


def _clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.upper() in {"", "N/A", "NA", "NULL", "-"}:
        return None
    return text


def _first_existing_column(raw: pd.DataFrame, aliases: list[str]) -> str | None:
    lower_lookup = {column.lower(): column for column in raw.columns}
    for alias in aliases:
        if alias in raw.columns:
            return alias
        match = lower_lookup.get(alias.lower())
        if match:
            return match
    return None


def _coerce_year_or_date(value: object) -> object:
    if value is None or pd.isna(value):
        return value
    text = str(value).strip()
    if text.isdigit() and len(text) == 4:
        return f"{text}-01-01"
    return value


def _coerce_compatible_source(raw: pd.DataFrame) -> pd.DataFrame:
    official_available = all(field in raw.columns for field in FIELD_MAP)
    if official_available:
        return raw

    compatible = pd.DataFrame(index=raw.index)
    for official_field, aliases in COMPATIBLE_ALIASES.items():
        source_column = _first_existing_column(raw, aliases)
        if source_column:
            compatible[official_field] = raw[source_column]
        else:
            compatible[official_field] = pd.NA

    compatible["DATASET_E"] = compatible["DATASET_E"].fillna("User uploaded building records")
    compatible["DATASET_C"] = compatible["DATASET_C"].fillna("用戶上載樓宇資料")
    compatible["SEARCH2_E"] = compatible["SEARCH2_E"].fillna("Unknown")
    compatible["SEARCH2_C"] = compatible["SEARCH2_C"].fillna("")
    compatible["NSEARCH4_E"] = compatible["NSEARCH4_E"].fillna("Unknown")
    compatible["NSEARCH5_E"] = compatible["NSEARCH5_E"].fillna("Unknown")
    compatible["NSEARCH3_E"] = compatible["NSEARCH3_E"].map(_coerce_year_or_date)
    compatible["NSEARCH3_C"] = compatible["NSEARCH3_C"].map(_coerce_year_or_date)
    compatible["OBJECTID"] = compatible["OBJECTID"].fillna(pd.Series(range(1, len(compatible) + 1), index=compatible.index).astype(str))
    return compatible


def _age_band(age: object) -> str:
    if pd.isna(age):
        return "Unknown"
    age_int = int(age)
    if age_int <= 19:
        return "0-19"
    if age_int <= 29:
        return "20-29"
    if age_int <= 39:
        return "30-39"
    if age_int <= 49:
        return "40-49"
    if age_int <= 59:
        return "50-59"
    return "60+"


def _standardize_usage(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return "Unknown"
    lowered = text.lower()
    if "industrial" in lowered:
        return "Industrial"
    if "office" in lowered or "commercial" in lowered or lowered in {"retail", "shop"}:
        return "Office/Commercial"
    if "residential" in lowered or "domestic" in lowered or "composite" in lowered or "mixed" in lowered:
        return "Residential/Composite"
    if text in USAGE_VALUES:
        return text
    if lowered == "others" or lowered == "other":
        return "Others"
    return "Unknown"


def _standardize_type(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return "Unknown"
    lowered = text.lower()
    if "tower" in lowered or text == "座":
        return "Tower"
    if "podium" in lowered or "platform" in lowered or text == "平台":
        return "Podium"
    if text in TYPE_VALUES:
        return text
    return "Unknown"


def _flags(row: pd.Series) -> list[str]:
    flags: list[str] = []
    if not row.get("address_en"):
        flags.append("missing_address")
    if not row.get("district_en"):
        flags.append("missing_district")
    if pd.isna(row.get("occupation_permit_date")):
        flags.append("missing_op_date")
    future_op_date = row.get("future_op_date")
    if future_op_date is True or str(future_op_date).lower() == "true":
        flags.append("future_op_date")
    invalid_early_op_date = row.get("invalid_early_op_date")
    if invalid_early_op_date is True or str(invalid_early_op_date).lower() == "true":
        flags.append("invalid_op_date_before_1800")
    if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
        flags.append("missing_coordinate")
    elif not row.get("has_valid_coordinate"):
        flags.append("invalid_coordinate")
    if row.get("usage_group") == "Unknown":
        flags.append("unknown_usage")
    if row.get("type_group") == "Unknown":
        flags.append("unknown_type")
    duplicate_source_object_id = row.get("duplicate_source_object_id")
    if duplicate_source_object_id is True or str(duplicate_source_object_id).lower() == "true":
        flags.append("duplicate_source_object_id")
    return flags


def _loads_flags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or pd.isna(value):
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _write_data_quality_issues(df: pd.DataFrame) -> pd.DataFrame:
    issue_rows = []
    for _, row in df.iterrows():
        flags = _loads_flags(row.get("data_quality_flags"))
        if not flags:
            continue
        issue_rows.append(
            {
                "source_object_id": row.get("source_object_id"),
                "address_en": row.get("address_en"),
                "district_en": row.get("district_en") or "Unknown",
                "usage_group": row.get("usage_group") or "Unknown",
                "occupation_permit_date": row.get("occupation_permit_date"),
                "occupation_permit_year": row.get("occupation_permit_year"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "issue_flags": json.dumps(flags, ensure_ascii=False),
                "issue_count": len(flags),
            }
        )
    issues = pd.DataFrame(issue_rows)
    if issues.empty:
        issues = pd.DataFrame(
            columns=[
                "source_object_id",
                "address_en",
                "district_en",
                "usage_group",
                "occupation_permit_date",
                "occupation_permit_year",
                "latitude",
                "longitude",
                "issue_flags",
                "issue_count",
            ]
        )
    write_parquet(issues, DATA_QUALITY_ISSUES_PARQUET)
    return issues


def normalize_buildings(csv_path: Path | None = None, analysis_year: int | None = None) -> pd.DataFrame:
    ensure_dirs()
    if analysis_year is None:
        analysis_year = datetime.now().year
    if csv_path is None:
        csv_path = fetch_bdbiar(use_cache=True)
    raw = read_csv_flexible(csv_path)
    raw = _coerce_compatible_source(raw)
    missing = [field for field in FIELD_MAP if field not in raw.columns]
    if missing:
        raise ValueError(f"Missing required source fields: {missing}")
    df = raw.rename(columns=FIELD_MAP)[list(FIELD_MAP.values())].copy()
    for field in TEXT_FIELDS:
        df[field] = df[field].map(_clean_text)

    df["occupation_permit_date"] = pd.to_datetime(df["occupation_permit_date"], errors="coerce")
    df["occupation_permit_year"] = df["occupation_permit_date"].dt.year.astype("Int64")
    df["invalid_early_op_date"] = df["occupation_permit_year"] < 1800
    df["future_op_date"] = df["occupation_permit_year"] > analysis_year
    invalid_op_date = df["future_op_date"].fillna(False) | df["invalid_early_op_date"].fillna(False)
    df.loc[invalid_op_date, ["occupation_permit_date", "occupation_permit_year"]] = pd.NA
    df["building_age"] = (analysis_year - df["occupation_permit_year"]).astype("Int64")
    df["age_band"] = df["building_age"].apply(_age_band)

    df["usage_group"] = df["building_usage"].map(_standardize_usage)
    df["type_group"] = df["building_type"].map(_standardize_type)

    for field in ["source_latitude", "source_longitude", "geometry_latitude", "geometry_longitude"]:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    df["latitude"] = df["geometry_latitude"].combine_first(df["source_latitude"])
    df["longitude"] = df["geometry_longitude"].combine_first(df["source_longitude"])
    df["has_valid_coordinate"] = df["latitude"].between(22.10, 22.60) & df["longitude"].between(113.80, 114.45)

    df["has_mbis_notice"] = False
    df["match_confidence"] = "Unmatched"
    df["regulatory_signal_score"] = 0.0
    df["duplicate_source_object_id"] = df["source_object_id"].notna() & df.duplicated("source_object_id", keep=False)
    df["data_quality_flags"] = df.apply(lambda row: json.dumps(_flags(row), ensure_ascii=False), axis=1)
    quality_issues = _write_data_quality_issues(df)
    df = apply_risk_scores(df)

    write_parquet(df, BUILDINGS_PARQUET)
    manifest = load_manifest().get("bdbiar", {})
    update_manifest(
        "buildings_processed",
        {
            "source_file": str(csv_path),
            "output_file": str(BUILDINGS_PARQUET),
            "record_count": int(len(df)),
            "analysis_year": analysis_year,
            "age_parse_rate": float(df["building_age"].notna().mean()) if len(df) else 0,
            "coordinate_valid_rate": float(df["has_valid_coordinate"].mean()) if len(df) else 0,
            "data_quality_issue_count": int(len(quality_issues)),
            "source_manifest": manifest,
        },
    )
    update_manifest(
        "data_quality_issues",
        {
            "output_file": str(DATA_QUALITY_ISSUES_PARQUET),
            "record_count": int(len(quality_issues)),
        },
    )
    log(f"Normalized buildings: {len(df)} rows -> {BUILDINGS_PARQUET}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-path")
    parser.add_argument("--analysis-year", type=int)
    args = parser.parse_args()
    normalize_buildings(Path(args.csv_path) if args.csv_path else None, args.analysis_year)


if __name__ == "__main__":
    main()
