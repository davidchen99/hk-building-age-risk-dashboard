from __future__ import annotations


BLOCKED_PHRASES = [
    "正式结构安全鉴定",
    "dangerous building",
    "must be demolished",
    "必须拆除",
]


def validate_summary_text(text: str) -> tuple[bool, list[str]]:
    issues = []
    lowered = text.lower()
    for phrase in BLOCKED_PHRASES:
        if phrase.lower() in lowered:
            issues.append(f"Unsupported or over-strong phrase: {phrase}")
    if "structural inspection" not in lowered and "结构安全鉴定" not in text and "正式结构" not in text:
        issues.append("Missing limitation statement about structural inspection.")
    return not issues, issues
