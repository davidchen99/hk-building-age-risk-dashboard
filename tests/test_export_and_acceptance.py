import zipfile
from pathlib import Path

from src.pipeline.acceptance_check import run_acceptance_check
from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.export_results import export_results
from src.pipeline.generate_scenario_reports import generate_scenario_reports
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import normalize_buildings
from src.utils.config import EXPORT_PACKAGE_ZIP, EXPORTS_DIR, FIGURES_DIR, REPORTS_DIR


def _build_sample_outputs() -> None:
    normalize_buildings(Path("data/sample/sample_buildings.csv"), analysis_year=2026)
    match_regulatory_notices()
    build_district_metrics()


def test_export_results_creates_delivery_artifacts():
    _build_sample_outputs()
    artifacts = export_results()
    assert artifacts["manifest"]["exists"]
    assert (EXPORTS_DIR / "district_metrics_latest.csv").exists()
    assert (EXPORTS_DIR / "data_quality_issues_latest.csv").exists()
    assert (EXPORTS_DIR / "method_summary.md").exists()
    assert (FIGURES_DIR / "age_distribution.html").exists()
    assert (FIGURES_DIR / "age_only_vs_combined_risk.html").exists()
    assert (REPORTS_DIR / "example_report.md").exists()
    assert artifacts["package"]["exists"]
    assert EXPORT_PACKAGE_ZIP.exists()
    with zipfile.ZipFile(EXPORT_PACKAGE_ZIP) as archive:
        names = set(archive.namelist())
    assert "exports/district_metrics_latest.csv" in names
    assert "figures/age_distribution.html" in names
    assert "reports/example_report.md" in names
    assert artifacts["scenario_reports"]["passed"] is True
    assert (REPORTS_DIR / "scenario_full_hong_kong.md").exists()
    assert (REPORTS_DIR / "scenario_district_yau_tsim_mong.md").exists()
    assert (REPORTS_DIR / "scenario_use_industrial.md").exists()
    assert (REPORTS_DIR / "scenario_data_quality_memo.md").exists()


def test_generate_scenario_reports_creates_final_journey_reports():
    _build_sample_outputs()
    result = generate_scenario_reports()
    assert result["passed"] is True
    assert result["scenario_count"] == 4
    assert all(item["passed"] for item in result["scenarios"])
    assert (EXPORTS_DIR / "scenario_reports_manifest.json").exists()


def test_acceptance_check_writes_json_and_markdown(tmp_path: Path):
    _build_sample_outputs()
    json_path = tmp_path / "acceptance_check.json"
    markdown_path = tmp_path / "acceptance_report.md"
    checks = run_acceptance_check(json_path, markdown_path, min_district_groups=1)
    assert checks["passed"] is True
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Dashboard Acceptance Report" in markdown_path.read_text(encoding="utf-8")
    assert "Data Quality Issues" in markdown_path.read_text(encoding="utf-8")
    assert "Dashboard Smoke" in markdown_path.read_text(encoding="utf-8")
    assert "Scenario Reports" in markdown_path.read_text(encoding="utf-8")
