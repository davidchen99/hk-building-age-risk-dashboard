from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import EXPORTS_DIR, PROJECT_ROOT, ensure_dirs, log, now_iso


@dataclass(frozen=True)
class ReadinessStep:
    name: str
    command: list[str]
    timeout_seconds: int


def build_readiness_steps(skip_tests: bool = False, skip_build: bool = False) -> list[ReadinessStep]:
    python = sys.executable
    steps = [
        ReadinessStep("compile", [python, "-m", "compileall", "app.py", "src", "tests"], 120),
    ]
    if not skip_tests:
        steps.append(ReadinessStep("pytest", [python, "-m", "pytest"], 300))
    if not skip_build:
        steps.append(ReadinessStep("build_all", [python, "-m", "src.pipeline.build_all", "--use-cache", "--analysis-year", "2026"], 360))
    steps.extend(
        [
            ReadinessStep("validate_outputs", [python, "-m", "src.pipeline.validate_outputs"], 120),
            ReadinessStep("generate_scenario_reports", [python, "-m", "src.pipeline.generate_scenario_reports"], 180),
            ReadinessStep("dashboard_smoke", [python, "-m", "src.pipeline.dashboard_smoke"], 240),
            ReadinessStep("acceptance_check", [python, "-m", "src.pipeline.acceptance_check"], 300),
        ]
    )
    return steps


def _tail(text: str, max_chars: int = 12_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _run_step(step: ReadinessStep) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            step.command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=step.timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - started
        return {
            "name": step.name,
            "command": step.command,
            "timeout_seconds": step.timeout_seconds,
            "returncode": completed.returncode,
            "duration_seconds": round(duration, 2),
            "passed": completed.returncode == 0,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        return {
            "name": step.name,
            "command": step.command,
            "timeout_seconds": step.timeout_seconds,
            "returncode": None,
            "duration_seconds": round(duration, 2),
            "passed": False,
            "stdout_tail": _tail(exc.stdout or ""),
            "stderr_tail": _tail(exc.stderr or ""),
            "error": f"Timed out after {step.timeout_seconds} seconds",
        }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Product Readiness Report",
        "",
        f"- Passed: {result.get('passed')}",
        f"- Generated at: {result.get('generated_at')}",
        f"- Duration seconds: {result.get('duration_seconds')}",
        "",
        "## Steps",
        "",
        "| Step | Passed | Return code | Seconds | Command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in result.get("steps", []):
        command = " ".join(step.get("command", []))
        lines.append(
            f"| {step.get('name')} | {step.get('passed')} | {step.get('returncode')} | "
            f"{step.get('duration_seconds')} | `{command}` |"
        )
    lines.extend(["", "## Errors", ""])
    errors = result.get("errors", [])
    if errors:
        lines.extend([f"- {error}" for error in errors])
    else:
        lines.append("- None")
    lines.extend(["", "## Output Tails", ""])
    for step in result.get("steps", []):
        lines.extend(
            [
                f"### {step.get('name')}",
                "",
                "Stdout tail:",
                "",
                "```text",
                step.get("stdout_tail", "").strip() or "(empty)",
                "```",
                "",
                "Stderr tail:",
                "",
                "```text",
                step.get("stderr_tail", "").strip() or "(empty)",
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def run_product_readiness(
    output: Path | None = None,
    markdown_output: Path | None = None,
    skip_tests: bool = False,
    skip_build: bool = False,
) -> dict[str, Any]:
    ensure_dirs()
    output = output or (EXPORTS_DIR / "product_readiness.json")
    markdown_output = markdown_output or (EXPORTS_DIR / "product_readiness.md")
    started = time.perf_counter()
    step_results = []
    errors: list[str] = []
    for step in build_readiness_steps(skip_tests=skip_tests, skip_build=skip_build):
        log(f"Product readiness step started: {step.name}")
        result = _run_step(step)
        step_results.append(result)
        if not result["passed"]:
            errors.append(f"{step.name} failed")
            log(json.dumps({"product_readiness_step": step.name, "passed": False}, ensure_ascii=False))
            break
        log(json.dumps({"product_readiness_step": step.name, "passed": True, "duration_seconds": result["duration_seconds"]}, ensure_ascii=False))
    readiness = {
        "generated_at": now_iso(),
        "passed": not errors,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "steps": step_results,
        "errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_render_markdown(readiness), encoding="utf-8")
    log(json.dumps({"product_readiness_passed": readiness["passed"], "errors": errors}, ensure_ascii=False))
    if errors:
        raise RuntimeError("; ".join(errors))
    return readiness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/exports/product_readiness.json")
    parser.add_argument("--markdown-output", default="outputs/exports/product_readiness.md")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_product_readiness(
                Path(args.output) if args.output else None,
                Path(args.markdown_output) if args.markdown_output else None,
                skip_tests=args.skip_tests,
                skip_build=args.skip_build,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
