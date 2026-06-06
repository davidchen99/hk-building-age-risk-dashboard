from __future__ import annotations

import json
from html import escape
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.element import Element
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from src.ai.llm_client import generate_llm_summary, test_llm_connection
from src.ai.llm_settings import connection_status, load_llm_settings, masked_key, provider_defaults, save_llm_settings
from src.ai.prompt_builder import build_analysis_payload
from src.ai.template_summary import generate_template_summary
from src.ai.validate_summary import validate_summary_text
from src.dashboard.data import apply_filters, load_dashboard_data
from src.pipeline.build_all import build_all
from src.pipeline.build_district_metrics import build_district_metrics
from src.pipeline.build_risk_scores import build_risk_scores
from src.pipeline.export_results import export_results
from src.pipeline.match_regulatory_notices import match_regulatory_notices
from src.pipeline.normalize_buildings import COMPATIBLE_ALIASES, normalize_buildings
from src.reports.html_report import save_html_report
from src.reports.markdown_report import save_markdown_report
from src.utils.config import (
    BUILDINGS_PARQUET,
    CACHE_DIR,
    DATA_QUALITY_ISSUES_PARQUET,
    DISTRICT_METRICS_PARQUET,
    EXPORTS_DIR,
    EXPORT_PACKAGE_ZIP,
    MANIFEST_PATH,
    RAW_DIR,
    REGULATORY_NOTICES_PARQUET,
    REPORTS_DIR,
    log,
)
from src.utils.io import read_parquet

st.set_page_config(
    page_title="HK Building Asset Age Risk Dashboard",
    page_icon="🏙️",
    layout="wide",
)

RISK_COLORS = {
    "Low": "#2ca25f",
    "Medium": "#f1c40f",
    "High": "#e67e22",
    "Critical": "#c0392b",
    "Unknown": "#7f8c8d",
}

DISTRICT_LAYER_METRICS = {
    "district_priority_index": "Priority index",
    "median_age": "Median age",
    "share_50_plus": "50+ share",
    "mbis_notice_rate": "MBIS notices per 1,000 buildings",
}

BUILDING_PREVIEW_COLUMNS = [
    "source_object_id",
    "address_en",
    "district_en",
    "usage_group",
    "type_group",
    "building_age",
    "age_band",
    "risk_level",
    "risk_score",
    "has_mbis_notice",
    "match_confidence",
]

DISTRICT_RANKING_COLUMNS = [
    "district_en",
    "total_buildings",
    "median_age",
    "share_50_plus",
    "combined_high_critical_share",
    "mbis_notice_rate",
    "data_quality_score",
    "district_priority_index",
]

NOTICE_PREVIEW_COLUMNS = [
    "notice_name_en",
    "address_en",
    "notice_count",
    "match_confidence",
    "match_method",
    "match_distance_m",
    "last_update",
    "notice_ref",
]

QUALITY_PREVIEW_COLUMNS = [
    "source_object_id",
    "address_en",
    "district_en",
    "usage_group",
    "occupation_permit_year",
    "issue_flags",
    "issue_count",
]

PAGE_OPTIONS = [
    "Home / Start",
    "Data Intake",
    "Portfolio Overview",
    "Spatial Dashboard",
    "District Benchmark",
    "Use & Typology",
    "Regulatory Signals",
    "AI Report Studio",
    "Admin / Settings",
    "Method & QA",
]

PAGE_INTROS = {
    "Home / Start": {
        "en": ("Start from the current data status and the most common research tasks.", "Use this page to decide whether the dataset is ready and where to go next."),
        "zh": ("从当前数据状态和常用研究任务开始。", "先判断数据是否可用，再进入全港、单区、用途、监管或报告流程。"),
    },
    "Data Intake": {
        "en": ("Check whether the current dataset is usable before analysis.", "Business health metrics stay visible; source manifest and raw previews stay in expandable sections."),
        "zh": ("分析前先确认当前数据是否可用。", "默认展示业务化数据健康指标，source manifest 和原始预览放在展开区。"),
    },
    "Portfolio Overview": {
        "en": ("Understand the portfolio-wide age and risk structure.", "Use this page for the first all-Hong-Kong or filtered-scope readout."),
        "zh": ("理解建筑组合整体楼龄和风险结构。", "适合做全港或当前筛选范围的第一层概览。"),
    },
    "Spatial Dashboard": {
        "en": ("Locate where ageing pressure and regulatory signals concentrate.", "Start with the district layer, then enable point layers only when needed."),
        "zh": ("定位老化压力和监管信号集中在哪里。", "先看区域图层，需要单栋资产时再开启点位图层。"),
    },
    "District Benchmark": {
        "en": ("Compare districts by ageing, regulatory signals, and priority index.", "Use the ranking to choose a district for closer review."),
        "zh": ("按老化、监管信号和优先级指数比较区域。", "用排名选择后续需要重点查看的区域。"),
    },
    "Use & Typology": {
        "en": ("Compare ageing and risk patterns by use and building type.", "Use this page for industrial, residential, composite, and typology-specific questions."),
        "zh": ("按用途和建筑类型比较老化与风险模式。", "适合回答工业、住宅、综合用途或类型专题问题。"),
    },
    "Regulatory Signals": {
        "en": ("Review MBIS notices as public regulatory signals.", "These records support screening and prioritisation, not structural defect conclusions."),
        "zh": ("把 MBIS 通知作为公开监管信号审查。", "这些记录用于筛查和优先级判断，不等同于结构缺陷结论。"),
    },
    "AI Report Studio": {
        "en": ("Turn the current analysis scope into a research-ready report.", "Confirm scope, model version, prompt version, and generation method before exporting."),
        "zh": ("把当前分析范围转成可导出的研究报告。", "导出前确认范围、模型版本、prompt 版本和生成方式。"),
    },
    "Admin / Settings": {
        "en": ("Configure generation providers without exposing API keys.", "Template mode works without a key; DeepSeek, OpenAI, and Local can be tested here."),
        "zh": ("配置生成服务，同时避免暴露 API Key。", "Template 无需 Key；DeepSeek、OpenAI 和 Local 可在这里测试。"),
    },
    "Method & QA": {
        "en": ("Audit the method, data quality, and reproducibility package.", "Use this page before sharing outputs with a supervisor or research team."),
        "zh": ("审查方法、数据质量和可复现交付包。", "对导师或研究团队分享前，先用本页做最终检查。"),
    },
}

