from __future__ import annotations

from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def generate_template_summary(payload: dict[str, Any], language: str = "zh") -> str:
    metrics = payload.get("portfolio_metrics", {})
    risk_model = payload.get("risk_model_breakdown", {})
    quality = payload.get("data_quality", {})
    regulatory = payload.get("regulatory_signals", {})
    districts = payload.get("district_ranking", [])[:3]
    district_names = ", ".join(str(item.get("district_en", "")) for item in districts if item.get("district_en")) or "N/A"
    total = metrics.get("total_buildings", 0)
    median_age = metrics.get("median_age", 0)
    share_30 = _pct(metrics.get("share_30_plus", 0))
    share_40 = _pct(metrics.get("share_40_plus", 0))
    share_50 = _pct(metrics.get("share_50_plus", 0))
    share_60 = _pct(metrics.get("share_60_plus", 0))
    high_share = _pct(metrics.get("high_critical_share", 0))
    age_only_high_share = _pct(risk_model.get("age_only_high_critical_share", 0))
    combined_high_share = _pct(risk_model.get("combined_high_critical_share", metrics.get("high_critical_share", 0)))
    matched = regulatory.get("matched_count", 0)
    notices = regulatory.get("notice_count", 0)

    if language == "en":
        return (
            "## Overall Risk Summary\n"
            f"The current scope contains {total:,} building records. The median building age is {median_age:.1f} years. "
            f"Buildings aged 30+ account for {share_30}, 40+ for {share_40}, 50+ for {share_50}, and 60+ for {share_60}. "
            f"High and Critical screening levels account for {high_share}; age-only High/Critical is {age_only_high_share}, "
            f"while combined High/Critical is {combined_high_share}.\n\n"
            "## Key Observations\n"
            f"The highest-priority districts in the current screening are {district_names}. "
            f"The regulatory signal layer contains {notices:,} MBIS notice records, with {matched:,} matched to building records.\n\n"
            "## Maintenance Priorities\n"
            "Prioritize districts and usage groups with older median age, higher 50+ share, and concentrated High/Critical screening results.\n\n"
            "## Data Limitations\n"
            f"Age parse rate is {_pct(quality.get('age_parse_rate', 0))}; coordinate valid rate is {_pct(quality.get('coordinate_valid_rate', 0))}. "
            "This is a rule-based screening indicator, not a structural inspection result.\n\n"
            "## Method Note\n"
            "The summary is generated from aggregated dashboard metrics and public records only."
        )

    return (
        "## Overall Risk Summary\n"
        f"当前分析范围共有 {total:,} 条建筑记录，中位楼龄为 {median_age:.1f} 年。"
        f"30 年以上建筑占比为 {share_30}，40 年以上为 {share_40}，50 年以上为 {share_50}，60 年以上为 {share_60}，"
        f"High / Critical 初步筛查等级占比为 {high_share}。"
        f"其中 age-only High / Critical 为 {age_only_high_share}，combined High / Critical 为 {combined_high_share}。\n\n"
        "## Key Observations\n"
        f"当前优先级较高的区域包括：{district_names}。"
        f"监管信号层共有 {notices:,} 条 MBIS 通知记录，其中 {matched:,} 条与建筑记录形成匹配。\n\n"
        "## Maintenance Priorities\n"
        "建议优先关注中位楼龄较高、50 年以上建筑占比较高、High / Critical 筛查结果较集中的区域和用途类别。\n\n"
        "## Data Limitations\n"
        f"楼龄解析率为 {_pct(quality.get('age_parse_rate', 0))}，坐标有效率为 {_pct(quality.get('coordinate_valid_rate', 0))}。"
        "本结果是基于公开数据和规则模型的初步筛查指标，不等同于正式结构安全鉴定。\n\n"
        "## Method Note\n"
        "本摘要只基于 dashboard 聚合指标和公开记录生成，没有读取或判断现场检测结果。"
    )
