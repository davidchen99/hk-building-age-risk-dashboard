from src.pipeline.capture_dashboard_screenshots import SCREENSHOT_TARGETS


def test_standard_screenshot_targets_are_defined():
    filenames = [target.filename for target in SCREENSHOT_TARGETS]
    pages = [target.page for target in SCREENSHOT_TARGETS]
    assert filenames == [
        "01_home_start.png",
        "02_portfolio_overview.png",
        "03_spatial_dashboard.png",
        "04_district_benchmark.png",
        "05_ai_report_studio.png",
        "06_method_qa.png",
    ]
    assert pages == [
        "Home / Start",
        "Portfolio Overview",
        "Spatial Dashboard",
        "District Benchmark",
        "AI Report Studio",
        "Method & QA",
    ]
