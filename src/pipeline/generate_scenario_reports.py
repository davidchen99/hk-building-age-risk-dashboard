from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.ai.prompt_builder import build_analysis_payload
from src.ai.template_summary import generate_template_summary
from src.reports.html_report import render_html_report
from src.reports.markdown_report import render_markdown_report
from src.utils.config import (
    BUILDINGS_PARQUET,
    DISTRICT_METRICS_PARQUET,
    EXPORTS_DIR,
    MANIFEST_PATH,
    REGULATORY_NOTICES_PARQUET,
    REPORTS_DIR,
    ensure_dirs,
    load_manifest,
    log,
    now_iso,
)
from src.utils.io import read_parquet


SCENARIO_DEFINITIONS = [
    {
        "id": "full_hong_kong",
        "title": "Full Hong Kong Portfolio Analysis",
        "report_scope": "Full Hong Kong",
        "report_type": "Research Note",
        "filters": {},
    },
    {
        "id": "district_yau_tsim_mong",
        "title": "Yau Tsim Mong Maintenance Priority Analysis",
        "report_scope": "Single district",
        "report_type": "Maintenance Priority Brief",
        "filters": {"district_en": ["Yau Tsim Mong"]},
    },
    {
        "id": "use_industrial",
        "title": "Industrial Building Use Topic Analysis",
        "report_scope": "Use topic",
        "report_type": "Research Note",
        "filters": {"usage_group": ["Industrial"]},
    },
    {
        "id": "data_quality_memo",
        "title": "Data Quality Review Memo",
        "report_scope": "Full Hong Kong",
        "report_type": "Data Quality Memo",
        "filters": {},
    },
]


def _artifact_status(path: Path, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _load_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    missing = [path for path in [BUILDINGS_PARQUET, DISTRICT_METRICS_PARQUET] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required processed outputs: {[str(path) for path in missing]}")
    buildings = read_parquet(BUILDINGS_PARQUET)
    districts = read_parquet(DISTRICT_METRICS_PARQUET)
    notices = read_parquet(REGULATORY_NOTICES_PARQUET) if REGULATORY_NOTICES_PARQUET.exists() else pd.DataFrame()
    manifest = load_manifest() if MANIFEST_PATH.exists() else {}
    return buildings, districts, notices, manifest


def _apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    result = df.copy()
    for column, values in filters.items():
        if values and column in result.columns:
            result = result[result[column].isin(values)]
    return result


def _filter_district_metrics(metrics: pd.DataFrame, buildings: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty or buildings.empty or "district_en" not in buildings.columns:
        return pd.DataFrame()
    districts = buildings["district_en"].dropna().unique()
    return metrics[metrics["district_en"].isin(districts)].copy()


def _filter_notices(notices: pd.DataFrame, buildings: pd.DataFrame) -> pd.DataFrame:
    if notices.empty or buildings.empty or "matched_building_id" not in notices.columns:
        return pd.DataFrame(columns=notices.columns)
    building_ids = set(buildings["source_object_id"].astype(str)) if "source_object_id" in buildings.columns else set()
    if not building_ids:
        return pd.DataFrame(columns=notices.columns)
    return notices[notices["matched_building_id"].astype(str).isin(building_ids)].copy()


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _scenario_is_available(buildings: pd.DataFrame, filters: dict[str, list[str]]) -> bool:
    return not _apply_filters(buildings, filters).empty


def generate_scenario_reports() -> dict[str, Any]:
    ensure_dirs()
    buildings, districts, notices, manifest = _load_outputs()
    scenarios = []
    errors: list[str] = []
    for definition in SCENARIO_DEFINITIONS:
        scenario_id = definition["id"]
        filters = definition["filters"]
        if not _scenario_is_available(buildings, filters):
            errors.append(f"{scenario_id} has no records after filters {filters}")
            scenarios.append({"id": scenario_id, "passed": False, "errors": [errors[-1]]})
            continue
        scoped_buildings = _apply_filters(buildings, filters)
        scoped_metrics = _filter_district_metrics(districts, scoped_buildings)
        scoped_notices = _filter_notices(notices, scoped_buildings)
        payload = build_analysis_payload(scoped_buildings, scoped_metrics, scoped_notices, filters=filters, manifest=manifest)
        payload["analysis_scope"]["report_scope"] = definition["report_scope"]
        payload["analysis_scope"]["report_type"] = definition["report_type"]
        payload["analysis_scope"]["generation_method"] = "Template"
        summary = generate_template_summary(payload, language="zh")
        title = f"Hong Kong Building Asset Age Risk Report - {definition['title']}"
        md_path = REPORTS_DIR / f"scenario_{scenario_id}.md"
        html_path = REPORTS_DIR / f"scenario_{scenario_id}.html"
        payload_path = EXPORTS_DIR / f"scenario_{scenario_id}_payload.json"
        _write_text(render_markdown_report(payload, summary, title=title), md_path)
        _write_text(render_html_report(payload, summary, title=title), html_path)
        _write_json(payload, payload_path)
        scenario_errors = []
        for path in [md_path, html_path, payload_path]:
            if not path.exists() or path.stat().st_size == 0:
                scenario_errors.append(f"Missing or empty artifact: {path}")
        scenarios.append(
            {
                "id": scenario_id,
                "title": definition["title"],
                "passed": not scenario_errors,
                "record_count": int(len(scoped_buildings)),
                "notice_count": int(len(scoped_notices)),
                "filters": filters,
                "artifacts": [
                    _artifact_status(md_path, "scenario_report_md"),
                    _artifact_status(html_path, "scenario_report_html"),
                    _artifact_status(payload_path, "scenario_payload"),
                ],
                "errors": scenario_errors,
            }
        )
        errors.extend([f"{scenario_id}: {error}" for error in scenario_errors])
    result = {
        "generated_at": now_iso(),
        "passed": not errors,
        "scenario_count": len(SCENARIO_DEFINITIONS),
        "scenarios": scenarios,
        "errors": errors,
    }
    manifest_path = EXPORTS_DIR / "scenario_reports_manifest.json"
    _write_json(result, manifest_path)
    result["manifest"] = _artifact_status(manifest_path, "scenario_manifest")
    log(json.dumps({"scenario_reports_passed": result["passed"], "errors": errors}, ensure_ascii=False))
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(generate_scenario_reports(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
