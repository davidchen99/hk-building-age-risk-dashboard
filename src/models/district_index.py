from __future__ import annotations

import pandas as pd

COMBINED_PRIORITY_WEIGHTS = {
    "median_age": 0.30,
    "share_50_plus": 0.25,
    "high_critical_share": 0.20,
    "mbis_notice_rate": 0.15,
    "industrial_or_commercial_share": 0.10,
}

AGE_ONLY_PRIORITY_WEIGHTS = {
    "median_age": 0.35,
    "share_50_plus": 0.30,
    "high_critical_share": 0.25,
    "industrial_or_commercial_share": 0.10,
}


def normalize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    min_value = values.min()
    max_value = values.max()
    if max_value == min_value:
        return pd.Series(0.0, index=series.index)
    return (values - min_value) / (max_value - min_value) * 100


def apply_district_priority_index(metrics: pd.DataFrame, combined: bool = True) -> pd.DataFrame:
    result = metrics.copy()
    result["industrial_or_commercial_share"] = result.get("industrial_or_commercial_share", 0)
    high_critical_column = "combined_high_critical_share" if "combined_high_critical_share" in result.columns else "high_critical_share"
    normalized = {
        "median_age": normalize(result["median_age"]),
        "share_50_plus": normalize(result["share_50_plus"]),
        "high_critical_share": normalize(result[high_critical_column]),
        "mbis_notice_rate": normalize(result.get("mbis_notice_rate", pd.Series(0, index=result.index))),
        "industrial_or_commercial_share": normalize(result["industrial_or_commercial_share"]),
    }
    weights = COMBINED_PRIORITY_WEIGHTS if combined else AGE_ONLY_PRIORITY_WEIGHTS
    result["priority_median_age_component"] = (weights["median_age"] * normalized["median_age"]).round(2)
    result["priority_share_50_plus_component"] = (weights["share_50_plus"] * normalized["share_50_plus"]).round(2)
    result["priority_high_critical_component"] = (weights["high_critical_share"] * normalized["high_critical_share"]).round(2)
    result["priority_usage_mix_component"] = (weights["industrial_or_commercial_share"] * normalized["industrial_or_commercial_share"]).round(2)
    if combined:
        result["priority_mbis_notice_component"] = (weights["mbis_notice_rate"] * normalized["mbis_notice_rate"]).round(2)
        score = (
            result["priority_median_age_component"]
            + result["priority_share_50_plus_component"]
            + result["priority_high_critical_component"]
            + result["priority_mbis_notice_component"]
            + result["priority_usage_mix_component"]
        )
    else:
        result["priority_mbis_notice_component"] = 0.0
        score = (
            result["priority_median_age_component"]
            + result["priority_share_50_plus_component"]
            + result["priority_high_critical_component"]
            + result["priority_usage_mix_component"]
        )
    result["district_priority_index"] = score.clip(0, 100).round(2)
    result["district_priority_mode"] = "combined_age_regulatory" if combined else "age_only"
    return result
