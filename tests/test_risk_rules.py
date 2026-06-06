import math

import pandas as pd

from src.models.risk_rules import apply_risk_scores, risk_level, score_age


def test_score_age_boundaries():
    assert score_age(19) == 10
    assert score_age(20) == 25
    assert score_age(29) == 25
    assert score_age(30) == 45
    assert score_age(39) == 45
    assert score_age(40) == 60
    assert score_age(49) == 60
    assert score_age(50) == 75
    assert score_age(59) == 75
    assert score_age(60) == 85


def test_risk_level_boundaries():
    assert risk_level(None) == "Unknown"
    assert risk_level(math.nan) == "Unknown"
    assert risk_level(30) == "Low"
    assert risk_level(31) == "Medium"
    assert risk_level(55) == "Medium"
    assert risk_level(56) == "High"
    assert risk_level(75) == "High"
    assert risk_level(76) == "Critical"


def test_apply_risk_scores():
    df = pd.DataFrame(
        [
            {
                "building_age": 60,
                "age_band": "60+",
                "usage_group": "Industrial",
                "type_group": "Tower",
                "regulatory_signal_score": 0,
                "has_mbis_notice": False,
                "match_confidence": "Unmatched",
            }
        ]
    )
    result = apply_risk_scores(df)
    assert result.loc[0, "age_only_risk_score"] == 85
    assert result.loc[0, "age_only_risk_level"] == "Critical"
    assert result.loc[0, "contextual_risk_score"] == 20
    assert result.loc[0, "risk_score"] == 100
    assert result.loc[0, "combined_risk_score"] == 100
    assert result.loc[0, "combined_risk_level"] == "Critical"
    assert result.loc[0, "risk_level"] == "Critical"
    assert "rule-based screening" in result.loc[0, "risk_reason"]