TRANSLATIONS = {
    "en": {
        "app_title": "Hong Kong Building Asset Age Risk Dashboard",
        "app_caption": "v1.0 local-first research dashboard. Rule-based screening only.",
        "sidebar_title": "HK Building Assets",
        "screening_caption": "Rule-based screening, not structural inspection.",
        "language": "Language",
        "page": "Page",
        "reset_filters": "Reset filters",
        "refresh_cache": "Refresh data cache",
    },
    "zh": {
        "app_title": "香港建筑资产年龄风险 Dashboard",
        "app_caption": "v1.0 本地优先研究型 dashboard。仅作为规则化筛查工具。",
        "sidebar_title": "香港建筑资产",
        "screening_caption": "规则化筛查，不是结构安全鉴定。",
        "language": "语言",
        "page": "页面",
        "reset_filters": "重置筛选",
        "refresh_cache": "刷新数据缓存",
        "District": "区域",
        "Territory": "地域",
        "Usage": "用途",
        "Type": "类型",
        "Age band": "楼龄分段",
        "Risk level": "风险等级",
        "Home / Start": "首页 / 开始",
        "Data Intake": "数据接入",
        "Portfolio Overview": "组合概览",
        "Spatial Dashboard": "空间看板",
        "District Benchmark": "区域对标",
        "Use & Typology": "用途与类型",
        "Regulatory Signals": "监管信号",
        "AI Report Studio": "AI 报告工作台",
        "Admin / Settings": "管理员 / 设置",
        "Method & QA": "方法与质检",
        "Data Mode": "数据模式",
        "Building Records": "建筑记录",
        "Filtered Records": "筛选记录",
        "MBIS Notices": "MBIS 通知",
        "Quality Issues": "质量问题",
        "Age Parse Rate": "楼龄解析率",
        "Coordinate Valid Rate": "坐标有效率",
        "MBIS Match Rate": "MBIS 匹配率",
        "Data Updated": "数据更新时间",
        "Start With A Task": "从任务开始",
        "Available Deliverables": "可用交付物",
        "Current Filter Summary": "当前筛选摘要",
        "Download export package ZIP": "下载完整导出包 ZIP",
        "Official cache": "官方缓存",
        "Uploaded data": "用户上传数据",
        "Sample fallback": "样例回退数据",
        "Processed data": "已处理数据",
        "No processed data": "无处理后数据",
        "Map points are screening indicators, not structural inspection results.": "地图点位是筛查信号，不是结构安全鉴定结果。",
        "No valid coordinates in current filter scope.": "当前筛选范围内没有可用于地图的有效坐标。",
        "Map Layers & Display": "地图图层与展示",
        "Map display answers where ageing and regulatory signals concentrate; layers can be switched without changing the underlying data.": "地图用于回答老化与监管信号集中在哪里；切换图层不会改变底层数据。",
        "District choropleth": "区域分级着色",
        "Building points": "建筑点位",
        "MBIS notice layer": "MBIS 通知图层",
        "District layer metric": "区域图层指标",
        "Building point cap": "建筑点位上限",
        "MBIS point cap": "MBIS 点位上限",
        "Layer Display Status": "图层展示状态",
        "Layer": "图层",
        "Status": "状态",
        "Records": "记录",
        "Notes": "说明",
        "On": "开启",
        "Off": "关闭",
        "District layer": "区域图层",
        "Building point layer": "建筑点位图层",
        "Filtered scope": "当前筛选范围",
        "Clustered sample": "聚合抽样",
        "Full filtered set": "完整筛选集合",
        "Not shown": "未展示",
        "Enable the layer to inspect individual assets after narrowing filters.": "缩小筛选后可开启该图层查看单栋资产。",
        "Point cap reached; showing a deterministic sample for performance.": "点位超过上限，为保证性能展示固定抽样。",
        "Scoped to buildings in the current filter.": "已按当前筛选范围内建筑关联。",
        "No mappable layer is enabled. Turn on a layer to inspect spatial patterns.": "当前没有开启可展示图层；开启至少一个图层后查看空间分布。",
        "Map display mode": "地图展示模式",
        "District choropleth first; point layers are optional for performance.": "默认优先区域图层；点位图层按需开启以保证性能。",
        "Map Legend": "地图图例",
        "Priority index": "优先级指数",
        "Median age": "中位楼龄",
        "50+ share": "50 年以上占比",
        "MBIS notices per 1,000 buildings": "每千栋 MBIS 通知数",
        "District priority index": "区域优先级指数",
        "MBIS notice": "MBIS 通知",
        "Status Snapshot": "状态快照",
        "Data readiness": "数据可用性",
        "Analysis risk pressure": "分析风险压力",
        "Regulatory coverage": "监管信号覆盖",
        "Ready": "可用",
        "Review": "需复核",
        "Attention": "需关注",
        "Low pressure": "压力较低",
        "Moderate pressure": "中等压力",
        "High pressure": "高压力",
        "Strong match": "匹配较强",
        "Partial match": "部分匹配",
        "Weak match": "匹配较弱",
        "Data Health Summary": "数据健康摘要",
        "Default Building Preview": "默认建筑预览",
        "Advanced building fields": "高级建筑字段",
        "Default District Ranking": "默认区域排名",
        "Advanced district metrics": "高级区域指标",
        "Default Notice Preview": "默认监管通知预览",
        "Advanced notice fields": "高级监管字段",
        "Default Quality Issue Preview": "默认质量问题预览",
        "Advanced quality issue fields": "高级质量问题字段",
        "Chart note: Age bands show building age from occupation permit dates; unknown ages remain in data quality review.": "图表说明：楼龄分段基于入伙纸日期计算；无法解析楼龄的记录进入数据质量审查。",
        "Chart note: Usage groups are normalised from public building records and support topic screening.": "图表说明：用途分类由公开建筑记录标准化得到，用于专题筛查。",
        "Chart note: Risk levels are rule-based screening categories, not engineering inspection results.": "图表说明：风险等级是规则化筛查分类，不是工程检测结论。",
        "Chart note: Combined risk adds usage, type, and matched regulatory signal to the age-only baseline.": "图表说明：综合风险在楼龄基线外加入用途、类型和匹配监管信号。",
        "Chart note: District priority index combines age structure, high/critical share, MBIS signal, use mix, and data quality.": "图表说明：区域优先级指数综合楼龄结构、高/重点关注占比、MBIS 信号、用途结构和数据质量。",
        "Chart note: The heatmap counts buildings by district and use group within the current filter.": "图表说明：热力图统计当前筛选范围内各区域和用途组合的建筑数量。",
        "Chart note: Type and age bands help identify typology-specific ageing pressure.": "图表说明：类型和楼龄分段用于识别特定建筑类型的老化压力。",
        "Chart note: Matching confidence indicates how reliably MBIS notices can be associated with building records.": "图表说明：匹配置信度表示 MBIS 通知与建筑记录关联的可靠程度。",
        "Chart note: MBIS notice rate is a regulatory signal density per 1,000 buildings, not a defect rate.": "图表说明：MBIS 通知率是每千栋建筑的监管信号密度，不是缺陷率。",
        "Full Hong Kong Portfolio": "全港组合概览",
        "Single District Priority": "单区维护优先级",
        "Use Topic Analysis": "用途专题分析",
        "Spatial Risk Review": "空间风险审查",
        "Regulatory Signal Review": "监管信号审查",
        "Generate Research Report": "生成研究报告",
        "Review portfolio age, usage, and risk structure.": "查看组合楼龄、用途和风险结构。",
        "Compare district priority index and maintenance signals.": "比较区域优先级指数和维护信号。",
        "Inspect ageing pressure by building use and type.": "按用途和类型查看老化压力。",
        "Explore district layer, building points, and MBIS notices.": "查看区域图层、建筑点位和 MBIS 通知。",
        "Check MBIS notice density and matching confidence.": "检查 MBIS 通知密度和匹配置信度。",
        "Create a template or LLM-assisted report for export.": "生成模板或 LLM 辅助报告并导出。",
        "Open": "打开",
        "Total Buildings": "建筑总数",
        "Median Age": "中位楼龄",
        "30+ Share": "30 年以上占比",
        "40+ Share": "40 年以上占比",
        "50+ Share": "50 年以上占比",
        "60+ Share": "60 年以上占比",
        "High/Critical": "高/重点关注",
        "Data Quality": "数据质量",
        "Age Band Distribution": "楼龄分段分布",
        "Usage Distribution": "用途分布",
        "Risk Level Distribution": "风险等级分布",
        "Age-only vs Combined Risk": "楼龄基线与综合风险对比",
        "Top District Priority Index": "区域优先级指数 Top",
        "Usage x Risk": "用途 x 风险",
        "District x Usage Heatmap": "区域 x 用途热力图",
        "Type x Age Band": "类型 x 楼龄分段",
        "Matching Confidence": "匹配置信度",
        "MBIS Notice Rate by District": "各区域 MBIS 通知率",
        "Notice records": "通知记录",
        "Matched records": "已匹配记录",
        "High confidence": "高置信匹配",
        "Download district metrics CSV": "下载区域指标 CSV",
        "Download regulatory notices CSV": "下载监管通知 CSV",
        "Download usage-age cross table": "下载用途-楼龄交叉表",
        "Report scope": "报告范围",
        "Report type": "报告类型",
        "Generation": "生成方式",
        "Full Hong Kong": "全港",
        "Current filters": "当前筛选",
        "Single district": "单一区域",
        "Use topic": "用途专题",
        "Executive Summary": "执行摘要",
        "Research Note": "研究札记",
        "Maintenance Priority Brief": "维护优先级简报",
        "Data Quality Memo": "数据质量备忘录",
        "Total": "总数",
        "Generate summary": "生成摘要",
        "Export Markdown": "导出 Markdown",
        "Export HTML": "导出 HTML",
        "Files": "文件",
        "Risk Rule": "风险规则",
        "Data Source Manifest": "数据源 Manifest",
        "Quality Snapshot": "质量快照",
        "District Priority Components": "区域优先级组成",
        "Download method summary": "下载方法摘要",
        "Download current filtered buildings CSV": "下载当前筛选建筑 CSV",
        "Download data quality issues CSV": "下载数据质量问题 CSV",
        "Generate full export package": "生成完整导出包",
    }
}


@st.cache_data(show_spinner=False)
def cached_data():
    return load_dashboard_data()


def current_language() -> str:
    return "zh" if st.session_state.get("ui_language") == "中文" else "en"


def tr(text: str) -> str:
    return TRANSLATIONS.get(current_language(), {}).get(text, text)


def page_label(page: str) -> str:
    return tr(page)


def apply_visual_system() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.35rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.7rem 0.85rem;
        }
        div[data-testid="stMetric"] label {
            color: #4b5563;
            font-size: 0.78rem;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #111827;
        }
        .scope-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.2rem 0 1rem;
            padding-bottom: 0.85rem;
            border-bottom: 1px solid #e5e7eb;
        }
        .scope-chip {
            display: inline-flex;
            align-items: baseline;
            gap: 0.35rem;
            border: 1px solid #d1d5db;
            background: #f9fafb;
            border-radius: 999px;
            padding: 0.28rem 0.62rem;
            color: #111827;
            font-size: 0.78rem;
            max-width: 100%;
        }
        .scope-chip strong {
            color: #374151;
            font-weight: 700;
            white-space: nowrap;
        }
        .scope-chip span {
            overflow-wrap: anywhere;
        }
        .page-intro {
            border-left: 3px solid #2563eb;
            background: #f8fafc;
            border-radius: 6px;
            padding: 0.7rem 0.85rem;
            margin: 0.35rem 0 1rem;
            color: #1f2937;
        }
        .page-intro strong {
            display: block;
            margin-bottom: 0.2rem;
            color: #111827;
        }
        .page-intro span {
            color: #4b5563;
        }
        .status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.25rem 0 1rem;
        }
        .status-tag {
            border: 1px solid #d1d5db;
            border-radius: 999px;
            padding: 0.34rem 0.72rem;
            background: #f9fafb;
            color: #111827;
            font-size: 0.8rem;
            line-height: 1.2;
        }
        .status-tag strong {
            color: #374151;
            margin-right: 0.3rem;
        }
        .status-ok {
            background: #f0fdf4;
            border-color: #86efac;
        }
        .status-warn {
            background: #fffbeb;
            border-color: #fcd34d;
        }
        .status-danger {
            background: #fef2f2;
            border-color: #fca5a5;
        }
        .status-neutral {
            background: #f8fafc;
            border-color: #cbd5e1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_intro(page: str) -> None:
    intro = PAGE_INTROS.get(page, {}).get(current_language())
    if not intro:
        return
    title, body = intro
    st.markdown(
        f"<div class='page-intro'><strong>{escape(title)}</strong><span>{escape(body)}</span></div>",
        unsafe_allow_html=True,
    )


def render_status_tags(title: str, tags: list[tuple[str, str, str]]) -> None:
    if not tags:
        return
    st.subheader(tr(title))
    tag_html = "".join(
        f"<div class='status-tag status-{escape(tone)}'><strong>{escape(tr(label))}</strong>{escape(tr(value))}</div>"
        for label, value, tone in tags
    )
    st.markdown(f"<div class='status-strip'>{tag_html}</div>", unsafe_allow_html=True)


def chart_note(text: str) -> None:
    st.caption(tr(text))


def available_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in df.columns]


