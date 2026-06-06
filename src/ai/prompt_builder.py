from __future__ import annotations

from typing import Any

import pandas as pd

from src.models.risk_rules import RISK_MODEL_VERSION

PROMPT_VERSION = "summary_prompt_v0.2_with_regulatory_signals"


def _distribution(df: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    if df.empty or column not in df.columns:
        return []
    counts = df[column].fillna("Unknown").value_counts().reset_index()
    counts.columns = [column, "count"]
    total = counts["count"].sum()
    counts["share"] = counts["count"] / total if total else 0
    return counts.to_dict("records")


def build_analysis_payload(
    buildings: pd.DataFrame,
    district_metrics: pd.DataFrame,
    notices: pd.DataFrame,
    filters: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    manifest = manifest or {}
    valid_age = buildings["building_age"].dropna() if "building_age" in buildings else pd.Series(dtype=float)
    valid_risk = buildings[buildings.get("risk_level", pd.Series(dtype=str)) != "Unknown"] if "risk_level" in buildings else pd.DataFrame()
    valid_age_only_risk = buildings[buildings.get("age_only_risk_level", pd.Series(dtype=str)) != "Unknown"] if "age_only_risk_level" in buildings else pd.DataFrame()
    valid_combined_risk = buildings[buildings.get("combined_risk_level", pd.Series(dtype=str)) != "Unknown"] if "combined_risk_level" in buildings else valid_risk
    total = len(buildings)
    age_only_scores = pd.to_numeric(buildings.get("age_only_risk_score", pd.Series(dtype=float)), errors="coerce").dropna()
    combined_scores = pd.to_numeric(buildings.get("combined_risk_score", buildings.get("risk_score", pd.Series(dtype=float))), errors="coerce").dropna()
    contextual_scores = pd.to_numeric(buildings.get("contextual_risk_score", pd.Series(dtype=float)), errors="coerce").dropna()
    portfolio_metrics = {
        "total_buildings": int(total),
        "mean_age": float(valid_age.mean()) if len(valid_age) else 0,
        "median_age": float(valid_age.median()) if len(valid_age) else 0,
        "share_30_plus": float((buildings["building_age"] >= 30).sum() / len(valid_age)) if len(valid_age) else 0,
        "share_40_plus": float((buildings["building_age"] >= 40).sum() / len(valid_age)) if len(valid_age) else 0,
        "share_50_plus": float((buildings["building_age"] >= 50).sum() / len(valid_age)) if len(valid_age) else 0,
        "share_60_plus": float((buildings["building_age"] >= 60).sum() / len(valid_age)) if len(valid_age) else 0,
        "high_critical_share": float(buildings["risk_level"].isin(["High", "Critical"]).sum() / len(valid_risk)) if len(valid_risk) else 0,
    }
    risk_model_breakdown = {
        "age_only_mean_risk_score": float(age_only_scores.mean()) if len(age_only_scores) else 0,
        "combined_mean_risk_score": float(combined_scores.mean()) if len(combined_scores) else 0,
        "mean_contextual_risk_score": float(contextual_scores.mean()) if len(contextual_scores) else 0,
        "age_only_high_critical_share": float(buildings["age_only_risk_level"].isin(["High", "Critical"]).sum() / len(valid_age_only_risk))
        if len(valid_age_only_risk) and "age_only_risk_level" in buildings
        else 0,
        "combined_high_critical_share": float(buildings["combined_risk_level"].isin(["High", "Critical"]).sum() / len(valid_combined_risk))
        if len(valid_combined_risk) and "combined_risk_level" in buildings
        else portfolio_metrics["high_critical_share"],
        "records_with_regulatory_signal": int(buildings["has_mbis_notice"].fillna(False).sum()) if "has_mbis_notice" in buildings else 0,
    }
    top_districts = district_metrics.sort_values("district_priority_index", ascending=False).head(10).to_dict("records") if not district_metrics.empty else []
    payload = {
        "analysis_scope": {"filters": filters},
        "data_version": manifest,
        "model_version": RISK_MODEL_VERSION,
        "prompt_version": PROMPT_VERSION,
        "portfolio_metrics": portfolio_metrics,
        "age_distribution": _distribution(buildings, "age_band"),
        "age_only_risk_distribution": _distribution(buildings, "age_only_risk_level"),
        "risk_distribution": _distribution(buildings, "risk_level"),
        "combined_risk_distribution": _distribution(buildings, "combined_risk_level"),
        "risk_model_breakdown": risk_model_breakdown,
        "district_ranking": top_districts,
        "usage_analysis": _distribution(buildings, "usage_group"),
        "regulatory_signals": {
            "notice_count": int(len(notices)) if notices is not None else 0,
            "matched_count": int(notices["match_confidence"].isin(["High", "Medium"]).sum()) if notices is not None and not notices.empty and "match_confidence" in notices.columns else 0,
        },
        "data_quality": {
            "coordinate_valid_rate": float(buildings["has_valid_coordinate"].fillna(False).mean()) if total and "has_valid_coordinate" in buildings else 0,
            "age_parse_rate": float(buildings["building_age"].notna().mean()) if total and "building_age" in buildings else 0,
            "unknown_usage_count": int((buildings["usage_group"] == "Unknown").sum()) if total and "usage_group" in buildings else 0,
            "unknown_type_count": int((buildings["type_group"] == "Unknown").sum()) if total and "type_group" in buildings else 0,
            "invalid_coordinate_count": int((~buildings["has_valid_coordinate"].fillna(False)).sum()) if total and "has_valid_coordinate" in buildings else 0,
        },
        "limitations": [
            "Risk scores are rule-based screening indicators, not structural inspection results.",
            "Regulatory notices are public-record signals, not direct proof of structural defects.",
            "Results depend on public data field completeness and matching quality.",
        ],
    }
    return payload


def build_prompt(payload: dict[str, Any], language: str = "zh") -> str:
    output_language = "Chinese" if language == "zh" else "English"
    return (
        "You are an urban building asset risk analyst. "
        f"Write a concise {output_language} report from the structured JSON only. "
        "Do not invent data. Do not claim this is a structural inspection. "
        "Include Overall Risk Summary, Key Observations, Maintenance Priorities, Data Limitations, and Method Note.\n\n"
        f"JSON:\n{payload}"
    )
