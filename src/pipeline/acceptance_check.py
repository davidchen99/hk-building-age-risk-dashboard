from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.pipeline.dashboard_smoke import run_dashboard_smoke
from src.pipeline.export_results import export_results
from src.utils.config import (
    BUILDINGS_PARQUET,
    DATA_QUALITY_ISSUES_PARQUET,
    DISTRICT_METRICS_PARQUET,
    EXPORT_PACKAGE_ZIP,
    EXPORTS_DIR,
    FIGURES_DIR,
    MANIFEST_PATH,
    REGULATORY_NOTICES_PARQUET,
    REPORTS_DIR,
    ensure_dirs,
    log,
)
from src.utils.io import read_parquet


def _file_status(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _status_table(statuses: dict[str, dict[str, object]]) -> list[str]:
    lines = ["| Artifact | Exists | Size bytes | Path |", "| --- | --- | --- | --- |"]
    for key, status in statuses.items():
        lines.append(f"| {key} | {status['exists']} | {status['size_bytes']} | `{status['path']}` |")
    return lines


def _artifact_rows(artifacts: dict[str, object]) -> list[str]:
    rows = ["| Kind | Exists | Size bytes | Path |", "| --- | --- | --- | --- |"]
    for group in ["tables", "figures", "reports"]:
        for item in artifacts.get(group, []):
            if isinstance(item, dict):
                rows.append(f"| {item.get('kind', group)} | {item.get('exists')} | {item.get('size_bytes')} | `{item.get('path')}` |")
    manifest = artifacts.get("manifest")
    if isinstance(manifest, dict):
        rows.append(f"| {manifest.get('kind', 'manifest')} | {manifest.get('exists')} | {manifest.get('size_bytes')} | `{manifest.get('path')}` |")
    package = artifacts.get("package")
    if isinstance(package, dict):
        rows.append(f"| {package.get('kind', 'package')} | {package.get('exists')} | {package.get('size_bytes')} | `{package.get('path')}` |")
    return rows


def _dashboard_rows(smoke: dict[str, object]) -> list[str]:
    rows = ["| Page | Passed | Exceptions | Errors |", "| --- | --- | --- | --- |"]
    for item in smoke.get("pages", []):
        if isinstance(item, dict):
            rows.append(
                f"| {item.get('page')} | {item.get('passed')} | {item.get('exception_count')} | "
                f"{'; '.join(item.get('errors', [])) or 'None'} |"
            )
    if len(rows) == 2:
        rows.append("| N/A | N/A | N/A | Dashboard smoke was not run |")
    return rows


def _scenario_rows(scenarios: dict[str, object]) -> list[str]:
    rows = ["| Scenario | Passed | Records | Notices | Artifacts | Errors |", "| --- | --- | --- | --- | --- | --- |"]
    for item in scenarios.get("scenarios", []):
        if isinstance(item, dict):
            artifact_count = len([artifact for artifact in item.get("artifacts", []) if isinstance(artifact, dict) and artifact.get("exists")])
            rows.append(
                f"| {item.get('id')} | {item.get('passed')} | {item.get('record_count')} | {item.get('notice_count')} | "
                f"{artifact_count} | {'; '.join(item.get('errors', [])) or 'None'} |"
            )
    if len(rows) == 2:
        rows.append("| N/A | N/A | N/A | N/A | N/A | Scenario reports were not generated |")
    return rows


def _render_markdown_acceptance(checks: dict[str, object]) -> str:
    lines = [
        "# Dashboard Acceptance Report",
        "",
        f"- Passed: {checks.get('passed')}",
        "",
        "## Required Files",
        "",
        *_status_table(checks.get("files", {})),
        "",
        "## Building Output",
        "",
        "```json",
        json.dumps(checks.get("buildings", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## District Metrics",
        "",
        "```json",
        json.dumps(checks.get("district_metrics", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Regulatory Notices",
        "",
        "```json",
        json.dumps(checks.get("regulatory_notices", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Data Quality Issues",
        "",
        "```json",
        json.dumps(checks.get("data_quality_issues", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Export Package",
        "",
        *_artifact_rows(checks.get("exports", {})),
        "",
        "## Dashboard Smoke",
        "",
        *_dashboard_rows(checks.get("dashboard_smoke", {})),
        "",
        "## Scenario Reports",
        "",
        *_scenario_rows(checks.get("scenario_reports", {})),
        "",
        "## Errors",
        "",
        *(f"- {item}" for item in checks.get("errors", [])),
    ]
    if not checks.get("errors"):
        lines.append("- None")
    return "\n".join(lines)


def run_acceptance_check(
    output: Path | None = None,
    markdown_output: Path | None = None,
    min_district_groups: int = 18,
    run_dashboard: bool = True,
) -> dict[str, object]:
    ensure_dirs()
    errors: list[str] = []
    exports: dict[str, object] = {}
    dashboard_smoke: dict[str, object] = {}
    if BUILDINGS_PARQUET.exists() and DISTRICT_METRICS_PARQUET.exists():
        try:
            exports = export_results()
        except Exception as exc:
            errors.append(f"export_results failed: {exc}")
        if run_dashboard:
            try:
                dashboard_smoke = run_dashboard_smoke(EXPORTS_DIR / "dashboard_smoke.json")
            except Exception as exc:
                errors.append(f"dashboard_smoke failed: {exc}")

    files = {
        "buildings": _file_status(BUILDINGS_PARQUET),
        "district_metrics": _file_status(DISTRICT_METRICS_PARQUET),
        "regulatory_notices": _file_status(REGULATORY_NOTICES_PARQUET),
        "data_quality_issues": _file_status(DATA_QUALITY_ISSUES_PARQUET),
        "manifest": _file_status(MANIFEST_PATH),
        "example_report_md": _file_status(REPORTS_DIR / "example_report.md"),
        "example_report_html": _file_status(REPORTS_DIR / "example_report.html"),
        "export_manifest": _file_status(EXPORTS_DIR / "export_manifest.json"),
        "export_package_zip": _file_status(EXPORT_PACKAGE_ZIP),
        "method_summary": _file_status(EXPORTS_DIR / "method_summary.md"),
        "district_metrics_csv": _file_status(EXPORTS_DIR / "district_metrics_latest.csv"),
        "data_quality_issues_csv": _file_status(EXPORTS_DIR / "data_quality_issues_latest.csv"),
        "age_distribution_figure": _file_status(FIGURES_DIR / "age_distribution.html"),
        "age_only_vs_combined_figure": _file_status(FIGURES_DIR / "age_only_vs_combined_risk.html"),
        "dashboard_smoke": _file_status(EXPORTS_DIR / "dashboard_smoke.json"),
        "scenario_reports_manifest": _file_status(EXPORTS_DIR / "scenario_reports_manifest.json"),
        "scenario_full_hong_kong_md": _file_status(REPORTS_DIR / "scenario_full_hong_kong.md"),
        "scenario_district_yau_tsim_mong_md": _file_status(REPORTS_DIR / "scenario_district_yau_tsim_mong.md"),
        "scenario_use_industrial_md": _file_status(REPORTS_DIR / "scenario_use_industrial.md"),
        "scenario_data_quality_memo_md": _file_status(REPORTS_DIR / "scenario_data_quality_memo.md"),
    }
    checks: dict[str, object] = {"files": files}
    checks["exports"] = exports
    checks["scenario_reports"] = exports.get("scenario_reports", {}) if isinstance(exports, dict) else {}
    checks["dashboard_smoke"] = dashboard_smoke

    if BUILDINGS_PARQUET.exists():
        buildings = read_parquet(BUILDINGS_PARQUET)
        checks["buildings"] = {
            "record_count": int(len(buildings)),
            "age_parse_rate": float(buildings["building_age"].notna().mean()) if len(buildings) else 0,
            "coordinate_valid_rate": float(buildings["has_valid_coordinate"].fillna(False).mean()) if len(buildings) else 0,
            "district_count": int(buildings["district_en"].nunique(dropna=False)),
            "risk_levels": sorted(buildings["risk_level"].dropna().unique().tolist()),
            "has_age_only_risk": {"age_only_risk_score", "age_only_risk_level"}.issubset(buildings.columns),
            "has_combined_risk": {"combined_risk_score", "combined_risk_level"}.issubset(buildings.columns),
        }
        if len(buildings) == 0:
            errors.append("buildings.parquet has no records")
        if checks["buildings"]["age_parse_rate"] < 0.90:
            errors.append("age_parse_rate below 90%")
        if checks["buildings"]["coordinate_valid_rate"] < 0.80:
            errors.append("coordinate_valid_rate below 80%")
        if not checks["buildings"]["has_age_only_risk"]:
            errors.append("age-only risk fields missing")
        if not checks["buildings"]["has_combined_risk"]:
            errors.append("combined risk fields missing")
    else:
        errors.append("buildings.parquet missing")

    if DISTRICT_METRICS_PARQUET.exists():
        metrics = read_parquet(DISTRICT_METRICS_PARQUET)
        checks["district_metrics"] = {
            "record_count": int(len(metrics)),
            "has_priority_index": "district_priority_index" in metrics.columns,
            "has_priority_components": {
                "priority_median_age_component",
                "priority_share_50_plus_component",
                "priority_high_critical_component",
                "priority_mbis_notice_component",
                "priority_usage_mix_component",
            }.issubset(metrics.columns),
            "has_age_combined_metrics": {"age_only_high_critical_share", "combined_high_critical_share"}.issubset(metrics.columns),
            "districts": sorted(metrics["district_en"].dropna().tolist()) if "district_en" in metrics.columns else [],
        }
        if len(metrics) < min_district_groups:
            errors.append(f"district_metrics has fewer than {min_district_groups} groups")
        if not checks["district_metrics"]["has_priority_components"]:
            errors.append("district priority component fields missing")
        if not checks["district_metrics"]["has_age_combined_metrics"]:
            errors.append("age-only/combined district metric fields missing")
    else:
        errors.append("district_metrics.parquet missing")

    if REGULATORY_NOTICES_PARQUET.exists():
        notices = read_parquet(REGULATORY_NOTICES_PARQUET)
        checks["regulatory_notices"] = {
            "record_count": int(len(notices)),
            "matched_count": int(notices["match_confidence"].isin(["High", "Medium"]).sum()) if "match_confidence" in notices.columns else 0,
        }
    else:
        errors.append("regulatory_notices.parquet missing")

    if DATA_QUALITY_ISSUES_PARQUET.exists():
        issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET)
        checks["data_quality_issues"] = {
            "record_count": int(len(issues)),
            "has_issue_flags": "issue_flags" in issues.columns,
        }
        if "issue_flags" not in issues.columns:
            errors.append("data_quality_issues missing issue_flags")
    else:
        errors.append("data_quality_issues.parquet missing")

    for key, status in files.items():
        if key in {"regulatory_notices"} and not status["exists"]:
            continue
        if key == "dashboard_smoke" and not run_dashboard:
            continue
        if not status["exists"]:
            errors.append(f"{key} missing")
    scenario_reports = checks.get("scenario_reports", {})
    if isinstance(scenario_reports, dict) and scenario_reports.get("passed") is False:
        errors.append(f"scenario_reports failed: {scenario_reports.get('errors', [])}")
    checks["errors"] = errors
    checks["passed"] = not errors

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(_render_markdown_acceptance(checks), encoding="utf-8")
    log(json.dumps({"acceptance_passed": checks["passed"], "errors": errors}, ensure_ascii=False))
    if errors:
        raise RuntimeError("; ".join(errors))
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/exports/acceptance_check.json")
    parser.add_argument("--markdown-output", default="outputs/exports/acceptance_report.md")
    parser.add_argument("--min-district-groups", type=int, default=18)
    parser.add_argument("--skip-dashboard-smoke", action="store_true")
    args = parser.parse_args()
    run_acceptance_check(
        Path(args.output) if args.output else None,
        Path(args.markdown_output) if args.markdown_output else None,
        min_district_groups=args.min_district_groups,
        run_dashboard=not args.skip_dashboard_smoke,
    )


if __name__ == "__main__":
    main()