def default_table(df: pd.DataFrame, columns: list[str], *, rows: int | None = None) -> pd.DataFrame:
    visible = df[available_columns(df, columns)].copy()
    if rows is not None:
        visible = visible.head(rows)
    return visible


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes} B"


def clean_display_value(value, default: str = "N/A", limit: int | None = None) -> str:
    try:
        missing = bool(pd.isna(value))
    except (TypeError, ValueError):
        missing = False
    if missing:
        return default
    text = str(value).replace("\n", " ").strip()
    if not text:
        return default
    if limit and len(text) > limit:
        text = f"{text[: limit - 3]}..."
    return text


def as_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def district_metric_label(metric: str) -> str:
    return tr(DISTRICT_LAYER_METRICS.get(metric, metric))


def district_metric_display(metric: str, value: float) -> str:
    numeric = as_float(value)
    if metric == "share_50_plus":
        return pct(numeric)
    if metric == "mbis_notice_rate":
        return f"{numeric:.1f}/1000"
    if metric == "median_age":
        return f"{numeric:.1f} years"
    return f"{numeric:.1f}"


def district_metric_color(metric: str, value: float) -> str:
    numeric = as_float(value)
    if metric == "median_age":
        if numeric >= 45:
            return "#b2182b"
        if numeric >= 38:
            return "#ef8a62"
        if numeric >= 30:
            return "#fddbc7"
        return "#d1e5f0"
    if metric == "share_50_plus":
        if numeric >= 0.4:
            return "#b2182b"
        if numeric >= 0.3:
            return "#ef8a62"
        if numeric >= 0.15:
            return "#fddbc7"
        return "#d1e5f0"
    if metric == "mbis_notice_rate":
        if numeric >= 90:
            return "#b2182b"
        if numeric >= 60:
            return "#ef8a62"
        if numeric >= 30:
            return "#fddbc7"
        return "#d1e5f0"
    if numeric >= 75:
        return "#b2182b"
    if numeric >= 50:
        return "#ef8a62"
    if numeric >= 25:
        return "#fddbc7"
    return "#d1e5f0"


def district_metric_legend(metric: str) -> dict[str, str]:
    if metric == "median_age":
        return {
            "Median age 45+": "#b2182b",
            "Median age 38-44": "#ef8a62",
            "Median age 30-37": "#fddbc7",
            "Median age <30": "#d1e5f0",
        }
    if metric == "share_50_plus":
        return {
            "50+ share 40%+": "#b2182b",
            "50+ share 30-39%": "#ef8a62",
            "50+ share 15-29%": "#fddbc7",
            "50+ share <15%": "#d1e5f0",
        }
    if metric == "mbis_notice_rate":
        return {
            "MBIS 90+/1000": "#b2182b",
            "MBIS 60-89/1000": "#ef8a62",
            "MBIS 30-59/1000": "#fddbc7",
            "MBIS <30/1000": "#d1e5f0",
        }
    return {
        "Priority 75+": "#b2182b",
        "Priority 50-74": "#ef8a62",
        "Priority 25-49": "#fddbc7",
        "Priority <25": "#d1e5f0",
    }


def scoped_notices_for_buildings(notices: pd.DataFrame, buildings: pd.DataFrame) -> pd.DataFrame:
    if notices is None or notices.empty:
        return pd.DataFrame()
    notice_valid = notices.dropna(subset=["latitude", "longitude"]).copy()
    if notice_valid.empty:
        return notice_valid
    if buildings.empty or "matched_building_id" not in notice_valid.columns or "source_object_id" not in buildings.columns:
        return notice_valid
    building_ids = set(buildings["source_object_id"].dropna().astype(str))
    if not building_ids:
        return notice_valid.iloc[0:0].copy()
    matched_ids = notice_valid["matched_building_id"].astype("string")
    return notice_valid[matched_ids.isin(building_ids)].copy()


def building_tooltip(row: pd.Series) -> folium.Tooltip:
    address = escape(clean_display_value(row.get("address_en"), limit=120))
    district = escape(clean_display_value(row.get("district_en")))
    usage = escape(clean_display_value(row.get("usage_group")))
    building_type = escape(clean_display_value(row.get("type_group")))
    age_value = clean_display_value(row.get("building_age"))
    age = escape(f"{age_value} years" if age_value != "N/A" else age_value)
    risk = escape(clean_display_value(row.get("risk_level")))
    reason = escape(clean_display_value(row.get("risk_reason"), limit=180))
    confidence = clean_display_value(row.get("match_confidence"), default="Unmatched")
    mbis_status = "Matched" if bool(row.get("has_mbis_notice", False)) else confidence
    mbis_status = escape(mbis_status)
    html = (
        "<div style='min-width:260px;max-width:340px;font-size:12px;line-height:1.35;color:#111827;'>"
        f"<div style='font-weight:700;margin-bottom:6px;'>{address}</div>"
        "<table style='width:100%;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;'>District</td><td>{district}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Usage</td><td>{usage}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Type</td><td>{building_type}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Building age</td><td>{age}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Risk level</td><td>{risk}</td></tr>"
        f"<tr><td style='color:#6b7280;'>MBIS matched</td><td>{mbis_status}</td></tr>"
        "</table>"
        f"<div style='margin-top:6px;color:#374151;'>{reason}</div>"
        "</div>"
    )
    return folium.Tooltip(html, sticky=True)


def notice_tooltip(row: pd.Series) -> folium.Tooltip:
    address = escape(clean_display_value(row.get("address_en"), limit=130))
    confidence = escape(clean_display_value(row.get("match_confidence"), default="Unmatched"))
    method = escape(clean_display_value(row.get("match_method")))
    ref = escape(clean_display_value(row.get("notice_ref")))
    count = escape(clean_display_value(row.get("notice_count"), default="1"))
    html = (
        "<div style='min-width:240px;max-width:320px;font-size:12px;line-height:1.35;color:#111827;'>"
        f"<div style='font-weight:700;margin-bottom:6px;'>{address}</div>"
        "<table style='width:100%;border-collapse:collapse;'>"
        f"<tr><td style='color:#6b7280;'>Notice count</td><td>{count}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Confidence</td><td>{confidence}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Method</td><td>{method}</td></tr>"
        f"<tr><td style='color:#6b7280;'>Ref</td><td>{ref}</td></tr>"
        "</table>"
        "<div style='margin-top:6px;color:#374151;'>Regulatory record, not a structural defect conclusion.</div>"
        "</div>"
    )
    return folium.Tooltip(html, sticky=True)


def set_page(page: str) -> None:
    st.session_state["page_selector"] = page


def data_mode_label(manifest: dict) -> str:
    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    source_file = str(processed.get("source_file", "")).lower()
    if "uploaded_buildings" in source_file:
        return "Uploaded data"
    if "sample" in source_file:
        return "Sample fallback"
    if "bdbiar" in source_file or "building information and age records" in json.dumps(processed.get("source_manifest", {}), ensure_ascii=False).lower():
        return "Official cache"
    if source_file:
        return "Processed data"
    return "No processed data"


def quality_issue_count(manifest: dict) -> int:
    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    if "data_quality_issue_count" in processed:
        return int(processed.get("data_quality_issue_count") or 0)
    if DATA_QUALITY_ISSUES_PARQUET.exists():
        return len(read_parquet(DATA_QUALITY_ISSUES_PARQUET))
    return 0


def mbis_match_rate(notices: pd.DataFrame, manifest: dict) -> float:
    matching = manifest.get("mbis_matching", {}) if isinstance(manifest, dict) else {}
    if "match_rate" in matching:
        return float(matching.get("match_rate") or 0)
    if notices.empty or "match_confidence" not in notices.columns:
        return 0.0
    return float(notices["match_confidence"].isin(["High", "Medium"]).mean())


def data_readiness_status(buildings: pd.DataFrame, manifest: dict) -> tuple[str, str]:
    if buildings.empty:
        return "Review", "danger"
    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    age_parse_rate = float(processed.get("age_parse_rate") or buildings["building_age"].notna().mean())
    coordinate_rate = float(processed.get("coordinate_valid_rate") or buildings["has_valid_coordinate"].fillna(False).mean())
    if age_parse_rate >= 0.95 and coordinate_rate >= 0.95:
        return "Ready", "ok"
    if age_parse_rate >= 0.9 and coordinate_rate >= 0.85:
        return "Review", "warn"
    return "Attention", "danger"


def risk_pressure_status(buildings: pd.DataFrame) -> tuple[str, str]:
    if buildings.empty or "risk_level" not in buildings.columns:
        return "Review", "neutral"
    valid = buildings[buildings["risk_level"] != "Unknown"]
    if valid.empty:
        return "Review", "neutral"
    share = float(valid["risk_level"].isin(["High", "Critical"]).mean())
    if share >= 0.35:
        return "High pressure", "danger"
    if share >= 0.15:
        return "Moderate pressure", "warn"
    return "Low pressure", "ok"


