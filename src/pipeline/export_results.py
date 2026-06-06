from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px

from src.ai.prompt_builder import build_analysis_payload
from src.ai.template_summary import generate_template_summary
from src.models.district_index import AGE_ONLY_PRIORITY_WEIGHTS, COMBINED_PRIORITY_WEIGHTS
from src.pipeline.generate_scenario_reports import generate_scenario_reports
from src.pipeline.package_exports import create_export_package_zip
from src.reports.html_report import render_html_report
from src.reports.markdown_report import render_markdown_report
from src.utils.config import (
    BUILDINGS_PARQUET,
    DATA_QUALITY_ISSUES_PARQUET,
    DISTRICT_METRICS_PARQUET,
    EXPORTS_DIR,
    FIGURES_DIR,
    MANIFEST_PATH,
    REGULATORY_NOTICES_PARQUET,
    REPORTS_DIR,
    ensure_dirs,
    load_manifest,
    log,
    now_iso,
)
from src.utils.io import read_parquet


def _artifact_status(path: Path, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_json(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _save_figure(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
    return path


def _read_required_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    missing = [path for path in [BUILDINGS_PARQUET, DISTRICT_METRICS_PARQUET] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required processed outputs: {[str(path) for path in missing]}")
    buildings = read_parquet(BUILDINGS_PARQUET)
    districts = read_parquet(DISTRICT_METRICS_PARQUET)
    notices = read_parquet(REGULATORY_NOTICES_PARQUET) if REGULATORY_NOTICES_PARQUET.exists() else pd.DataFrame()
    quality_issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET) if DATA_QUALITY_ISSUES_PARQUET.exists() else pd.DataFrame()
    manifest = load_manifest() if MANIFEST_PATH.exists() else {}
    return buildings, districts, notices, quality_issues, manifest


def _method_summary(
    buildings: pd.DataFrame,
    districts: pd.DataFrame,
    notices: pd.DataFrame,
    quality_issues: pd.DataFrame,
    manifest: dict[str, Any],
) -> str:
    top_issue_flags: dict[str, int] = {}
    if not quality_issues.empty and "issue_flags" in quality_issues.columns:
        for flags_json in quality_issues["issue_flags"].dropna():
            try:
                flags = json.loads(str(flags_json))
            except json.JSONDecodeError:
                continue
            if isinstance(flags, list):
                for flag in flags:
                    top_issue_flags[str(flag)] = top_issue_flags.get(str(flag), 0) + 1
    quality = {
        "record_count": int(len(buildings)),
        "district_count": int(buildings["district_en"].nunique(dropna=False)) if "district_en" in buildings else 0,
        "age_parse_rate": float(buildings["building_age"].notna().mean()) if len(buildings) and "building_age" in buildings else 0,
        "coordinate_valid_rate": float(buildings["has_valid_coordinate"].fillna(False).mean())
        if len(buildings) and "has_valid_coordinate" in buildings
        else 0,
        "district_metric_rows": int(len(districts)),
        "regulatory_notice_rows": int(len(notices)),
        "data_quality_issue_rows": int(len(quality_issues)),
        "top_issue_flags": dict(sorted(top_issue_flags.items(), key=lambda item: item[1], reverse=True)[:10]),
    }
    risk_model_snapshot = {
        "age_only_mean_risk_score": float(pd.to_numeric(buildings.get("age_only_risk_score", pd.Series(dtype=float)), errors="coerce").mean())
        if "age_only_risk_score" in buildings
        else 0,
        "combined_mean_risk_score": float(pd.to_numeric(buildings.get("combined_risk_score", buildings.get("risk_score", pd.Series(dtype=float))), errors="coerce").mean())
        if "risk_score" in buildings
        else 0,
        "age_only_high_critical_share": float(buildings["age_only_risk_level"].isin(["High", "Critical"]).mean()) if "age_only_risk_level" in buildings and len(buildings) else 0,
        "combined_high_critical_share": float(buildings["combined_risk_level"].isin(["High", "Critical"]).mean()) if "combined_risk_level" in buildings and len(buildings) else 0,
        "priority_weights_combined": COMBINED_PRIORITY_WEIGHTS,
        "priority_weights_age_only": AGE_ONLY_PRIORITY_WEIGHTS,
    }
    return "\n".join(
        [
            "# Method And Export Summary",
            "",
            f"- Generated at: {now_iso()}",
            "- Product: HK Building Asset Age Risk Dashboard v1.0",
            "- Interpretation: rule-based public-data screening, not structural inspection.",
            "",
            "## Data Quality Snapshot",
            "",
            "```json",
            json.dumps(quality, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Risk Model Snapshot",
            "",
            "```json",
            json.dumps(risk_model_snapshot, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Source Manifest",
            "",
            "```json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Core Method",
            "",
            "- Normalize official or compatible building records into a stable building schema.",
            "- Parse occupation permit date/year and derive building age bands.",
            "- Apply rule-based risk scoring from age, usage, type, data quality, and regulatory signals.",
            "- Match MBIS notices to buildings by exact normalized address and spatial proximity.",
            "- Aggregate district-level indicators and compute a priority index for screening.",
            "- Generate template or LLM-assisted summaries from structured aggregate payloads only.",
        ]
    )


def _write_example_reports(buildings: pd.DataFrame, districts: pd.DataFrame, notices: pd.DataFrame, manifest: dict[str, Any]) -> list[Path]:
    payload = build_analysis_payload(buildings, districts, notices, manifest=manifest)
    summary = generate_template_summary(payload, language="zh")
    title = "Hong Kong Building Asset Age Risk Report - Example"
    md_path = REPORTS_DIR / "example_report.md"
    html_path = REPORTS_DIR / "example_report.html"
    _write_text(render_markdown_report(payload, summary, title=title), md_path)
    _write_text(render_html_report(payload, summary, title=title), html_path)
    return [md_path, html_path]


def _write_tables(
    buildings: pd.DataFrame,
    districts: pd.DataFrame,
    notices: pd.DataFrame,
    quality_issues: pd.DataFrame,
    manifest: dict[str, Any],
) -> list[Path]:
    paths = [
        _write_csv(buildings, EXPORTS_DIR / "buildings_latest.csv"),
        _write_csv(districts.sort_values("district_priority_index", ascending=False), EXPORTS_DIR / "district_metrics_latest.csv"),
        _write_csv(notices, EXPORTS_DIR / "regulatory_notices_latest.csv"),
        _write_csv(quality_issues, EXPORTS_DIR / "data_quality_issues_latest.csv"),
        _write_json(manifest, EXPORTS_DIR / "source_manifest_snapshot.json"),
    ]
    if not buildings.empty and {"usage_group", "age_band"}.issubset(buildings.columns):
        paths.append(_write_csv(pd.crosstab(buildings["usage_group"], buildings["age_band"]).reset_index(), EXPORTS_DIR / "usage_age_cross_table.csv"))
    if not buildings.empty and {"age_band", "risk_level"}.issubset(buildings.columns):
        paths.append(_write_csv(pd.crosstab(buildings["age_band"], buildings["risk_level"]).reset_index(), EXPORTS_DIR / "age_risk_cross_table.csv"))
    paths.append(_write_text(_method_summary(buildings, districts, notices, quality_issues, manifest), EXPORTS_DIR / "method_summary.md"))
    return paths


def _write_figures(buildings: pd.DataFrame, districts: pd.DataFrame) -> list[Path]:
    paths: list[Path] = []
    if not buildings.empty and "age_band" in buildings:
        paths.append(_save_figure(px.histogram(buildings, x="age_band", title="Age Band Distribution"), FIGURES_DIR / "age_distribution.html"))
    if not buildings.empty and "risk_level" in buildings:
        risk_counts = buildings["risk_level"].fillna("Unknown").value_counts().reset_index()
        risk_counts.columns = ["risk_level", "count"]
        paths.append(_save_figure(px.bar(risk_counts, x="risk_level", y="count", title="Risk Level Distribution"), FIGURES_DIR / "risk_distribution.html"))
    if not buildings.empty and {"age_only_risk_level", "combined_risk_level"}.issubset(buildings.columns):
        comparison = pd.concat(
            [
                buildings["age_only_risk_level"].fillna("Unknown").value_counts().rename_axis("risk_level").reset_index(name="count").assign(model="Age-only"),
                buildings["combined_risk_level"].fillna("Unknown").value_counts().rename_axis("risk_level").reset_index(name="count").assign(model="Combined"),
            ],
            ignore_index=True,
        )
        paths.append(_save_figure(px.bar(comparison, x="risk_level", y="count", color="model", barmode="group", title="Age-only vs Combined Risk"), FIGURES_DIR / "age_only_vs_combined_risk.html"))
    if not districts.empty and {"district_en", "district_priority_index"}.issubset(districts.columns):
        top_priority = districts.sort_values("district_priority_index", ascending=False).head(15)
        paths.append(
            _save_figure(
                px.bar(top_priority, x="district_priority_index", y="district_en", orientation="h", title="Top District Priority Index"),
                FIGURES_DIR / "district_priority_index_top15.html",
            )
        )
    if not districts.empty and {"district_en", "mbis_notice_rate"}.issubset(districts.columns):
        top_mbis = districts.sort_values("mbis_notice_rate", ascending=False).head(15)
        paths.append(
            _save_figure(
                px.bar(top_mbis, x="mbis_notice_rate", y="district_en", orientation="h", title="Top MBIS Notice Rate"),
                FIGURES_DIR / "mbis_notice_rate_top15.html",
            )
        )
    if not buildings.empty and {"district_en", "usage_group"}.issubset(buildings.columns):
        heat = pd.crosstab(buildings["district_en"], buildings["usage_group"])
        paths.append(_save_figure(px.imshow(heat, aspect="auto", title="District x Usage Heatmap"), FIGURES_DIR / "district_usage_heatmap.html"))
    return paths


def export_results() -> dict[str, Any]:
    ensure_dirs()
    buildings, districts, notices, quality_issues, manifest = _read_required_outputs()
    table_paths = _write_tables(buildings, districts, notices, quality_issues, manifest)
    figure_paths = _write_figures(buildings, districts)
    report_paths = _write_example_reports(buildings, districts, notices, manifest)
    scenario_reports = generate_scenario_reports()
    artifacts = {
        "generated_at": now_iso(),
        "tables": [_artifact_status(path, "table") for path in table_paths],
        "figures": [_artifact_status(path, "figure") for path in figure_paths],
        "reports": [_artifact_status(path, "report") for path in report_paths],
        "scenario_reports": scenario_reports,
    }
    manifest_path = EXPORTS_DIR / "export_manifest.json"
    _write_json(artifacts, manifest_path)
    artifacts["manifest"] = _artifact_status(manifest_path, "manifest")
    package_path = create_export_package_zip()
    artifacts["package"] = _artifact_status(package_path, "package")
    _write_json(artifacts, manifest_path)
    log(f"Export package ready: {manifest_path}")
    return artifacts


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(export_results(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
