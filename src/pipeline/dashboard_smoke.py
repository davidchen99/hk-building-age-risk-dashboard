from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from src.utils.config import EXPORTS_DIR, PROJECT_ROOT, ensure_dirs, log, now_iso

CORE_PAGES = [
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


def run_dashboard_smoke(output: Path | None = None, timeout: int = 60) -> dict[str, Any]:
    ensure_dirs()
    app_test = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=timeout)
    app_test.run()
    page_results = []
    errors: list[str] = []
    if app_test.exception:
        errors.append(f"Initial app load raised {len(app_test.exception)} exception(s)")
    if not app_test.sidebar.radio:
        errors.append("Sidebar page radio was not found")
        result = {
            "generated_at": now_iso(),
            "passed": False,
            "page_count": len(CORE_PAGES),
            "pages": page_results,
            "errors": errors,
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log(json.dumps({"dashboard_smoke_passed": False, "errors": errors}, ensure_ascii=False))
        raise RuntimeError("; ".join(errors))
    for page in CORE_PAGES:
        app_test.sidebar.radio[0].set_value(page).run()
        exception_count = len(app_test.exception)
        headers = [header.value for header in app_test.header]
        error_messages = [str(getattr(error, "value", error)) for error in getattr(app_test, "error", [])]
        page_errors = []
        if exception_count:
            page_errors.append(f"{exception_count} Streamlit exception(s)")
        if error_messages:
            page_errors.append(f"Streamlit error element(s): {'; '.join(error_messages)}")
        if page not in headers:
            page_errors.append(f"Expected header '{page}' not found")
        page_results.append(
            {
                "page": page,
                "passed": not page_errors,
                "headers": headers,
                "exception_count": exception_count,
                "error_messages": error_messages,
                "errors": page_errors,
            }
        )
        errors.extend([f"{page}: {error}" for error in page_errors])
    result = {
        "generated_at": now_iso(),
        "passed": not errors,
        "page_count": len(CORE_PAGES),
        "pages": page_results,
        "errors": errors,
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps({"dashboard_smoke_passed": result["passed"], "errors": errors}, ensure_ascii=False))
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/exports/dashboard_smoke.json")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(run_dashboard_smoke(Path(args.output) if args.output else None, timeout=args.timeout), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