def regulatory_coverage_status(notices: pd.DataFrame, manifest: dict) -> tuple[str, str]:
    rate = mbis_match_rate(notices, manifest)
    if rate >= 0.9:
        return "Strong match", "ok"
    if rate >= 0.6:
        return "Partial match", "warn"
    return "Weak match", "danger"


def render_page_safely(page_name: str, renderer, *args) -> None:
    try:
        renderer(*args)
    except Exception as exc:
        log(json.dumps({"dashboard_page_error": page_name, "error": str(exc)}, ensure_ascii=False))
        st.error(f"{page_name} could not be rendered. Rerun validation or refresh the processed data.")
        st.caption(f"Error summary: {exc}")


def add_map_legend(fmap: folium.Map, title: str, entries: dict[str, str]) -> None:
    rows = "".join(
        f"<div style='display:flex;align-items:center;gap:6px;margin:3px 0;'>"
        f"<span style='width:12px;height:12px;background:{color};display:inline-block;border:1px solid #374151;'></span>"
        f"<span>{label}</span></div>"
        for label, color in entries.items()
    )
    legend_html = (
        "<div style='position: fixed; bottom: 28px; left: 28px; z-index: 9999; "
        "background: white; padding: 10px 12px; border: 1px solid #d1d5db; "
        "border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); "
        "font-size: 12px; color: #111827;'>"
        f"<div style='font-weight: 700; margin-bottom: 6px;'>{title}</div>{rows}</div>"
    )
    fmap.get_root().html.add_child(Element(legend_html))


def sidebar_filters(buildings: pd.DataFrame) -> dict:
    if "ui_language" not in st.session_state:
        st.session_state["ui_language"] = "English"
    st.sidebar.segmented_control("Language / 语言", ["English", "中文"], key="ui_language")
    st.sidebar.title(tr("sidebar_title"))
    st.sidebar.caption(tr("screening_caption"))
    if "page_selector" not in st.session_state:
        st.session_state["page_selector"] = "Home / Start"
    if buildings.empty:
        if st.sidebar.button(tr("refresh_cache")):
            st.cache_data.clear()
            st.rerun()
        st.sidebar.divider()
        filters = {"_page": st.sidebar.radio(tr("page"), PAGE_OPTIONS, key="page_selector", format_func=page_label)}
        return filters
    filters = {}
    filter_columns = [
        ("district_en", "District"),
        ("territory_en", "Territory"),
        ("usage_group", "Usage"),
        ("type_group", "Type"),
        ("age_band", "Age band"),
        ("risk_level", "Risk level"),
    ]
    options_by_column = {
        column: sorted([value for value in buildings[column].dropna().unique()])
        for column, _ in filter_columns
        if column in buildings.columns
    }
    reset_clicked = st.sidebar.button(tr("reset_filters"))
    if reset_clicked:
        for column, options in options_by_column.items():
            st.session_state[f"filter_{column}"] = options
    for column, label in filter_columns:
        options = options_by_column.get(column, [])
        key = f"filter_{column}"
        if key not in st.session_state:
            st.session_state[key] = options
        else:
            st.session_state[key] = [value for value in st.session_state[key] if value in options]
        selected = st.sidebar.multiselect(tr(label), options, key=key)
        filters[column] = selected
    if st.sidebar.button(tr("refresh_cache")):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.divider()
    page = st.sidebar.radio(tr("page"), PAGE_OPTIONS, key="page_selector", format_func=page_label)
    filters["_page"] = page
    return filters


def _active_filter_summary(buildings: pd.DataFrame, filters: dict) -> str:
    active = []
    for column, selected in filters.items():
        if column.startswith("_") or column not in buildings.columns:
            continue
        all_values = set(buildings[column].dropna().unique())
        selected_values = set(selected or [])
        if selected_values and selected_values != all_values:
            active.append(f"{column}={len(selected_values)}/{len(all_values)}")
        elif not selected_values and all_values:
            active.append(f"{column}=0/{len(all_values)}")
    return ", ".join(active) if active else "All records"


def render_scope_bar(buildings: pd.DataFrame, filtered: pd.DataFrame, manifest: dict, filters: dict) -> None:
    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    source = processed.get("source_file", "unknown source")
    analysis_year = processed.get("analysis_year", "N/A")
    updated_at = processed.get("updated_at", "N/A")
    source_name = Path(str(source)).name if source else "unknown source"
    chips = [
        ("Records" if current_language() == "en" else "记录", f"{len(filtered):,}/{len(buildings):,}"),
        (tr("Data Mode"), tr(data_mode_label(manifest))),
        ("Analysis year" if current_language() == "en" else "分析年份", str(analysis_year)),
        (tr("Data Updated"), str(updated_at)),
        ("Filters" if current_language() == "en" else "筛选", _active_filter_summary(buildings, filters)),
        ("Source" if current_language() == "en" else "来源", source_name),
    ]
    chip_html = "".join(
        f"<div class='scope-chip'><strong>{escape(label)}</strong><span>{escape(value)}</span></div>"
        for label, value in chips
    )
    st.markdown(
        f"<div class='scope-bar'>{chip_html}</div>",
        unsafe_allow_html=True,
    )


