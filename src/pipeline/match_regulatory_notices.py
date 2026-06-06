from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_sources.fetch_mbis import fetch_mbis
from src.models.risk_rules import apply_risk_scores
from src.utils.config import BUILDINGS_PARQUET, REGULATORY_NOTICES_PARQUET, log, update_manifest
from src.utils.io import read_csv_flexible, read_parquet, write_parquet


def normalize_address(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).upper()
    text = re.sub(r"\bROAD\b", "RD", text)
    text = re.sub(r"\bSTREET\b", "ST", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def standardize_mbis(csv_path: Path | None = None) -> pd.DataFrame:
    if csv_path is None:
        csv_path = fetch_mbis(use_cache=True)
    if not csv_path.exists():
        df = pd.DataFrame(
            columns=[
                "notice_source",
                "source_object_id",
                "notice_name_en",
                "address_en",
                "address_tc",
                "notice_count",
                "notice_ref",
                "latitude",
                "longitude",
                "last_update",
                "matched_building_id",
                "match_method",
                "match_distance_m",
                "match_confidence",
            ]
        )
        write_parquet(df, REGULATORY_NOTICES_PARQUET)
        return df
    raw = read_csv_flexible(csv_path)
    if raw.empty:
        write_parquet(raw, REGULATORY_NOTICES_PARQUET)
        return raw
    df = pd.DataFrame()
    df["notice_source"] = "MBIS_issued"
    df["source_object_id"] = raw.get("OBJECTID", raw.get("GmlId", pd.Series(index=raw.index))).astype(str)
    df["notice_name_en"] = raw.get("NAME_EN", pd.Series(index=raw.index)).astype(str)
    df["address_en"] = raw.get("ADDRESS_EN", pd.Series(index=raw.index)).astype(str)
    df["address_tc"] = raw.get("ADDRESS_TC", pd.Series(index=raw.index)).astype(str)
    df["notice_count"] = pd.to_numeric(raw.get("NSEARCH01_EN", 1), errors="coerce").fillna(1).astype(int)
    df["notice_ref"] = raw.get("NSEARCH02_EN", pd.Series(index=raw.index)).astype(str)
    df["latitude"] = pd.to_numeric(raw.get("LATITUDE", pd.Series(index=raw.index)), errors="coerce")
    df["longitude"] = pd.to_numeric(raw.get("LONGITUDE", pd.Series(index=raw.index)), errors="coerce")
    df["last_update"] = pd.to_datetime(raw.get("LASTUPDATE", pd.Series(index=raw.index)), errors="coerce")
    df["matched_building_id"] = ""
    df["match_method"] = "unmatched"
    df["match_distance_m"] = np.nan
    df["match_confidence"] = "Unmatched"
    return df


def _distance_m(lat1: float, lon1: float, lat2: pd.Series, lon2: pd.Series) -> pd.Series:
    return np.sqrt(((lat2 - lat1) * 111_000) ** 2 + ((lon2 - lon1) * 102_000) ** 2)


def match_regulatory_notices() -> pd.DataFrame:
    buildings = read_parquet(BUILDINGS_PARQUET)
    notices = standardize_mbis()
    if notices.empty or buildings.empty:
        write_parquet(notices, REGULATORY_NOTICES_PARQUET)
        update_manifest("mbis_matching", {"matched_count": 0, "notice_count": int(len(notices))})
        return notices

    building_addresses = buildings["address_en"].map(normalize_address)
    valid_coords = buildings[buildings["has_valid_coordinate"].fillna(False)].copy()

    matched_ids: list[str] = []
    methods: list[str] = []
    distances: list[float] = []
    confidences: list[str] = []

    for _, notice in notices.iterrows():
        notice_address = normalize_address(notice["address_en"])
        exact = buildings[building_addresses == notice_address]
        if notice_address and not exact.empty:
            matched_ids.append(str(exact.iloc[0]["source_object_id"]))
            methods.append("exact_address")
            distances.append(0.0)
            confidences.append("High")
            continue
        if pd.notna(notice["latitude"]) and pd.notna(notice["longitude"]) and not valid_coords.empty:
            dists = _distance_m(float(notice["latitude"]), float(notice["longitude"]), valid_coords["latitude"], valid_coords["longitude"])
            min_idx = dists.idxmin()
            min_dist = float(dists.loc[min_idx])
            if min_dist <= 20:
                matched_ids.append(str(valid_coords.loc[min_idx, "source_object_id"]))
                methods.append("spatial_20m")
                distances.append(min_dist)
                confidences.append("High")
                continue
            if min_dist <= 50:
                matched_ids.append(str(valid_coords.loc[min_idx, "source_object_id"]))
                methods.append("spatial_50m")
                distances.append(min_dist)
                confidences.append("Medium")
                continue
        matched_ids.append("")
        methods.append("unmatched")
        distances.append(np.nan)
        confidences.append("Unmatched")

    notices["matched_building_id"] = matched_ids
    notices["match_method"] = methods
    notices["match_distance_m"] = distances
    notices["match_confidence"] = confidences
    write_parquet(notices, REGULATORY_NOTICES_PARQUET)

    matched = notices[notices["match_confidence"].isin(["High", "Medium"])]
    if not matched.empty:
        buildings = buildings.copy()
        confidence_by_id = matched.groupby("matched_building_id")["match_confidence"].first()
        buildings["match_confidence"] = buildings["source_object_id"].astype(str).map(confidence_by_id).fillna(buildings["match_confidence"])
        buildings["has_mbis_notice"] = buildings["match_confidence"].isin(["High", "Medium"])
        buildings["regulatory_signal_score"] = buildings["match_confidence"].map({"High": 15.0, "Medium": 8.0}).fillna(0.0)
        buildings = apply_risk_scores(buildings)
        write_parquet(buildings, BUILDINGS_PARQUET)

    update_manifest(
        "mbis_matching",
        {
            "notice_count": int(len(notices)),
            "matched_count": int(len(matched)),
            "match_rate": float(len(matched) / len(notices)) if len(notices) else 0,
            "output_file": str(REGULATORY_NOTICES_PARQUET),
        },
    )
    log(f"MBIS notices standardized and matched: {len(matched)}/{len(notices)}")
    return notices


def main() -> None:
    argparse.ArgumentParser().parse_args()
    match_regulatory_notices()


if __name__ == "__main__":
    main()
