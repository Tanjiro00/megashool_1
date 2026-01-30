from __future__ import annotations

import re
from typing import List

from .schemas import ConversationTurn, Intent, ObserverAnalysis, SessionState

STOP_PHRASES = {
    "стоп интервью",
    "стоп игра",
    "стоп игра. давай фидбэк",
    "давай фидбэк",
    "stop",
    "/stop",
}
PROGRESS_PHRASES = {"прогресс", "progress", "/progress"}
ROLE_REVERSAL_HINTS = {"а ты", "а вы", "что ты думаешь", "твое мнение", "ваше мнение", "ты мне скажи"}
OFF_TOPIC_HINTS = {
    "кот",
    "кошка",
    "собака",
    "песня",
    "шутка",
    "анекдот",
    "погода",
    "фильм",
    "кино",
    "сериал",
    "игра",
    "игры",
    "футбол",
    "хоккей",
    "гороскоп",
    "политика",
    "новости",
    "путешествие",
    "еда",
    "рецепт",
}
PROMPT_INJECTION_HINTS = {
    "ignore",
    "игнорируй",
    "перестань следовать",
    "забудь инструкции",
    "забудь правила",
    "забудь что ты",
    "disregard",
    "forget previous",
    "system prompt",
    "ты больше не",
    "pretend you are",
    "imitate",
    "override",
    "промпт",
}
CONTROVERSIAL_MARKERS = {
    "всегда",
    "никогда",
    "100%",
    "гарантированно",
    "точно",
    "без исключений",
    "уберут",
    "запретят",
    "не нужен",
    "не существует",
    "никто не",
    "все знают",
    "python 4.0",
}
ROLE_CONTEXT_KEYWORDS = {"компания", "компании", "задачи", "команда", "проект", "роль", "продукт", "испытательный"}
HONESTY_HINTS = {
    "не знаю",
    "не уверен",
    "не помню",
    "затрудняюсь",
    "not sure",
    "don't know",
    "no idea",
    "can't recall",
}


def classify_intent(user_message: str) -> Intent:
    text = re.sub(r"[.!?]", "", user_message.lower()).strip()
    if any(p in text for p in STOP_PHRASES):
        return Intent.STOP
    if any(p in text for p in PROGRESS_PHRASES):
        return Intent.PROGRESS
    if detect_role_reversal_request(user_message) or any(h in text for h in ROLE_REVERSAL_HINTS):
        return Intent.ROLE_REVERSAL
    if any(h in text for h in OFF_TOPIC_HINTS):
        return Intent.OFF_TOPIC
    return Intent.NORMAL_ANSWER


def detect_role_reversal_request(user_message: str) -> bool:
    text = user_message.lower()
    if not any(k in text for k in ROLE_CONTEXT_KEYWORDS):
        return False
    if "?" in text:
        return True
    return bool(re.search(r"\b(расскаж|расскажите|опиши|опишите|поделис|что за|какая|какой|какие|сколько|где|кто)\b", text))


def detect_off_topic_context(
    user_message: str,
    last_question: str,
    topic_keywords: list[str] | None = None,
) -> bool:
    """
    Heuristic context-aware off-topic detector.
    Flags messages that contain off-topic cues and lack overlap with the current topic/question.
    """
    text = user_message.lower()
    # Honest admission is not off-topic
    if detect_honesty(user_message):
        return False
    # Short greetings or empty replies are handled elsewhere
    words = {w for w in re.findall(r"[a-zа-яё0-9]{3,}", text)}
    if not words:
        return False

    # Hard off-topic cues
    if words & OFF_TOPIC_HINTS:
        return True

    # Company/role questions should not be treated as off-topic
    if words & ROLE_CONTEXT_KEYWORDS:
        return False

    topic_keywords = [k.lower() for k in (topic_keywords or []) if k]
    question_words = {w for w in re.findall(r"[a-zа-яё0-9]{3,}", last_question.lower())}
    topic_words = set(topic_keywords) | question_words

    # If we have topic context, require some overlap
    if topic_words:
        overlap = words & topic_words
        if overlap:
            return False
        # No overlap + presence of generic small-talk markers => off-topic
        small_talk = {"как дела", "добрый", "привет", "здоров", "хаю", "окей", "ок ", "ага"}
        if any(marker in text for marker in small_talk):
            return True

    return False


def detect_prompt_injection(user_message: str) -> bool:
    text = user_message.lower()
    return any(hint in text for hint in PROMPT_INJECTION_HINTS)


def detect_controversial_claim(user_message: str) -> bool:
    text = user_message.lower()
    # quick exit on question form
    if "?" in text:
        return False
    if any(marker in text for marker in CONTROVERSIAL_MARKERS):
        return True
    # absolute statements with "все / никто / всегда / никогда" patterns
    if re.search(r"\b(все|никто)\b.+\b(могут|умеют|делают|работает)\b", text):
        return True
    return False


def detect_honesty(user_message: str) -> bool:
    text = user_message.lower()
    return any(h in text for h in HONESTY_HINTS)


def detect_hallucination(user_message: str) -> bool:
    trap = "python 4.0" in user_message.lower() and "for" in user_message.lower()
    obviously_false = "уберут for" in user_message.lower()
    return trap or obviously_false


def update_difficulty(state: SessionState, analysis: ObserverAnalysis) -> int:
    scores = state.recent_scores[-1:] + [analysis.answer_score]
    state.recent_scores.append(analysis.answer_score)
    state.recent_scores = state.recent_scores[-3:]

    delta = analysis.difficulty_delta
    if len(scores) >= 2:
        if scores[-1] >= 3 and scores[-2] >= 3:
            delta = max(delta, 1)
        if scores[-1] <= 1 and scores[-2] <= 1:
            delta = min(delta, -1)
    new_level = max(1, min(5, state.difficulty + delta))
    return new_level


def extract_facts(state: SessionState, last_question: str, user_message: str) -> List[str]:
    snippets: List[str] = []
    sentences = re.split(r"[.!?]", user_message)
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s.split()) >= 3:
            snippets.append(s)
    for sn in snippets:
        if sn not in state.extracted_facts:
            state.extracted_facts.append(sn)
    return snippets


def update_summary(state: SessionState, last_question: str, user_message: str) -> None:
    recent = state.remember_recent(3)
    summary_parts = [f"Q{t.turn_id}:{t.agent_visible_message[:50]} | A:{t.user_message[:60]}" for t in recent]
    state.running_summary = " || ".join(summary_parts)


def question_already_covered(state: SessionState, next_question: str) -> bool:
    normalized = next_question.lower().strip()
    for turn in state.history:
        if normalized in turn.agent_visible_message.lower():
            return True
    for fact in state.extracted_facts:
        if normalized and normalized.split(" ")[0] in fact.lower():
            return True
    return False


def register_turn(state: SessionState, turn: ConversationTurn) -> None:
    state.history.append(turn)
    update_summary(state, turn.agent_visible_message, turn.user_message)
