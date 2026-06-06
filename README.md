# Hong Kong Building Asset Age Risk Dashboard

This project implements a local-first research dashboard for Hong Kong private building asset ageing, maintenance priority screening, regulatory signals, and AI-assisted reporting.

## Quick Start

The easiest way to open the product on Windows is to double-click:

```text
start_dashboard.bat
```

Then open:

```text
http://localhost:8501
```

Detailed usage notes are in `docs/07_使用说明.md`.
The app opens on `Home / Start`, which shows data status, recommended analysis tasks, and available deliverables.
Use the sidebar `Language / 语言` control for English or Chinese UI. Configure DeepSeek/OpenAI under `Admin / Settings` before using LLM generation in `AI Report Studio`; Template mode works without any API key.
`Spatial Dashboard` opens with a district choropleth first and lets users enable building points or MBIS notice layers with explicit point caps, clustering, and display status.
Every page now includes a short first-screen explanation, and the top scope bar shows records, data mode, analysis year, data update time, filters, and source as scan-friendly status labels.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.pipeline.build_all --use-cache
python -m src.pipeline.validate_outputs
python -m src.pipeline.acceptance_check
streamlit run app.py
```

If the official data source is unavailable, the pipeline falls back to `data/sample/sample_buildings.csv`.

## Core Commands

```bash
python -m src.data_sources.fetch_bdbiar --force
python -m src.data_sources.fetch_boundaries --force
python -m src.data_sources.fetch_mbis --force
python -m src.pipeline.build_all --use-cache
python -m src.pipeline.export_results
python -m src.pipeline.generate_scenario_reports
python -m src.pipeline.capture_dashboard_screenshots
python -m src.pipeline.dashboard_smoke
python -m src.pipeline.validate_outputs
python -m src.pipeline.acceptance_check
python -m src.pipeline.product_readiness
streamlit run app.py
```

## Data Outputs

- `data/processed/buildings.parquet`
- `data/processed/district_metrics.parquet`
- `data/processed/regulatory_notices.parquet`
- `data/processed/data_quality_issues.parquet`
- `data/cache/source_manifest.json`
- `outputs/exports/acceptance_check.json`
- `outputs/exports/acceptance_report.md`
- `outputs/exports/dashboard_smoke.json`
- `outputs/exports/scenario_reports_manifest.json`
- `outputs/exports/product_readiness.json`
- `outputs/exports/product_readiness.md`
- `outputs/exports/export_manifest.json`
- `outputs/exports/export_package.zip`
- `outputs/exports/buildings_latest.csv`
- `outputs/exports/district_metrics_latest.csv`
- `outputs/exports/regulatory_notices_latest.csv`
- `outputs/exports/data_quality_issues_latest.csv`
- `outputs/exports/method_summary.md`
- `outputs/figures/*.html`
- `outputs/screenshots/*.png`
- `outputs/screenshots/screenshots_manifest.json`
- `outputs/reports/example_report.md`
- `outputs/reports/example_report.html`
- `outputs/reports/scenario_full_hong_kong.md`
- `outputs/reports/scenario_district_yau_tsim_mong.md`
- `outputs/reports/scenario_use_industrial.md`
- `outputs/reports/scenario_data_quality_memo.md`

`python -m src.pipeline.build_all --use-cache` now validates processed data and refreshes the standard export package.
`python -m src.pipeline.generate_scenario_reports` writes the four final acceptance journey reports: full Hong Kong, single district, use topic, and data quality memo.
`python -m src.pipeline.capture_dashboard_screenshots` writes the standard dashboard screenshots under `outputs/screenshots/`. Run `python -m playwright install chromium` once before first use.
`python -m src.pipeline.dashboard_smoke` loads all 10 dashboard pages and fails on unhandled exceptions or visible Streamlit error elements.
`python -m src.pipeline.product_readiness` runs the full release gate and writes product readiness evidence.
The Method & QA page can generate and download `outputs/exports/export_package.zip`, which bundles export tables, HTML figures, and generated reports.
The pytest suite snapshots and restores processed data/output artifacts, so standalone test runs do not leave the dashboard in sample-data state.

Demo guidance and screenshot references are in `docs/09_演示流程与截图清单.md`.

## User CSV Upload

The dashboard can process the official schema and common compatible fields such as:

- `building_id`
- `address`
- `district`
- `territory`
- `building_use`
- `building_type`
- `completion_year`
- `latitude`
- `longitude`

Uploaded CSVs replace the processed dashboard outputs under `data/processed/`, but they do not delete official raw/cache files. Use **Restore official cached data** on the Data Intake page to rebuild the processed outputs from official cached sources. The equivalent command-line recovery path is:

```bash
python -m src.pipeline.build_all --use-cache --analysis-year 2026
```

## Scope

The risk score is a rule-based screening indicator based on public records. It is not a structural inspection result.

## Product Verification

```bash
python -m compileall app.py src tests
python -m pytest
python -m src.pipeline.build_all --use-cache --analysis-year 2026
python -m src.pipeline.validate_outputs
python -m src.pipeline.generate_scenario_reports
python -m src.pipeline.dashboard_smoke
python -m src.pipeline.acceptance_check
python -m src.pipeline.product_readiness
```

The acceptance command writes both machine-readable and human-readable evidence:

- `outputs/exports/acceptance_check.json`
- `outputs/exports/acceptance_report.md`
- `outputs/exports/dashboard_smoke.json`
- `outputs/exports/scenario_reports_manifest.json`
- `outputs/exports/product_readiness.json`
- `outputs/exports/product_readiness.md`
