import os
from importlib import reload

import interview_coach.config as config_module


def test_openrouter_key_in_openai_env_sets_base_url(monkeypatch):
    # simulate user putting OpenRouter key into OPENAI_API_KEY only
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-123456789")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    reload(config_module)
    # calling get_llm should apply heuristic: treat sk-or- key as OpenRouter
    _, cfg_after = config_module.get_llm()
    assert cfg_after.openrouter_api_key == "sk-or-123456789"
    assert os.getenv("OPENAI_BASE_URL", "").startswith("https://openrouter.ai")
    # cleanup
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