def filtered_district_metrics(metrics: pd.DataFrame, buildings_filtered: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty or buildings_filtered.empty:
        return pd.DataFrame()
    districts = buildings_filtered["district_en"].dropna().unique()
    return metrics[metrics["district_en"].isin(districts)].copy()


def metric_row(buildings: pd.DataFrame, metrics: pd.DataFrame) -> None:
    total = len(buildings)
    valid_age = buildings["building_age"].dropna() if not buildings.empty else pd.Series(dtype=float)
    valid_risk = buildings[buildings["risk_level"] != "Unknown"] if not buildings.empty else pd.DataFrame()
    high_critical = buildings["risk_level"].isin(["High", "Critical"]).sum() if not buildings.empty else 0
    quality = metrics["data_quality_score"].mean() if not metrics.empty and "data_quality_score" in metrics.columns else 0
    cols = st.columns(8)
    cols[0].metric(tr("Total Buildings"), f"{total:,}")
    cols[1].metric(tr("Median Age"), f"{valid_age.median():.1f} yrs" if len(valid_age) else "N/A")
    cols[2].metric(tr("30+ Share"), pct((buildings["building_age"] >= 30).sum() / len(valid_age)) if len(valid_age) else "N/A")
    cols[3].metric(tr("40+ Share"), pct((buildings["building_age"] >= 40).sum() / len(valid_age)) if len(valid_age) else "N/A")
    cols[4].metric(tr("50+ Share"), pct((buildings["building_age"] >= 50).sum() / len(valid_age)) if len(valid_age) else "N/A")
    cols[5].metric(tr("60+ Share"), pct((buildings["building_age"] >= 60).sum() / len(valid_age)) if len(valid_age) else "N/A")
    cols[6].metric(tr("High/Critical"), pct(high_critical / len(valid_risk)) if len(valid_risk) else "N/A")
    cols[7].metric(tr("Data Quality"), f"{quality:.1f}/100" if quality else "N/A")


def page_home_start(buildings: pd.DataFrame, filtered: pd.DataFrame, metrics: pd.DataFrame, notices: pd.DataFrame, manifest: dict, filters: dict) -> None:
    st.header(tr("Home / Start"))
    render_page_intro("Home / Start")
    if buildings.empty:
        st.warning("No processed data found. Build from official cache or run the pipeline before analysis.")
        st.code("python -m src.pipeline.build_all --use-cache --analysis-year 2026", language="bash")
        if st.button("Restore official cached data", help="Rebuild processed outputs from cached official sources when available."):
            try:
                with st.spinner("Rebuilding processed outputs from official cached data..."):
                    build_all(use_cache=True, analysis_year=2026)
                st.cache_data.clear()
                st.success("Official cached data restored. Reloading dashboard data.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not restore official cached data: {exc}")
        return

    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    updated_at = processed.get("updated_at", "N/A")
    age_parse_rate = float(buildings["building_age"].notna().mean()) if len(buildings) and "building_age" in buildings else 0
    coordinate_valid_rate = (
        float(buildings["has_valid_coordinate"].fillna(False).mean())
        if len(buildings) and "has_valid_coordinate" in buildings
        else 0
    )
    cols = st.columns(5)
    cols[0].metric(tr("Data Mode"), tr(data_mode_label(manifest)))
    cols[1].metric(tr("Building Records"), f"{len(buildings):,}")
    cols[2].metric(tr("Filtered Records"), f"{len(filtered):,}")
    cols[3].metric(tr("MBIS Notices"), f"{len(notices):,}")
    cols[4].metric(tr("Quality Issues"), f"{quality_issue_count(manifest):,}")

    health_cols = st.columns(4)
    health_cols[0].metric(tr("Age Parse Rate"), pct(age_parse_rate))
    health_cols[1].metric(tr("Coordinate Valid Rate"), pct(coordinate_valid_rate))
    health_cols[2].metric(tr("MBIS Match Rate"), pct(mbis_match_rate(notices, manifest)))
    health_cols[3].metric(tr("Data Updated"), str(updated_at))

    data_status, data_tone = data_readiness_status(buildings, manifest)
    risk_status, risk_tone = risk_pressure_status(filtered)
    regulatory_status, regulatory_tone = regulatory_coverage_status(notices, manifest)
    render_status_tags(
        "Status Snapshot",
        [
            ("Data readiness", data_status, data_tone),
            ("Analysis risk pressure", risk_status, risk_tone),
            ("Regulatory coverage", regulatory_status, regulatory_tone),
        ],
    )

    st.info(
        "风险等级是基于公开数据的规则化筛查指标，不是结构安全鉴定结论。"
        if current_language() == "zh"
        else "Risk levels are rule-based public-data screening indicators, not structural inspection conclusions."
    )

    st.subheader(tr("Start With A Task"))
    tasks = [
        ("Full Hong Kong Portfolio", "Portfolio Overview", "Review portfolio age, usage, and risk structure."),
        ("Single District Priority", "District Benchmark", "Compare district priority index and maintenance signals."),
        ("Use Topic Analysis", "Use & Typology", "Inspect ageing pressure by building use and type."),
        ("Spatial Risk Review", "Spatial Dashboard", "Explore district layer, building points, and MBIS notices."),
        ("Regulatory Signal Review", "Regulatory Signals", "Check MBIS notice density and matching confidence."),
        ("Generate Research Report", "AI Report Studio", "Create a template or LLM-assisted report for export."),
    ]
    task_columns = st.columns(3)
    for index, (title, page, description) in enumerate(tasks):
        with task_columns[index % 3]:
            st.markdown(f"**{tr(title)}**")
            st.caption(tr(description))
            st.button(f"{tr('Open')} {tr(page)}", key=f"home_task_{index}", on_click=set_page, args=(page,))

    st.subheader(tr("Available Deliverables"))
    artifact_paths = [
        ("Export package ZIP", EXPORT_PACKAGE_ZIP),
        ("Example Markdown report", REPORTS_DIR / "example_report.md"),
        ("Example HTML report", REPORTS_DIR / "example_report.html"),
        ("Acceptance report", EXPORTS_DIR / "acceptance_report.md"),
        ("Product readiness report", EXPORTS_DIR / "product_readiness.md"),
    ]
    artifact_rows = [
        {
            "artifact": label,
            "status": ("Ready" if path.exists() else "Missing") if current_language() == "en" else ("可用" if path.exists() else "缺失"),
            "size": format_size(path.stat().st_size) if path.exists() else "N/A",
            "path": str(path),
        }
        for label, path in artifact_paths
    ]
    st.dataframe(pd.DataFrame(artifact_rows), width="stretch")
    if EXPORT_PACKAGE_ZIP.exists():
        st.download_button(
            tr("Download export package ZIP"),
            EXPORT_PACKAGE_ZIP.read_bytes(),
            EXPORT_PACKAGE_ZIP.name,
            "application/zip",
        )

    with st.expander(tr("Current Filter Summary")):
        st.write(_active_filter_summary(buildings, filters))


def page_data_intake(buildings: pd.DataFrame, metrics: pd.DataFrame, notices: pd.DataFrame, manifest: dict) -> None:
    st.header(tr("Data Intake"))
    render_page_intro("Data Intake")
    st.subheader("Data Source Controls" if current_language() == "en" else "数据源控制")
    if st.button(
        "Restore official cached data",
        help="Rebuild processed outputs from cached official BDBIAR, district boundary, and MBIS sources when available.",
    ):
        try:
            with st.spinner("Rebuilding processed outputs from official cached data..."):
                build_all(use_cache=True, analysis_year=2026)
            st.cache_data.clear()
            st.success("Official cached data restored. Reloading dashboard data.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not restore official cached data: {exc}")

    st.subheader("User CSV Upload" if current_language() == "en" else "用户 CSV 上传")
    uploaded = st.file_uploader("Upload building CSV with official or compatible fields", type=["csv"])
    if uploaded is not None:
        upload_path = CACHE_DIR / "uploaded_buildings.csv"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(uploaded.getvalue())
        st.info(f"Uploaded file staged at `{upload_path}`.")
        try:
            preview = pd.read_csv(upload_path, nrows=20)
            st.subheader("Uploaded Field Mapping Preview")
            lower_columns = {column.lower(): column for column in preview.columns}
            mapping_rows = []
            for target, aliases in COMPATIBLE_ALIASES.items():
                matched = next((alias for alias in aliases if alias in preview.columns), None)
                if matched is None:
                    matched = next((lower_columns[alias.lower()] for alias in aliases if alias.lower() in lower_columns), "")
                mapping_rows.append({"target_field": target, "matched_upload_column": matched})
            st.dataframe(pd.DataFrame(mapping_rows), width="stretch")
            st.dataframe(preview, width="stretch")
        except Exception as exc:
            st.warning(f"Could not preview uploaded CSV: {exc}")
        if st.button("Process uploaded CSV", type="primary"):
            try:
                normalize_buildings(upload_path, analysis_year=2026)
                build_risk_scores()
                match_regulatory_notices()
                build_district_metrics()
                st.cache_data.clear()
                st.success("Uploaded CSV processed. Reloading dashboard data.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not process uploaded CSV: {exc}")
    if buildings.empty:
        st.warning("No processed data found. Run `python -m src.pipeline.build_all --use-cache`.")
        st.code("python -m src.pipeline.build_all --use-cache\nstreamlit run app.py", language="bash")
        return
    quality_issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET) if DATA_QUALITY_ISSUES_PARQUET.exists() else pd.DataFrame()
    st.subheader("Data Health" if current_language() == "en" else "数据健康")
    health = st.columns(6)
    health[0].metric(tr("Data Mode"), tr(data_mode_label(manifest)))
    health[1].metric(tr("Building Records"), f"{len(buildings):,}")
    health[2].metric("Districts" if current_language() == "en" else "区域数", f"{buildings['district_en'].nunique(dropna=False):,}")
    health[3].metric(tr("Age Parse Rate"), pct(buildings["building_age"].notna().mean()))
    health[4].metric(tr("Coordinate Valid Rate"), pct(buildings["has_valid_coordinate"].fillna(False).mean()))
    health[5].metric(tr("Quality Issues"), f"{len(quality_issues):,}")
    data_status, data_tone = data_readiness_status(buildings, manifest)
    render_status_tags(
        "Data Health Summary",
        [
            ("Data readiness", data_status, data_tone),
            ("Regulatory coverage", regulatory_coverage_status(notices, manifest)[0], regulatory_coverage_status(notices, manifest)[1]),
        ],
    )

    quality = pd.DataFrame(
        [
            {"metric": "unknown_usage_count", "value": int((buildings["usage_group"] == "Unknown").sum())},
            {"metric": "unknown_type_count", "value": int((buildings["type_group"] == "Unknown").sum())},
            {"metric": "mbis_notice_records", "value": int(len(notices))},
            {"metric": "manifest_entries", "value": int(len(manifest))},
        ]
    )
    st.dataframe(quality, width="stretch", hide_index=True)
    if not quality_issues.empty:
        st.subheader("Data Quality Issues" if current_language() == "en" else "数据质量问题")
        flag_counts = {}
        for flags_json in quality_issues["issue_flags"].dropna():
            try:
                flags = json.loads(str(flags_json))
            except json.JSONDecodeError:
                flags = []
            for flag in flags if isinstance(flags, list) else []:
                flag_counts[str(flag)] = flag_counts.get(str(flag), 0) + 1
        st.dataframe(pd.DataFrame([{"issue_flag": key, "count": value} for key, value in sorted(flag_counts.items())]), width="stretch")
        st.subheader(tr("Default Quality Issue Preview"))
        st.dataframe(default_table(quality_issues, QUALITY_PREVIEW_COLUMNS, rows=100), width="stretch", hide_index=True)
        with st.expander(tr("Advanced quality issue fields")):
            st.dataframe(quality_issues.head(300), width="stretch")
        st.download_button(
            "Download data quality issues CSV",
            quality_issues.to_csv(index=False).encode("utf-8-sig"),
            "data_quality_issues.csv",
            "text/csv",
        )
    with st.expander("Source Manifest" if current_language() == "en" else "数据源 Manifest"):
        st.json(manifest)
    st.subheader(tr("Default Building Preview"))
    st.dataframe(default_table(buildings, BUILDING_PREVIEW_COLUMNS, rows=100), width="stretch", hide_index=True)
    with st.expander(tr("Advanced building fields")):
        st.dataframe(buildings.head(300), width="stretch")


def page_portfolio(buildings: pd.DataFrame, metrics: pd.DataFrame) -> None:
    st.header(tr("Portfolio Overview"))
    render_page_intro("Portfolio Overview")
    if buildings.empty:
        st.info("No data in current filter scope.")
        return
    metric_row(buildings, metrics)
    risk_status, risk_tone = risk_pressure_status(buildings)
    render_status_tags("Status Snapshot", [("Analysis risk pressure", risk_status, risk_tone)])
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.histogram(buildings, x="age_band", title=tr("Age Band Distribution")), width="stretch")
        chart_note("Chart note: Age bands show building age from occupation permit dates; unknown ages remain in data quality review.")
        st.plotly_chart(px.bar(buildings["usage_group"].value_counts().reset_index(), x="usage_group", y="count", title=tr("Usage Distribution")), width="stretch")
        chart_note("Chart note: Usage groups are normalised from public building records and support topic screening.")
    with right:
        risk_counts = buildings["risk_level"].value_counts().reset_index()
        st.plotly_chart(px.bar(risk_counts, x="risk_level", y="count", color="risk_level", color_discrete_map=RISK_COLORS, title=tr("Risk Level Distribution")), width="stretch")
        chart_note("Chart note: Risk levels are rule-based screening categories, not engineering inspection results.")
        if {"age_only_risk_level", "combined_risk_level"}.issubset(buildings.columns):
            comparison = pd.concat(
                [
                    buildings["age_only_risk_level"].value_counts().rename_axis("risk_level").reset_index(name="count").assign(model="Age-only"),
                    buildings["combined_risk_level"].value_counts().rename_axis("risk_level").reset_index(name="count").assign(model="Combined"),
                ],
                ignore_index=True,
            )
            st.plotly_chart(px.bar(comparison, x="risk_level", y="count", color="model", barmode="group", title=tr("Age-only vs Combined Risk")), width="stretch")
            chart_note("Chart note: Combined risk adds usage, type, and matched regulatory signal to the age-only baseline.")
        if not metrics.empty:
            top = metrics.sort_values("district_priority_index", ascending=False).head(10)
            st.plotly_chart(px.bar(top, x="district_priority_index", y="district_en", orientation="h", title=tr("Top District Priority Index")), width="stretch")
            chart_note("Chart note: District priority index combines age structure, high/critical share, MBIS signal, use mix, and data quality.")


