import json
from pathlib import Path

from interview_coach.logic import classify_intent, detect_hallucination, update_difficulty
from interview_coach.schemas import Intent, ObserverAnalysis, SessionState, Correctness


def test_intent_routing():
    assert classify_intent("Стоп интервью") == Intent.STOP
    assert classify_intent("А ты любишь Rust?") == Intent.ROLE_REVERSAL
    assert classify_intent("Расскажи анекдот") == Intent.OFF_TOPIC
    assert classify_intent("Окей") == Intent.NORMAL_ANSWER


def test_hallucination_trap():
    assert detect_hallucination("Python 4.0 уберут for") is True
    assert detect_hallucination("Python 3 forever") is False


def test_adaptivity_rules():
    state = SessionState(participant_name="t", position="p", grade="Junior", experience="1y")
    a1 = ObserverAnalysis(
        detected_intent=Intent.NORMAL_ANSWER,
        answer_score=3,
        correctness=Correctness.CORRECT,
        key_strengths=[],
        key_gaps=[],
        hallucination_flags=[],
        recommended_followup="",
        difficulty_delta=0,
        internal_memo="ok",
    )
    lvl1 = update_difficulty(state, a1)
    assert lvl1 >= 2
    a2 = ObserverAnalysis(
        detected_intent=Intent.NORMAL_ANSWER,
        answer_score=4,
        correctness=Correctness.CORRECT,
        key_strengths=[],
        key_gaps=[],
        hallucination_flags=[],
        recommended_followup="",
        difficulty_delta=0,
        internal_memo="ok",
    )
    lvl2 = update_difficulty(state, a2)
    assert lvl2 >= lvl1  # should climb after two good answers
