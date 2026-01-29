from __future__ import annotations

import re
from typing import List

from .schemas import ConversationTurn, Intent, ObserverAnalysis, SessionState


STOP_PHRASES = {"стоп интервью", "стоп игра", "давай фидбэк", "stop", "/stop"}
ROLE_REVERSAL_HINTS = {"а ты", "а вы", "что ты думаешь", "твое мнение", "ваше мнение"}
OFF_TOPIC_HINTS = {"кот", "песня", "шутка", "погода", "игра", "анекдот"}


def classify_intent(user_message: str) -> Intent:
    text = user_message.lower().strip()
    if any(p in text for p in STOP_PHRASES):
        return Intent.STOP
    if any(h in text for h in ROLE_REVERSAL_HINTS) or text.endswith("?"):
        return Intent.ROLE_REVERSAL
    if any(h in text for h in OFF_TOPIC_HINTS):
        return Intent.OFF_TOPIC
    return Intent.NORMAL_ANSWER


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

