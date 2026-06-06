from __future__ import annotations

import os

from src.ai.llm_settings import load_llm_settings
from src.ai.prompt_builder import build_prompt


def _client_config(settings: dict | None = None) -> dict:
    configured = settings or load_llm_settings()
    provider = configured.get("provider", "Template")
    api_key = configured.get("api_key") or os.getenv("OPENAI_API_KEY")
    model = configured.get("model") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = configured.get("base_url") or os.getenv("OPENAI_BASE_URL") or None
    return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}


def generate_llm_summary(payload: dict, language: str = "zh", settings: dict | None = None) -> str | None:
    config = _client_config(settings)
    if config["provider"] == "Template":
        return None
    api_key = config["api_key"]
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client_kwargs = {"api_key": api_key}
        if config["base_url"]:
            client_kwargs["base_url"] = config["base_url"]
        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": build_prompt(payload, language=language)}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def test_llm_connection(settings: dict | None = None) -> tuple[bool, str]:
    config = _client_config(settings)
    if config["provider"] == "Template":
        return True, "Template mode is ready."
    if not config["api_key"]:
        return False, f"{config['provider']} API key is missing."
    try:
        from openai import OpenAI

        client_kwargs = {"api_key": config["api_key"]}
        if config["base_url"]:
            client_kwargs["base_url"] = config["base_url"]
        client = OpenAI(**client_kwargs)
        client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": "Return only: ok"}],
            max_tokens=5,
            temperature=0,
        )
        return True, f"{config['provider']} connection succeeded."
    except Exception as exc:
        return False, str(exc)
