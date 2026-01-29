from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class AppConfig:
    openai_api_key: str | None
    anthropic_api_key: str | None
    openrouter_api_key: str | None
    mock_mode: bool

    @classmethod
    def load(cls) -> "AppConfig":
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        mock_mode = os.getenv("MOCK_MODE", "").lower() == "true" or not (openai_key or anthropic_key or openrouter_key)
        return cls(openai_key, anthropic_key, openrouter_key, mock_mode)


class DeterministicLLM:
    """
    Minimal deterministic LLM stub used when no API key is present.
    Returns short, schema-friendly strings so Pydantic parsing succeeds.
    """

    def __init__(self) -> None:
        self.name = "deterministic-mock"

    def _render_message(self, messages: List[Dict[str, str]]) -> str:
        # Take last user message as basis
        last = messages[-1]["content"] if messages else ""
        if "ObserverAnalysis" in last:
            return (
                '{"detected_intent": "NORMAL_ANSWER", "answer_score": 2, '
                '"correctness":"PARTIALLY_CORRECT","key_strengths":["clear"],'
                '"key_gaps":["missing complexity"],"hallucination_flags":[],'
                '"recommended_followup":"Ask about edge cases", "difficulty_delta":0,'
                '"internal_memo":"Keep steady, probe depth"}'
            )
        if "InterviewerPlan" in last:
            return (
                '{"next_action":"ASK_QUESTION","next_question":"Расскажите про сложность бинарного поиска?",'
                '"topic":"algorithms","difficulty":2,"internal_memo":"Stay neutral"}'
            )
        if "FinalFeedback" in last:
            return (
                '{"decision":{"grade":"Middle","hiring_recommendation":"Hire","confidence_score":70},'
                '"hard_skills":{"confirmed_skills":[{"topic":"Python","evidence":"solid answers"}],'
                '"knowledge_gaps":[{"topic":"Concurrency","what_went_wrong":"shallow","correct_answer":"Use asyncio event loop",'
                '"resources":["https://docs.python.org/3/library/asyncio.html"]}]},'
                '"soft_skills":{"clarity":"Good","honesty":"High","engagement":"Engaged"},'
                '"roadmap":{"next_steps":["Deepen concurrency"],"resources":["https://docs.python.org/3/"]}}'
            )
        return "Okay."

    def chat_completion(self, messages: List[Dict[str, str]], **_: Any) -> Any:
        class Resp:
            def __init__(self, content: str) -> None:
                self.content = content

        return Resp(self._render_message(messages))

    def __call__(self, messages: List[Dict[str, str]], **kwargs: Any) -> Any:
        return self.chat_completion(messages, **kwargs)


def get_llm():
    config = AppConfig.load()
    if config.mock_mode:
        return DeterministicLLM(), config
    try:
        from crewai import LLM

        # Prefer OpenAI by default; CrewAI will pick provider based on env.
        model = os.getenv("MODEL_NAME", "gpt-4o-mini")
        if config.openrouter_api_key:
            # OpenRouter is OpenAI-compatible. Explicitly pass api_key and base_url,
            # and set env vars so provider detection won't require OPENAI_API_KEY.
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            model = os.getenv("OPENROUTER_MODEL", model)
            os.environ.setdefault("OPENAI_API_KEY", config.openrouter_api_key)
            os.environ.setdefault("OPENAI_BASE_URL", base_url)
            return LLM(model=model, api_key=config.openrouter_api_key, base_url=base_url, provider="openai"), config
        return LLM(model=model), config
    except Exception:
        # Fallback to deterministic stub to prevent crashes in offline mode.
        return DeterministicLLM(), config
