from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.utils.config import CACHE_DIR, ensure_dirs

LLM_SETTINGS_PATH = CACHE_DIR / "llm_settings.json"

DEFAULT_LLM_SETTINGS = {
    "provider": "Template",
    "model": "",
    "base_url": "",
    "api_key": "",
    "last_test_status": "Not tested",
    "last_test_error": "",
}


def load_llm_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or LLM_SETTINGS_PATH
    if not settings_path.exists():
        return _settings_from_env()
    try:
        stored = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        stored = {}
    return {**DEFAULT_LLM_SETTINGS, **_settings_from_env(), **stored}


def save_llm_settings(settings: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    ensure_dirs()
    settings_path = path or LLM_SETTINGS_PATH
    payload = {**DEFAULT_LLM_SETTINGS, **settings}
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def masked_key(api_key: str | None) -> str:
    value = api_key or ""
    if not value:
        return "Not configured"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _settings_from_env() -> dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "").strip() or "Template"
    return {
        "provider": provider,
        "model": os.getenv("OPENAI_MODEL", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }


def connection_status(settings: dict[str, Any]) -> dict[str, str]:
    provider = settings.get("provider", "Template")
    if provider == "Template":
        return {"status": "Ready", "detail": "Template mode does not require an API key."}
    if not settings.get("api_key"):
        return {"status": "Missing API key", "detail": f"{provider} requires an API key."}
    return {"status": "Configured", "detail": f"{provider} key {masked_key(settings.get('api_key'))}"}


def provider_defaults(provider: str) -> dict[str, str]:
    if provider == "DeepSeek":
        return {"model": "deepseek-chat", "base_url": "https://api.deepseek.com"}
    if provider == "OpenAI":
        return {"model": "gpt-4.1-mini", "base_url": ""}
    if provider == "Local":
        return {"model": "local-model", "base_url": "http://localhost:8000/v1"}
    return {"model": "", "base_url": ""}
