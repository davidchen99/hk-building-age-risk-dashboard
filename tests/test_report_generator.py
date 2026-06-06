from pathlib import Path

from src.ai.prompt_builder import build_analysis_payload
from src.ai.template_summary import generate_template_summary
from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import normalize_buildings
from src.reports.markdown_report import render_markdown_report
from src.utils.config import REGULATORY_NOTICES_PARQUET
from src.utils.io import read_parquet


def test_render_markdown_report():
    buildings = normalize_buildings(Path("data/sample/sample_buildings.csv"), analysis_year=2026)
    match_regulatory_notices()
    metrics = build_district_metrics()
    notices = read_parquet(REGULATORY_NOTICES_PARQUET)
    payload = build_analysis_payload(buildings, metrics, notices)
    summary = generate_template_summary(payload)
    report = render_markdown_report(payload, summary)
    assert "Core Metrics" in report
    assert "40+ share" in report
    assert "60+ share" in report
    assert "Risk Model Breakdown" in report
    assert "District Priority Components" in report
    assert "Data Scope And Source Version" in report
    assert "District Priority Ranking" in report
    assert "Regulatory Signals" in report
    assert "Method Limitations" in report
    assert "rule-based screening" in report
