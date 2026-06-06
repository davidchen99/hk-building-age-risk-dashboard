from streamlit.testing.v1 import AppTest

from src.pipeline.dashboard_smoke import run_dashboard_smoke


def test_streamlit_app_loads_all_core_pages():
    pages = [
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
    app_test = AppTest.from_file("app.py", default_timeout=60)
    app_test.run()
    assert not app_test.exception
    assert any(title.value == "Hong Kong Building Asset Age Risk Dashboard" for title in app_test.title)
    assert any(header.value == "Home / Start" for header in app_test.header)
    assert any("Start from the current data status" in markdown.value for markdown in app_test.markdown)
    assert any("Data Mode" in markdown.value and "Official cache" in markdown.value for markdown in app_test.markdown)
    assert any(subheader.value == "Status Snapshot" for subheader in app_test.subheader)
    assert any("Data readiness" in markdown.value for markdown in app_test.markdown)
    assert any(button.label == "Open Portfolio Overview" for button in app_test.button)
    for page in pages:
        app_test.sidebar.radio[0].set_value(page).run()
        assert not app_test.exception
        assert any(header.value == page for header in app_test.header)
    app_test.sidebar.radio[0].set_value("Spatial Dashboard").run()
    assert any("Locate where ageing pressure" in markdown.value for markdown in app_test.markdown)
    assert any(subheader.value == "Map Layers & Display" for subheader in app_test.subheader)
    assert any(subheader.value == "Layer Display Status" for subheader in app_test.subheader)
    assert any(checkbox.label == "District choropleth" for checkbox in app_test.checkbox)
    assert any(selectbox.label == "District layer metric" for selectbox in app_test.selectbox)
    app_test.sidebar.radio[0].set_value("Portfolio Overview").run()
    assert any("Chart note: Age bands show building age" in caption.value for caption in app_test.caption)
    app_test.sidebar.radio[0].set_value("District Benchmark").run()
    assert any(subheader.value == "Default District Ranking" for subheader in app_test.subheader)
    app_test.sidebar.radio[0].set_value("Regulatory Signals").run()
    assert any(subheader.value == "Default Notice Preview" for subheader in app_test.subheader)
    app_test.sidebar.radio[0].set_value("Data Intake").run()
    assert any(button.label == "Restore official cached data" for button in app_test.button)


def test_dashboard_smoke_command_writes_result(tmp_path):
    output = tmp_path / "dashboard_smoke.json"
    result = run_dashboard_smoke(output=output, timeout=60)
    assert result["passed"] is True
    assert result["page_count"] == 10
    assert output.exists()
