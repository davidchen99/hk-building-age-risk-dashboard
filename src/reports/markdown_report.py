from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.config import REPORTS_DIR, ensure_dirs


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pct(value: Any) -> str:
    return f"{_as_float(value) * 100:.1f}%"


def _num(value: Any) -> str:
    return f"{_as_int(value):,}"


def _one_decimal(value: Any) -> str:
    return f"{_as_float(value):.1f}"


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["No records in current analysis scope."]
    rendered = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        rendered.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return rendered


def _distribution_rows(items: list[dict[str, Any]], label_key: str, max_rows: int = 10) -> list[list[str]]:
    rows = []
    for item in items[:max_rows]:
        rows.append(
            [
                str(item.get(label_key, "Unknown")),
                _num(item.get("count", 0)),
                _pct(item.get("share", 0)),
            ]
        )
    return rows


def _district_rows(items: list[dict[str, Any]], max_rows: int = 10) -> list[list[str]]:
    rows = []
    for item in items[:max_rows]:
        rows.append(
            [
                str(item.get("district_en", "Unknown")),
                _one_decimal(item.get("district_priority_index", 0)),
                _num(item.get("total_buildings", 0)),
                _one_decimal(item.get("median_age", 0)),
                _pct(item.get("share_50_plus", 0)),
                _pct(item.get("age_only_high_critical_share", 0)),
                _pct(item.get("combined_high_critical_share", item.get("high_critical_share", 0))),
                f"{_as_float(item.get('mbis_notice_rate', 0)):.2f}",
            ]
        )
    return rows


def _district_component_rows(items: list[dict[str, Any]], max_rows: int = 10) -> list[list[str]]:
    rows = []
    for item in items[:max_rows]:
        rows.append(
            [
                str(item.get("district_en", "Unknown")),
                _one_decimal(item.get("priority_median_age_component", 0)),
                _one_decimal(item.get("priority_share_50_plus_component", 0)),
                _one_decimal(item.get("priority_high_critical_component", 0)),
                _one_decimal(item.get("priority_mbis_notice_component", 0)),
                _one_decimal(item.get("priority_usage_mix_component", 0)),
                str(item.get("district_priority_mode", "")),
            ]
        )
    return rows


def _manifest_rows(manifest: dict[str, Any]) -> list[list[str]]:
    rows = []
    for key, value in manifest.items():
        if not isinstance(value, dict):
            rows.append([key, "", "", str(value)])
            continue
        rows.append(
            [
                key,
                str(value.get("record_count", value.get("district_count", value.get("notice_count", "")))),
                str(value.get("updated_at", "")),
                str(value.get("output_file", value.get("source_file", value.get("source_url", "")))),
            ]
        )
    return rows


