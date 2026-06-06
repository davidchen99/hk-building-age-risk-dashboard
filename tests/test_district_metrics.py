from pathlib import Path

from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import normalize_buildings


def test_build_district_metrics_from_sample():
    normalize_buildings(Path("data/sample/sample_buildings.csv"), analysis_year=2026)
    match_regulatory_notices()
    metrics = build_district_metrics()
    assert not metrics.empty
    assert "district_priority_index" in metrics.columns
    assert "age_only_high_critical_share" in metrics.columns
    assert "combined_high_critical_share" in metrics.columns
    assert "priority_median_age_component" in metrics.columns
    assert "priority_mbis_notice_component" in metrics.columns
    assert metrics["district_priority_index"].between(0, 100).all()
