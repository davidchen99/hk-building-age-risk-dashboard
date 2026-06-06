from __future__ import annotations

import html
from pathlib import Path

from src.reports.markdown_report import render_markdown_report
from src.utils.config import REPORTS_DIR, ensure_dirs


def render_html_report(payload: dict, summary: str, title: str = "Hong Kong Building Asset Age Risk Report") -> str:
    md = render_markdown_report(payload, summary, title=title)
    lines = []
    in_list = False
    in_pre = False

    def close_blocks() -> None:
        nonlocal in_list, in_pre
        if in_list:
            lines.append("</ul>")
            in_list = False
        if in_pre:
            lines.append("</pre>")
            in_pre = False

    for line in md.splitlines():
        escaped = html.escape(line)
        if line.startswith("|"):
            if in_list:
                lines.append("</ul>")
                in_list = False
            if not in_pre:
                lines.append("<pre class='md-table'>")
                in_pre = True
            lines.append(escaped)
        elif line.startswith("# "):
            close_blocks()
            lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_blocks()
            lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            close_blocks()
            lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if in_pre:
                lines.append("</pre>")
                in_pre = False
            if not in_list:
                lines.append("<ul>")
                in_list = True
            lines.append(f"<li>{html.escape(line[2:])}</li>")
        elif not line.strip():
            close_blocks()
        else:
            close_blocks()
            lines.append(f"<p>{escaped}</p>")
    close_blocks()
    content = "\n".join(lines)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;max-width:1040px;margin:32px auto;line-height:1.55;color:#1f2937}"
        "h1,h2,h3{color:#111827}li{margin:4px 0}"
        ".md-table{background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:12px;overflow:auto}"
        "</style></head><body>"
        + content
        + "</body></html>"
    )


def save_html_report(payload: dict, summary: str, title: str = "Hong Kong Building Asset Age Risk Report") -> Path:
    ensure_dirs()
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"report_{timestamp}.html"
    path.write_text(render_html_report(payload, summary, title=title), encoding="utf-8")
    return path
