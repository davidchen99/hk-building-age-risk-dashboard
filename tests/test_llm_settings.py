from src.ai.llm_settings import connection_status, load_llm_settings, masked_key, save_llm_settings


def test_llm_settings_round_trip(tmp_path):
    path = tmp_path / "llm_settings.json"
    saved = save_llm_settings(
        {
            "provider": "DeepSeek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test-123456",
        },
        path=path,
    )
    loaded = load_llm_settings(path=path)
    assert saved["provider"] == "DeepSeek"
    assert loaded["model"] == "deepseek-chat"
    assert loaded["api_key"] == "sk-test-123456"
    assert connection_status(loaded)["status"] == "Configured"


def test_masked_key_does_not_expose_full_secret():
    assert masked_key("") == "Not configured"
    assert masked_key("1234567890") == "1234...7890"
