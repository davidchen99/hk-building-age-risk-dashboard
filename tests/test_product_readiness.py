from src.pipeline.product_readiness import _render_markdown, build_readiness_steps


def test_product_readiness_steps_include_release_gates():
    names = [step.name for step in build_readiness_steps()]
    assert names == [
        "compile",
        "pytest",
        "build_all",
        "validate_outputs",
        "generate_scenario_reports",
        "dashboard_smoke",
        "acceptance_check",
    ]


def test_product_readiness_markdown_renderer():
    report = _render_markdown(
        {
            "passed": True,
            "generated_at": "2026-01-01T00:00:00+08:00",
            "duration_seconds": 1.2,
            "steps": [
                {
                    "name": "compile",
                    "passed": True,
                    "returncode": 0,
                    "duration_seconds": 1.2,
                    "command": ["python", "-m", "compileall"],
                    "stdout_tail": "ok",
                    "stderr_tail": "",
                }
            ],
            "errors": [],
        }
    )
    assert "Product Readiness Report" in report
    assert "| compile | True | 0 |" in report
    assert "- None" in report