def _district_color(value: float) -> str:
    if value >= 75:
        return "#b2182b"
    if value >= 50:
        return "#ef8a62"
    if value >= 25:
        return "#fddbc7"
    return "#d1e5f0"


def page_spatial(buildings: pd.DataFrame, metrics: pd.DataFrame, notices: pd.DataFrame) -> None:
    st.header(tr("Spatial Dashboard"))
    render_page_intro("Spatial Dashboard")
    st.caption(tr("Map points are screening indicators, not structural inspection results."))
    valid = buildings[buildings["has_valid_coordinate"].fillna(False)].copy()
    scoped_notices = scoped_notices_for_buildings(notices, buildings)
    if valid.empty and metrics.empty and scoped_notices.empty:
        st.info(tr("No valid coordinates in current filter scope."))
        return

    st.subheader(tr("Map Layers & Display"))
    st.caption(tr("Map display answers where ageing and regulatory signals concentrate; layers can be switched without changing the underlying data."))
    controls = st.columns([1.1, 1.1, 1.1, 1.4])
    with controls[0]:
        show_district_layer = st.checkbox(tr("District choropleth"), value=not metrics.empty, disabled=metrics.empty)
    with controls[1]:
        show_building_points = st.checkbox(tr("Building points"), value=0 < len(valid) <= 1500, disabled=valid.empty)
    with controls[2]:
        show_mbis_notices = st.checkbox(tr("MBIS notice layer"), value=0 < len(scoped_notices) <= 500, disabled=scoped_notices.empty)
    with controls[3]:
        choropleth_metric = st.selectbox(
            tr("District layer metric"),
            list(DISTRICT_LAYER_METRICS.keys()),
            index=0,
            format_func=district_metric_label,
            disabled=not show_district_layer or metrics.empty,
        )

    caps = st.columns(2)
    with caps[0]:
        building_limit = st.slider(
            tr("Building point cap"),
            100,
            5000,
            1200,
            step=100,
            disabled=not show_building_points or valid.empty,
            key="spatial_building_point_cap",
        )
    with caps[1]:
        notice_limit = st.slider(
            tr("MBIS point cap"),
            100,
            3000,
            1000,
            step=100,
            disabled=not show_mbis_notices or scoped_notices.empty,
            key="spatial_notice_point_cap",
        )

    map_buildings = valid.iloc[0:0].copy()
    building_mode = tr("Not shown")
    building_notes = tr("Enable the layer to inspect individual assets after narrowing filters.")
    if show_building_points and not valid.empty:
        if len(valid) > building_limit:
            map_buildings = valid.sample(building_limit, random_state=42)
            building_mode = tr("Clustered sample")
            building_notes = tr("Point cap reached; showing a deterministic sample for performance.")
        else:
            map_buildings = valid
            building_mode = tr("Full filtered set")
            building_notes = tr("Filtered scope")

    map_notices = scoped_notices.iloc[0:0].copy()
    notice_mode = tr("Not shown")
    notice_notes = tr("Scoped to buildings in the current filter.")
    if show_mbis_notices and not scoped_notices.empty:
        if len(scoped_notices) > notice_limit:
            map_notices = scoped_notices.sample(notice_limit, random_state=42)
            notice_mode = tr("Clustered sample")
            notice_notes = tr("Point cap reached; showing a deterministic sample for performance.")
        else:
            map_notices = scoped_notices
            notice_mode = tr("Full filtered set")

    status_rows = [
        {
            tr("Layer"): tr("District layer"),
            tr("Status"): tr("On") if show_district_layer else tr("Off"),
            tr("Records"): f"{len(metrics):,} districts",
            tr("Notes"): district_metric_label(choropleth_metric) if show_district_layer else tr("Not shown"),
        },
        {
            tr("Layer"): tr("Building point layer"),
            tr("Status"): building_mode if show_building_points else tr("Off"),
            tr("Records"): f"{len(map_buildings):,} / {len(valid):,}",
            tr("Notes"): building_notes,
        },
        {
            tr("Layer"): tr("MBIS notice layer"),
            tr("Status"): notice_mode if show_mbis_notices else tr("Off"),
            tr("Records"): f"{len(map_notices):,} / {len(scoped_notices):,}",
            tr("Notes"): notice_notes,
        },
    ]
    st.subheader(tr("Layer Display Status"))
    st.dataframe(pd.DataFrame(status_rows), width="stretch", hide_index=True)
    st.info(f"{tr('Map display mode')}: {tr('District choropleth first; point layers are optional for performance.')}")

    if not any([show_district_layer, show_building_points, show_mbis_notices]):
        st.warning(tr("No mappable layer is enabled. Turn on a layer to inspect spatial patterns."))

    fmap = folium.Map(location=[22.3193, 114.1694], zoom_start=11, tiles="CartoDB positron")
    boundary_path = RAW_DIR / "district_boundary" / "hksar_18_district_boundary.json"
    if show_district_layer and boundary_path.exists() and not metrics.empty:
        boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
        metric_records = metrics.set_index("district_en").to_dict("index")
        for feature in boundary.get("features", []):
            district = feature["properties"].get("District")
            record = metric_records.get(district, {})
            selected_value = as_float(record.get(choropleth_metric, 0))
            feature["properties"]["PriorityIndex"] = district_metric_display("district_priority_index", record.get("district_priority_index", 0))
            feature["properties"]["MedianAge"] = district_metric_display("median_age", record.get("median_age", 0))
            feature["properties"]["Share50Plus"] = district_metric_display("share_50_plus", record.get("share_50_plus", 0))
            feature["properties"]["MBISRate"] = district_metric_display("mbis_notice_rate", record.get("mbis_notice_rate", 0))
            feature["properties"]["SelectedRaw"] = selected_value
            feature["properties"]["SelectedMetric"] = district_metric_display(choropleth_metric, selected_value)

        def style_function(feature):
            value = as_float(feature["properties"].get("SelectedRaw", 0))
            return {
                "fillColor": district_metric_color(choropleth_metric, value),
                "color": "#4b5563",
                "weight": 1,
                "fillOpacity": 0.52,
            }

        folium.GeoJson(
            boundary,
            name=f"{district_metric_label(choropleth_metric)} choropleth",
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["District", "SelectedMetric", "PriorityIndex", "MedianAge", "Share50Plus", "MBISRate"],
                aliases=[
                    tr("District"),
                    district_metric_label(choropleth_metric),
                    tr("Priority index"),
                    tr("Median age"),
                    tr("50+ share"),
                    tr("MBIS notices per 1,000 buildings"),
                ],
                localize=True,
            ),
        ).add_to(fmap)

    if not map_buildings.empty:
        cluster = MarkerCluster(name=tr("Building points")).add_to(fmap)
        for _, row in map_buildings.iterrows():
            color = RISK_COLORS.get(row.get("risk_level", "Unknown"), "#7f8c8d")
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                tooltip=building_tooltip(row),
            ).add_to(cluster)

    if not map_notices.empty:
        notice_cluster = MarkerCluster(name=tr("MBIS notice layer")).add_to(fmap)
        for _, row in map_notices.iterrows():
            confidence = row.get("match_confidence", "Unmatched")
            color = "#111827" if confidence == "High" else "#4b5563" if confidence == "Medium" else "#9ca3af"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.72,
                tooltip=notice_tooltip(row),
            ).add_to(notice_cluster)

    folium.LayerControl().add_to(fmap)
    legend_entries = {}
    if show_district_layer:
        legend_entries.update(district_metric_legend(choropleth_metric))
    if show_building_points:
        legend_entries.update(
            {
                "Low risk": RISK_COLORS["Low"],
                "Medium risk": RISK_COLORS["Medium"],
                "High risk": RISK_COLORS["High"],
                "Critical risk": RISK_COLORS["Critical"],
            }
        )
    if show_mbis_notices:
        legend_entries[tr("MBIS notice")] = "#111827"
    add_map_legend(fmap, tr("Map Legend"), legend_entries or {"No active overlay": "#9ca3af"})
    st_folium(fmap, height=650, use_container_width=True)


