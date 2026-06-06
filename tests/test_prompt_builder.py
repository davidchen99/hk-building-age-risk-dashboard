from pathlib import Path

from src.ai.prompt_builder import build_analysis_payload
from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import normalize_buildings
from src.utils.config import REGULATORY_NOTICES_PARQUET
from src.utils.io import read_parquet


def test_build_analysis_payload():
    buildings = normalize_buildings(Path("data/sample/sample_buildings.csv"), analysis_year=2026)
    match_regulatory_notices()
    metrics = build_district_metrics()
    notices = read_parquet(REGULATORY_NOTICES_PARQUET)
    payload = build_analysis_payload(buildings, metrics, notices, filters={"district_en": ["Wan Chai"]})
    assert payload["portfolio_metrics"]["total_buildings"] == len(buildings)
    assert "share_40_plus" in payload["portfolio_metrics"]
    assert "share_60_plus" in payload["portfolio_metrics"]
    assert "risk_model_breakdown" in payload
    assert "age_only_risk_distribution" in payload
    assert "combined_risk_distribution" in payload
    assert "limitations" in payload
    assert payload["model_version"]
