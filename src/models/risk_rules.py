from __future__ import annotations

import math
from typing import Any

import pandas as pd

RISK_MODEL_VERSION = "risk_rules_v0.3_age_regulatory_combined"

AGE_SCORES = [
    (0, 19, 10),
    (20, 29, 25),
    (30, 39, 45),
    (40, 49, 60),
    (50, 59, 75),
    (60, 10_000, 85),
]

USAGE_SCORES = {
    "Residential/Composite": 8,
    "Office/Commercial": 10,
    "Industrial": 15,
    "Others": 5,
    "Unknown": 0,
}

TYPE_SCORES = {
    "Tower": 5,
    "Podium": 3,
    "Unknown": 0,
}


def score_age(age: Any) -> float | None:
    if age is None or pd.isna(age) or (isinstance(age, float) and math.isnan(age)):
        return None
    age_int = int(age)
    for lower, upper, score in AGE_SCORES:
        if lower <= age_int <= upper:
            return float(score)
    return None


def risk_level(score: Any) -> str:
    if score is None or pd.isna(score) or (isinstance(score, float) and math.isnan(score)):
        return "Unknown"
    value = float(score)
    if value <= 30:
        return "Low"
    if value <= 55:
        return "Medium"
    if value <= 75:
        return "High"
    return "Critical"


def build_risk_reason(row: pd.Series) -> str:
    if pd.isna(row.get("building_age")):
        return "Building age is unavailable because the occupation permit date could not be parsed."
    age_only_score = row.get("age_only_risk_score", row.get("age_risk_score", "N/A"))
    combined_score = row.get("combined_risk_score", row.get("risk_score", "N/A"))
    parts = [
        f"Building age is {int(row['building_age'])} years ({row.get('age_band', 'Unknown')}).",
        f"Age-only score is {age_only_score}.",
        f"Usage group is {row.get('usage_group', 'Unknown')}.",
        f"Building type is {row.get('type_group', 'Unknown')}.",
        f"Combined score is {combined_score}.",
    ]
    if row.get("has_mbis_notice") is True:
        parts.append(f"Matched MBIS notice with {row.get('match_confidence', 'unknown')} confidence.")
    parts.append("This is a rule-based screening indicator, not a structural inspection result.")
    return " ".join(parts)


def apply_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["age_risk_score"] = result["building_age"].apply(score_age)
    result["age_only_risk_score"] = result["age_risk_score"]
    result["age_only_risk_level"] = result["age_only_risk_score"].apply(risk_level)
    result["usage_score"] = result["usage_group"].map(USAGE_SCORES).fillna(0).astype(float)
    result["type_score"] = result["type_group"].map(TYPE_SCORES).fillna(0).astype(float)
    if "regulatory_signal_score" not in result.columns:
        result["regulatory_signal_score"] = 0.0
    result["contextual_risk_score"] = result["usage_score"] + result["type_score"] + result["regulatory_signal_score"]
    result["risk_score"] = result.apply(
        lambda row: None
        if pd.isna(row["age_risk_score"])
        else min(max(row["age_only_risk_score"] + row["contextual_risk_score"], 0), 100),
        axis=1,
    )
    result["combined_risk_score"] = result["risk_score"]
    result["risk_level"] = result["risk_score"].apply(risk_level)
    result["combined_risk_level"] = result["risk_level"]
    result["risk_model_mode"] = "combined_age_usage_type_regulatory"
    result["risk_reason"] = result.apply(build_risk_reason, axis=1)
    return result