def page_district(metrics: pd.DataFrame) -> None:
    st.header(tr("District Benchmark"))
    render_page_intro("District Benchmark")
    if metrics.empty:
        st.info("No district metrics available.")
        return
    sorted_metrics = metrics.sort_values("district_priority_index", ascending=False)
    st.subheader(tr("Default District Ranking"))
    st.dataframe(default_table(sorted_metrics, DISTRICT_RANKING_COLUMNS), width="stretch", hide_index=True)
    with st.expander(tr("Advanced district metrics")):
        st.dataframe(sorted_metrics, width="stretch")
    selected = st.selectbox("District detail", sorted_metrics["district_en"].tolist())
    row = sorted_metrics[sorted_metrics["district_en"] == selected].iloc[0]
    cols = st.columns(6)
    cols[0].metric(tr("Median Age"), f"{row['median_age']:.1f}")
    cols[1].metric(tr("50+ share"), pct(row["share_50_plus"]))
    cols[2].metric("Age-only H/C", pct(row.get("age_only_high_critical_share", row["high_critical_share"])))
    cols[3].metric("Combined H/C", pct(row.get("combined_high_critical_share", row["high_critical_share"])))
    cols[4].metric("MBIS Rate", f"{row['mbis_notice_rate']:.2f}/1000")
    cols[5].metric(tr("Priority index"), f"{row['district_priority_index']:.1f}")
    chart_note("Chart note: District priority index combines age structure, high/critical share, MBIS signal, use mix, and data quality.")
    st.download_button(tr("Download district metrics CSV"), sorted_metrics.to_csv(index=False).encode("utf-8-sig"), "district_metrics.csv", "text/csv")


def page_use_typology(buildings: pd.DataFrame) -> None:
    st.header(tr("Use & Typology"))
    render_page_intro("Use & Typology")
    if buildings.empty:
        st.info("No data in current filter scope.")
        return
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.histogram(buildings, x="usage_group", color="risk_level", barmode="group", title=tr("Usage x Risk")), width="stretch")
        chart_note("Chart note: Risk levels are rule-based screening categories, not engineering inspection results.")
        heat = pd.crosstab(buildings["district_en"], buildings["usage_group"])
        st.plotly_chart(px.imshow(heat, aspect="auto", title=tr("District x Usage Heatmap")), width="stretch")
        chart_note("Chart note: The heatmap counts buildings by district and use group within the current filter.")
    with right:
        st.plotly_chart(px.histogram(buildings, x="type_group", color="age_band", barmode="group", title=tr("Type x Age Band")), width="stretch")
        chart_note("Chart note: Type and age bands help identify typology-specific ageing pressure.")
        cross = pd.crosstab(buildings["usage_group"], buildings["age_band"])
        st.dataframe(cross, width="stretch")
        st.download_button(tr("Download usage-age cross table"), cross.to_csv().encode("utf-8-sig"), "usage_age_cross_table.csv", "text/csv")


def page_regulatory(notices: pd.DataFrame, metrics: pd.DataFrame) -> None:
    st.header(tr("Regulatory Signals"))
    render_page_intro("Regulatory Signals")
    st.warning("MBIS notices are regulatory records and should not be interpreted as direct proof of structural defect.")
    if notices.empty:
        st.info("No MBIS notice data available. Run `python -m src.data_sources.fetch_mbis --force` and rebuild the pipeline.")
        return
    coverage_status, coverage_tone = regulatory_coverage_status(notices, {})
    render_status_tags("Status Snapshot", [("Regulatory coverage", coverage_status, coverage_tone)])
    cols = st.columns(3)
    cols[0].metric(tr("Notice records"), f"{len(notices):,}")
    cols[1].metric(tr("Matched records"), f"{notices['match_confidence'].isin(['High', 'Medium']).sum():,}")
    cols[2].metric(tr("High confidence"), f"{(notices['match_confidence'] == 'High').sum():,}")
    st.plotly_chart(px.histogram(notices, x="match_confidence", title=tr("Matching Confidence")), width="stretch")
    chart_note("Chart note: Matching confidence indicates how reliably MBIS notices can be associated with building records.")
    if not metrics.empty:
        top = metrics.sort_values("mbis_notice_rate", ascending=False).head(10)
        st.plotly_chart(px.bar(top, x="mbis_notice_rate", y="district_en", orientation="h", title=tr("MBIS Notice Rate by District")), width="stretch")
        chart_note("Chart note: MBIS notice rate is a regulatory signal density per 1,000 buildings, not a defect rate.")
    notice_valid = notices.dropna(subset=["latitude", "longitude"]).copy()
    if not notice_valid.empty:
        st.subheader("MBIS Notice Points")
        notice_limit = st.slider("Max notice points", 100, 3000, min(1000, len(notice_valid)), step=100)
        notice_map = folium.Map(location=[22.3193, 114.1694], zoom_start=11, tiles="CartoDB positron")
        cluster = MarkerCluster(name="MBIS notices").add_to(notice_map)
        for _, row in notice_valid.head(notice_limit).iterrows():
            confidence = row.get("match_confidence", "Unmatched")
            color = "#111827" if confidence == "High" else "#4b5563" if confidence == "Medium" else "#9ca3af"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                tooltip=(
                    f"{row.get('address_en', '')}<br>"
                    f"Confidence: {confidence}<br>"
                    f"Method: {row.get('match_method', '')}<br>"
                    f"Ref: {row.get('notice_ref', '')}"
                ),
            ).add_to(cluster)
        folium.LayerControl().add_to(notice_map)
        add_map_legend(
            notice_map,
            "Match Confidence",
            {
                "High": "#111827",
                "Medium": "#4b5563",
                "Unmatched / Low": "#9ca3af",
            },
        )
        st_folium(notice_map, height=520, use_container_width=True)
    st.subheader(tr("Default Notice Preview"))
    st.dataframe(default_table(notices, NOTICE_PREVIEW_COLUMNS, rows=500), width="stretch", hide_index=True)
    with st.expander(tr("Advanced notice fields")):
        st.dataframe(notices.head(1000), width="stretch")
    st.download_button(tr("Download regulatory notices CSV"), notices.to_csv(index=False).encode("utf-8-sig"), "regulatory_notices.csv", "text/csv")


def page_ai_report(buildings: pd.DataFrame, metrics: pd.DataFrame, notices: pd.DataFrame, manifest: dict, filters: dict) -> None:
    st.header(tr("AI Report Studio"))
    render_page_intro("AI Report Studio")
    if buildings.empty:
        st.info("No data in current filter scope.")
        return
    settings = load_llm_settings()
    default_language = "中文" if current_language() == "zh" else "English"
    language_label = st.segmented_control("Language" if current_language() == "en" else "报告语言", ["中文", "English"], default=default_language)
    report_scope = st.segmented_control(
        tr("Report scope"),
        ["Full Hong Kong", "Current filters", "Single district", "Use topic"],
        default="Current filters",
        format_func=tr,
    )
    report_type = st.segmented_control(
        tr("Report type"),
        ["Executive Summary", "Research Note", "Maintenance Priority Brief", "Data Quality Memo"],
        default="Research Note",
        format_func=tr,
    )
    provider_options = ["Template", "DeepSeek", "OpenAI", "Local"]
    configured_provider = settings.get("provider", "Template") if settings.get("provider", "Template") in provider_options else "Template"
    method = st.segmented_control(tr("Generation"), provider_options, default=configured_provider)
    language = "zh" if language_label == "中文" else "en"
    payload = build_analysis_payload(buildings, metrics, notices, filters=filters, manifest=manifest)
    payload["analysis_scope"]["report_scope"] = report_scope
    payload["analysis_scope"]["report_type"] = report_type
    payload["analysis_scope"]["generation_method"] = method
    payload["analysis_scope"]["llm_provider_status"] = connection_status({**settings, "provider": method})

    processed = manifest.get("buildings_processed", {}) if isinstance(manifest, dict) else {}
    scope_rows = [
        {"item": "Current records", "value": f"{len(buildings):,}"},
        {"item": "Filters", "value": _active_filter_summary(buildings, filters)},
        {"item": "Data updated", "value": str(processed.get("updated_at", "N/A"))},
        {"item": "Analysis year", "value": str(processed.get("analysis_year", "N/A"))},
        {"item": "Risk model", "value": str(payload.get("model_version", "N/A"))},
        {"item": "Prompt version", "value": str(payload.get("prompt_version", "N/A"))},
        {"item": "Generation", "value": method},
    ]
    st.subheader("Report Scope Check" if current_language() == "en" else "报告范围确认")
    st.dataframe(pd.DataFrame(scope_rows), width="stretch", hide_index=True)

    metrics_preview = payload.get("portfolio_metrics", {})
    preview_cols = st.columns(4)
    preview_cols[0].metric(tr("Total"), f"{metrics_preview.get('total_buildings', 0):,}")
    preview_cols[1].metric(tr("Median age"), f"{metrics_preview.get('median_age', 0):.1f}")
    preview_cols[2].metric(tr("50+ share"), pct(metrics_preview.get("share_50_plus", 0)))
    preview_cols[3].metric(tr("High/Critical"), pct(metrics_preview.get("high_critical_share", 0)))

    if method != "Template":
        status = connection_status({**settings, "provider": method})
        if status["status"] != "Configured":
            st.warning(f"{method} is not ready: {status['detail']} Template fallback will be used.")

    if st.button(tr("Generate summary"), type="primary"):
        summary = None
        generation_note = "Template"
        if method != "Template":
            active_settings = {**settings, "provider": method}
            if method != settings.get("provider"):
                active_settings = {**active_settings, **provider_defaults(method), "api_key": ""}
            summary = generate_llm_summary(payload, language=language, settings=active_settings)
            if summary:
                ok, issues = validate_summary_text(summary)
                if not ok:
                    st.warning(f"LLM output failed validation and template fallback was used: {issues}")
                    summary = None
                else:
                    generation_note = method
        if not summary:
            summary = generate_template_summary(payload, language=language)
            st.info("Template summary generated." if method == "Template" else "LLM unavailable; template fallback generated.")
            generation_note = "Template fallback" if method != "Template" else "Template"
        payload["analysis_scope"]["generation_result"] = generation_note
        st.session_state["summary"] = summary
        st.session_state["payload"] = payload
    summary = st.session_state.get("summary")
    if summary:
        st.subheader("Report Preview" if current_language() == "en" else "报告预览")
        st.markdown(summary)
        col1, col2 = st.columns(2)
        if col1.button(tr("Export Markdown")):
            path = save_markdown_report(st.session_state["payload"], summary)
            st.success(f"Markdown report saved: {path} ({format_size(path.stat().st_size)})")
        if col2.button(tr("Export HTML")):
            path = save_html_report(st.session_state["payload"], summary)
            st.success(f"HTML report saved: {path} ({format_size(path.stat().st_size)})")


