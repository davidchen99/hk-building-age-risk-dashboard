from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.utils.config import OUTPUTS_DIR, log, now_iso, resolve_path


@dataclass(frozen=True)
class ScreenshotTarget:
    page: str
    filename: str
    title: str
    purpose: str


SCREENSHOT_TARGETS = [
    ScreenshotTarget("Home / Start", "01_home_start.png", "Dashboard Home / Start", "Data status, recommended tasks, deliverables."),
    ScreenshotTarget("Portfolio Overview", "02_portfolio_overview.png", "Portfolio Overview", "Portfolio age, usage, and risk structure."),
    ScreenshotTarget("Spatial Dashboard", "03_spatial_dashboard.png", "Spatial Dashboard", "District choropleth, point layers, and map display status."),
    ScreenshotTarget("District Benchmark", "04_district_benchmark.png", "District Benchmark", "District priority ranking and selected district metrics."),
    ScreenshotTarget("AI Report Studio", "05_ai_report_studio.png", "AI Report Studio", "Report scope check and generation controls."),
    ScreenshotTarget("Method & QA", "06_method_qa.png", "Method & QA", "Method audit, quality snapshot, and export package controls."),
]


def _healthcheck(base_url: str, timeout: int = 15) -> None:
    health_url = f"{base_url.rstrip('/')}/_stcore/health"
    response = requests.get(health_url, timeout=timeout)
    response.raise_for_status()
    if response.text.strip().lower() != "ok":
        raise RuntimeError(f"Streamlit healthcheck returned unexpected response: {response.text!r}")


def capture_dashboard_screenshots(base_url: str = "http://localhost:8501", output_dir: Path | None = None) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for screenshots. Run `pip install playwright` and `python -m playwright install chromium`.") from exc

    output = resolve_path(output_dir, OUTPUTS_DIR / "screenshots")
    output.mkdir(parents=True, exist_ok=True)
    _healthcheck(base_url)

    artifacts = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1600}, device_scale_factor=1)
        page.goto(base_url, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(2500)
        page.add_style_tag(
            content="""
            [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], header {
                display: none !important;
            }
            .block-container {
                padding-top: 0.8rem !important;
            }
            """
        )

        for target in SCREENSHOT_TARGETS:
            if target.page != "Home / Start":
                page.get_by_text(target.page, exact=True).first.click(timeout=20_000)
                page.wait_for_timeout(2500)
                page.get_by_role("heading", name=target.page).first.wait_for(timeout=20_000)
            screenshot_path = output / target.filename
            if target.page == "Spatial Dashboard":
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(5000)
                page.screenshot(path=str(screenshot_path), full_page=False)
            else:
                page.screenshot(path=str(screenshot_path), full_page=True)
            artifacts.append(
                {
                    "page": target.page,
                    "title": target.title,
                    "purpose": target.purpose,
                    "path": str(screenshot_path),
                    "size_bytes": screenshot_path.stat().st_size,
                }
            )
        browser.close()

    manifest = {
        "generated_at": now_iso(),
        "base_url": base_url,
        "screenshot_count": len(artifacts),
        "screenshots": artifacts,
    }
    manifest_path = output / "screenshots_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps({"screenshots_generated": True, "count": len(artifacts), "output": str(output)}, ensure_ascii=False))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8501")
    parser.add_argument("--output-dir", default="outputs/screenshots")
    args = parser.parse_args()
    print(json.dumps(capture_dashboard_screenshots(args.base_url, Path(args.output_dir)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