def render_markdown_report(payload: dict[str, Any], summary: str, title: str = "Hong Kong Building Asset Age Risk Report") -> str:
    metrics = payload.get("portfolio_metrics", {})
    filters = payload.get("analysis_scope", {}).get("filters", {})
    manifest = payload.get("data_version", {})
    age_distribution = payload.get("age_distribution", [])
    age_only_risk_distribution = payload.get("age_only_risk_distribution", [])
    risk_distribution = payload.get("risk_distribution", [])
    combined_risk_distribution = payload.get("combined_risk_distribution", [])
    risk_model = payload.get("risk_model_breakdown", {})
    district_ranking = payload.get("district_ranking", [])
    usage_analysis = payload.get("usage_analysis", [])
    regulatory = payload.get("regulatory_signals", {})
    quality = payload.get("data_quality", {})
    limitations = payload.get("limitations", [])
    lines = [
        f"# {title}",
        "",
        "## Report Metadata",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Model version: {payload.get('model_version', '')}",
        f"- Prompt version: {payload.get('prompt_version', '')}",
        f"- Filters: `{filters}`",
        "",
        "## Data Scope And Source Version",
        "",
        *_markdown_table(["Source", "Records", "Updated at", "File / URL"], _manifest_rows(manifest)),
        "",
        "## Core Metrics",
        "",
        f"- Total buildings: {_num(metrics.get('total_buildings', 0))}",
        f"- Mean age: {_one_decimal(metrics.get('mean_age', 0))} years",
        f"- Median age: {_one_decimal(metrics.get('median_age', 0))} years",
        f"- 30+ share: {_pct(metrics.get('share_30_plus', 0))}",
        f"- 40+ share: {_pct(metrics.get('share_40_plus', 0))}",
        f"- 50+ share: {_pct(metrics.get('share_50_plus', 0))}",
        f"- 60+ share: {_pct(metrics.get('share_60_plus', 0))}",
        f"- High/Critical share: {_pct(metrics.get('high_critical_share', 0))}",
        "",
        "## Age Distribution",
        "",
        *_markdown_table(["Age band", "Count", "Share"], _distribution_rows(age_distribution, "age_band")),
        "",
        "## Risk Distribution",
        "",
        *_markdown_table(["Risk level", "Count", "Share"], _distribution_rows(risk_distribution, "risk_level")),
        "",
        "## Risk Model Breakdown",
        "",
        f"- Age-only mean risk score: {_one_decimal(risk_model.get('age_only_mean_risk_score', 0))}",
        f"- Combined mean risk score: {_one_decimal(risk_model.get('combined_mean_risk_score', 0))}",
        f"- Mean contextual risk score: {_one_decimal(risk_model.get('mean_contextual_risk_score', 0))}",
        f"- Age-only High/Critical share: {_pct(risk_model.get('age_only_high_critical_share', 0))}",
        f"- Combined High/Critical share: {_pct(risk_model.get('combined_high_critical_share', 0))}",
        f"- Records with matched regulatory signal: {_num(risk_model.get('records_with_regulatory_signal', 0))}",
        "",
        "### Age-Only Risk Distribution",
        "",
        *_markdown_table(["Risk level", "Count", "Share"], _distribution_rows(age_only_risk_distribution, "age_only_risk_level")),
        "",
        "### Combined Risk Distribution",
        "",
        *_markdown_table(["Risk level", "Count", "Share"], _distribution_rows(combined_risk_distribution, "combined_risk_level")),
        "",
        "## District Priority Ranking",
        "",
        *_markdown_table(
            ["District", "Priority index", "Buildings", "Median age", "50+ share", "Age-only H/C", "Combined H/C", "MBIS / 1000"],
            _district_rows(district_ranking),
        ),
        "",
        "### District Priority Components",
        "",
        *_markdown_table(
            ["District", "Median age", "50+ share", "High/Critical", "MBIS", "Usage mix", "Mode"],
            _district_component_rows(district_ranking),
        ),
        "",
        "## Use And Typology Signals",
        "",
        *_markdown_table(["Usage group", "Count", "Share"], _distribution_rows(usage_analysis, "usage_group")),
        "",
        "## Regulatory Signals",
        "",
        f"- MBIS notice records: {_num(regulatory.get('notice_count', 0))}",
        f"- Matched MBIS records: {_num(regulatory.get('matched_count', 0))}",
        "- Regulatory signals are public-record indicators and must be interpreted as prioritization context only.",
        "",
        "## Data Quality",
        "",
        f"- Age parse rate: {_pct(quality.get('age_parse_rate', 0))}",
        f"- Coordinate valid rate: {_pct(quality.get('coordinate_valid_rate', 0))}",
        f"- Invalid coordinate records: {_num(quality.get('invalid_coordinate_count', 0))}",
        f"- Unknown usage records: {_num(quality.get('unknown_usage_count', 0))}",
        f"- Unknown type records: {_num(quality.get('unknown_type_count', 0))}",
        "",
        "## AI / Template Summary",
        "",
        summary,
        "",
        "## Method Limitations",
        "",
        *[f"- {item}" for item in limitations],
    ]
    return "\n".join(lines)


def save_markdown_report(payload: dict[str, Any], summary: str, title: str = "Hong Kong Building Asset Age Risk Report") -> Path:
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"report_{timestamp}.md"
    path.write_text(render_markdown_report(payload, summary, title=title), encoding="utf-8")
    return path