def page_admin_settings() -> None:
    st.header(tr("Admin / Settings"))
    render_page_intro("Admin / Settings")
    st.caption(
        "配置 DeepSeek / OpenAI / Local 模型连接。API Key 只写入本地 cache 配置，不进入报告或导出包。"
        if current_language() == "zh"
        else "Configure DeepSeek / OpenAI / Local model access. API keys are stored only in local cache settings and never included in reports or export packages."
    )
    settings = load_llm_settings()
    providers = ["Template", "DeepSeek", "OpenAI", "Local"]
    provider = st.selectbox(
        "LLM Provider" if current_language() == "en" else "LLM 服务商",
        providers,
        index=providers.index(settings.get("provider", "Template")) if settings.get("provider", "Template") in providers else 0,
    )
    defaults = provider_defaults(provider)
    current_status = connection_status({**settings, "provider": provider})
    status_cols = st.columns(3)
    status_cols[0].metric("Provider" if current_language() == "en" else "服务商", provider)
    status_cols[1].metric("Connection" if current_language() == "en" else "连接状态", current_status["status"])
    status_cols[2].metric("API Key" if current_language() == "en" else "API Key", masked_key(settings.get("api_key")))
    st.caption(current_status["detail"])

    api_key = st.text_input(
        "API Key",
        value=settings.get("api_key", ""),
        type="password",
        disabled=provider == "Template",
        help="Stored locally under data/cache and ignored by git.",
    )
    model = st.text_input(
        "Model name" if current_language() == "en" else "模型名称",
        value=settings.get("model") or defaults["model"],
        disabled=provider == "Template",
    )
    base_url = st.text_input(
        "Base URL",
        value=settings.get("base_url") or defaults["base_url"],
        disabled=provider == "Template",
        help="DeepSeek uses an OpenAI-compatible API base URL.",
    )

    next_settings = {
        **settings,
        "provider": provider,
        "api_key": api_key if provider != "Template" else "",
        "model": model if provider != "Template" else "",
        "base_url": base_url if provider != "Template" else "",
    }
    save_col, test_col = st.columns(2)
    if save_col.button("Save settings" if current_language() == "en" else "保存设置", type="primary"):
        save_llm_settings(next_settings)
        st.success("Settings saved locally." if current_language() == "en" else "设置已保存到本地。")
    if test_col.button("Test connection" if current_language() == "en" else "测试连接"):
        ok, message = test_llm_connection(next_settings)
        next_settings["last_test_status"] = "Passed" if ok else "Failed"
        next_settings["last_test_error"] = "" if ok else message
        save_llm_settings(next_settings)
        if ok:
            st.success(message)
        else:
            st.error(message)

    st.subheader("Safety" if current_language() == "en" else "安全规则")
    st.markdown(
        "- API keys are not included in Markdown/HTML reports.\n"
        "- API keys are not included in export packages.\n"
        "- LLM failures must fallback to Template mode."
        if current_language() == "en"
        else "- API Key 不进入 Markdown/HTML 报告。\n- API Key 不进入导出包。\n- LLM 失败时必须 fallback 到 Template 模式。"
    )


def page_method_qa(buildings: pd.DataFrame, metrics: pd.DataFrame, manifest: dict) -> None:
    st.header(tr("Method & QA"))
    render_page_intro("Method & QA")
    render_status_tags(
        "Status Snapshot",
        [
            ("Data readiness", data_readiness_status(buildings, manifest)[0], data_readiness_status(buildings, manifest)[1]),
            ("Analysis risk pressure", risk_pressure_status(buildings)[0], risk_pressure_status(buildings)[1]),
        ],
    )
    with st.expander(tr("Files")):
        st.code(
            f"{BUILDINGS_PARQUET}\n{DISTRICT_METRICS_PARQUET}\n{REGULATORY_NOTICES_PARQUET}\n{MANIFEST_PATH}",
            language="text",
        )
    st.subheader(tr("Risk Rule"))
    st.markdown(
        "Risk score reports both an age-only baseline and a combined score using age, usage, building type, and matched regulatory signal. "
        "It is a rule-based screening indicator, not a structural inspection result."
    )
    with st.expander(tr("Data Source Manifest")):
        st.json(manifest)
    st.subheader(tr("Quality Snapshot"))
    if not buildings.empty:
        quality_issues = read_parquet(DATA_QUALITY_ISSUES_PARQUET) if DATA_QUALITY_ISSUES_PARQUET.exists() else pd.DataFrame()
        quality_snapshot = {
            "record_count": len(buildings),
            "age_parse_rate": buildings["building_age"].notna().mean(),
            "coordinate_valid_rate": buildings["has_valid_coordinate"].fillna(False).mean(),
            "risk_distribution": buildings["risk_level"].value_counts().to_dict(),
            "district_count": buildings["district_en"].nunique(dropna=False),
            "data_quality_issue_count": len(quality_issues),
        }
        st.json(quality_snapshot)
        method_summary = "\n".join(
            [
                "# Method Summary",
                "",
                "Risk score combines age, usage, building type, and matched regulatory signal.",
                "This is a rule-based screening indicator, not a structural inspection result.",
                "",
                "## Data Quality",
                json.dumps(quality_snapshot, ensure_ascii=False, indent=2),
            ]
        )
        st.download_button(tr("Download method summary"), method_summary.encode("utf-8"), "method_summary.md", "text/markdown")
        st.download_button(tr("Download current filtered buildings CSV"), buildings.to_csv(index=False).encode("utf-8-sig"), "filtered_buildings.csv", "text/csv")
        if not quality_issues.empty:
            st.download_button(
                tr("Download data quality issues CSV"),
                quality_issues.to_csv(index=False).encode("utf-8-sig"),
                "data_quality_issues.csv",
                "text/csv",
            )
        if st.button(tr("Generate full export package")):
            try:
                artifacts = export_results()
                st.success("Export package generated under outputs/exports and outputs/figures.")
                st.json(artifacts)
            except Exception as exc:
                st.error(f"Could not generate export package: {exc}")
        if EXPORT_PACKAGE_ZIP.exists():
            st.download_button(
                "Download export package ZIP",
                EXPORT_PACKAGE_ZIP.read_bytes(),
                EXPORT_PACKAGE_ZIP.name,
                "application/zip",
            )
    if not metrics.empty:
        st.subheader(tr("Default District Ranking"))
        st.dataframe(default_table(metrics.sort_values("district_priority_index", ascending=False), DISTRICT_RANKING_COLUMNS), width="stretch", hide_index=True)
        with st.expander(tr("Advanced district metrics")):
            st.dataframe(metrics, width="stretch")
        component_columns = [
            "district_en",
            "priority_median_age_component",
            "priority_share_50_plus_component",
            "priority_high_critical_component",
            "priority_mbis_notice_component",
            "priority_usage_mix_component",
            "district_priority_index",
            "district_priority_mode",
        ]
        available_components = [column for column in component_columns if column in metrics.columns]
        if available_components:
            st.subheader(tr("District Priority Components"))
            st.dataframe(metrics[available_components].sort_values("district_priority_index", ascending=False), width="stretch", hide_index=True)
        st.download_button(tr("Download district metrics CSV"), metrics.to_csv(index=False).encode("utf-8-sig"), "district_metrics.csv", "text/csv")


def main() -> None:
    buildings, metrics, notices, manifest = cached_data()
    filters = sidebar_filters(buildings)
    page = filters.pop("_page", "Home / Start")
    filtered = apply_filters(buildings, filters) if not buildings.empty else buildings
    filtered_metrics = filtered_district_metrics(metrics, filtered)
    apply_visual_system()
    st.title(tr("app_title"))
    st.caption(tr("app_caption"))
    render_scope_bar(buildings, filtered, manifest, filters)
    page_renderers = {
        "Home / Start": (page_home_start, (buildings, filtered, metrics, notices, manifest, filters)),
        "Data Intake": (page_data_intake, (buildings, metrics, notices, manifest)),
        "Portfolio Overview": (page_portfolio, (filtered, filtered_metrics)),
        "Spatial Dashboard": (page_spatial, (filtered, filtered_metrics, notices)),
        "District Benchmark": (page_district, (filtered_metrics,)),
        "Use & Typology": (page_use_typology, (filtered,)),
        "Regulatory Signals": (page_regulatory, (notices, metrics)),
        "AI Report Studio": (page_ai_report, (filtered, filtered_metrics, notices, manifest, filters)),
        "Admin / Settings": (page_admin_settings, ()),
        "Method & QA": (page_method_qa, (filtered, filtered_metrics, manifest)),
    }
    renderer, args = page_renderers.get(page, page_renderers["Home / Start"])
    render_page_safely(page, renderer, *args)


if __name__ == "__main__":
    main()
