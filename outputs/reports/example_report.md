# Hong Kong Building Asset Age Risk Report - Example

## Report Metadata

- Generated at: 2026-06-06T20:39:03
- Model version: risk_rules_v0.3_age_regulatory_combined
- Prompt version: summary_prompt_v0.2_with_regulatory_signals
- Filters: `{}`

## Data Scope And Source Version

| Source | Records | Updated at | File / URL |
| --- | --- | --- | --- |
| bdbiar |  | 2026-06-06T13:42:14+08:00 |  |
| district_boundary |  | 2026-06-06T13:42:15+08:00 |  |
| mbis_issued |  | 2026-06-06T13:42:18+08:00 |  |
| buildings_processed | 51037 | 2026-06-06T20:38:28+08:00 | D:\AI+arch＋hku\香港建筑资产年龄数据分析与 AI 风险摘要生成\data\processed\buildings.parquet |
| risk_model | 51037 | 2026-06-06T20:38:30+08:00 | D:\AI+arch＋hku\香港建筑资产年龄数据分析与 AI 风险摘要生成\data\processed\buildings.parquet |
| mbis_matching | 2362 | 2026-06-06T20:38:40+08:00 | D:\AI+arch＋hku\香港建筑资产年龄数据分析与 AI 风险摘要生成\data\processed\regulatory_notices.parquet |
| district_metrics | 51037 | 2026-06-06T20:38:40+08:00 | D:\AI+arch＋hku\香港建筑资产年龄数据分析与 AI 风险摘要生成\data\processed\district_metrics.parquet |
| data_quality_issues | 776 | 2026-06-06T20:38:28+08:00 | D:\AI+arch＋hku\香港建筑资产年龄数据分析与 AI 风险摘要生成\data\processed\data_quality_issues.parquet |

## Core Metrics

- Total buildings: 51,037
- Mean age: 37.5 years
- Median age: 38.0 years
- 30+ share: 69.5%
- 40+ share: 45.6%
- 50+ share: 24.2%
- 60+ share: 12.1%
- High/Critical share: 68.0%

## Age Distribution

| Age band | Count | Share |
| --- | --- | --- |
| 30-39 | 11,992 | 23.5% |
| 40-49 | 10,754 | 21.1% |
| 0-19 | 8,158 | 16.0% |
| 20-29 | 7,195 | 14.1% |
| 50-59 | 6,095 | 11.9% |
| 60+ | 6,067 | 11.9% |
| Unknown | 776 | 1.5% |

## Risk Distribution

| Risk level | Count | Share |
| --- | --- | --- |
| High | 20,623 | 40.4% |
| Critical | 13,542 | 26.5% |
| Low | 8,157 | 16.0% |
| Medium | 7,939 | 15.6% |
| Unknown | 776 | 1.5% |

## Risk Model Breakdown

- Age-only mean risk score: 48.1
- Combined mean risk score: 61.5
- Mean contextual risk score: 13.7
- Age-only High/Critical share: 45.6%
- Combined High/Critical share: 68.0%
- Records with matched regulatory signal: 2,314

### Age-Only Risk Distribution

| Risk level | Count | Share |
| --- | --- | --- |
| High | 16,849 | 33.0% |
| Low | 15,353 | 30.1% |
| Medium | 11,992 | 23.5% |
| Critical | 6,067 | 11.9% |
| Unknown | 776 | 1.5% |

### Combined Risk Distribution

| Risk level | Count | Share |
| --- | --- | --- |
| High | 20,623 | 40.4% |
| Critical | 13,542 | 26.5% |
| Low | 8,157 | 16.0% |
| Medium | 7,939 | 15.6% |
| Unknown | 776 | 1.5% |

## District Priority Ranking

| District | Priority index | Buildings | Median age | 50+ share | Age-only H/C | Combined H/C | MBIS / 1000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Yau Tsim Mong | 93.2 | 4,219 | 49.0 | 49.6% | 67.7% | 80.8% | 94.81 |
| Sham Shui Po | 88.0 | 2,758 | 47.0 | 45.2% | 64.6% | 78.6% | 112.76 |
| Kowloon City | 82.5 | 4,015 | 47.0 | 43.7% | 61.6% | 72.3% | 96.89 |
| Wan Chai | 82.4 | 3,525 | 47.0 | 43.9% | 64.2% | 81.0% | 53.33 |
| Kwun Tong | 82.2 | 1,293 | 44.0 | 31.8% | 59.1% | 78.2% | 75.79 |
| Wong Tai Sin | 79.9 | 682 | 48.0 | 48.1% | 59.1% | 70.0% | 42.52 |
| Central & Western | 78.0 | 4,632 | 44.0 | 37.2% | 59.8% | 78.1% | 58.29 |
| Kwai Tsing | 74.5 | 1,021 | 43.0 | 25.2% | 58.1% | 73.5% | 58.77 |
| Eastern | 72.4 | 2,121 | 42.0 | 29.5% | 58.8% | 81.0% | 67.89 |
| Tsuen Wan | 68.6 | 1,360 | 38.0 | 30.5% | 46.3% | 67.8% | 69.85 |

### District Priority Components

| District | Median age | 50+ share | High/Critical | MBIS | Usage mix | Mode |
| --- | --- | --- | --- | --- | --- | --- |
| Yau Tsim Mong | 30.0 | 25.0 | 20.0 | 12.6 | 5.7 | combined_age_regulatory |
| Sham Shui Po | 28.7 | 22.8 | 19.4 | 15.0 | 2.1 | combined_age_regulatory |
| Kowloon City | 28.7 | 22.0 | 17.9 | 12.9 | 1.1 | combined_age_regulatory |
| Wan Chai | 28.7 | 22.1 | 20.0 | 7.1 | 4.4 | combined_age_regulatory |
| Kwun Tong | 26.8 | 16.0 | 19.3 | 10.1 | 10.0 | combined_age_regulatory |
| Wong Tai Sin | 29.4 | 24.2 | 17.3 | 5.7 | 3.3 | combined_age_regulatory |
| Central & Western | 26.8 | 18.7 | 19.3 | 7.8 | 5.4 | combined_age_regulatory |
| Kwai Tsing | 26.2 | 12.7 | 18.2 | 7.8 | 9.6 | combined_age_regulatory |
| Eastern | 25.5 | 14.9 | 20.0 | 9.0 | 3.0 | combined_age_regulatory |
| Tsuen Wan | 23.0 | 15.4 | 16.7 | 9.3 | 4.2 | combined_age_regulatory |

## Use And Typology Signals

| Usage group | Count | Share |
| --- | --- | --- |
| Residential/Composite | 40,522 | 79.4% |
| Others | 4,167 | 8.2% |
| Office/Commercial | 4,054 | 7.9% |
| Industrial | 2,294 | 4.5% |

## Regulatory Signals

- MBIS notice records: 2,362
- Matched MBIS records: 2,360
- Regulatory signals are public-record indicators and must be interpreted as prioritization context only.

## Data Quality

- Age parse rate: 98.5%
- Coordinate valid rate: 100.0%
- Invalid coordinate records: 0
- Unknown usage records: 0
- Unknown type records: 0

## AI / Template Summary

## Overall Risk Summary
当前分析范围共有 51,037 条建筑记录，中位楼龄为 38.0 年。30 年以上建筑占比为 69.5%，40 年以上为 45.6%，50 年以上为 24.2%，60 年以上为 12.1%，High / Critical 初步筛查等级占比为 68.0%。其中 age-only High / Critical 为 45.6%，combined High / Critical 为 68.0%。

## Key Observations
当前优先级较高的区域包括：Yau Tsim Mong, Sham Shui Po, Kowloon City。监管信号层共有 2,362 条 MBIS 通知记录，其中 2,360 条与建筑记录形成匹配。

## Maintenance Priorities
建议优先关注中位楼龄较高、50 年以上建筑占比较高、High / Critical 筛查结果较集中的区域和用途类别。

## Data Limitations
楼龄解析率为 98.5%，坐标有效率为 100.0%。本结果是基于公开数据和规则模型的初步筛查指标，不等同于正式结构安全鉴定。

## Method Note
本摘要只基于 dashboard 聚合指标和公开记录生成，没有读取或判断现场检测结果。

## Method Limitations

- Risk scores are rule-based screening indicators, not structural inspection results.
- Regulatory notices are public-record signals, not direct proof of structural defects.
- Results depend on public data field completeness and matching quality.