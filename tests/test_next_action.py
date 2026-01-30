from interview_coach.main import _ensure_analysis_object, _resolve_question_text
from interview_coach.schemas import InterviewerPlan, NextAction, Intent, Correctness


def test_resolve_question_uses_redirect_prefix():
    plan = InterviewerPlan(
        next_action=NextAction.REDIRECT_AND_ASK,
        next_question="Расскажите про индексы в SQL.",
        topic="DB",
        topic_id="db_sql_basics",
        difficulty=2,
        internal_memo="redirect",
    )
    msg = _resolve_question_text("Okay.", plan, "Расскажи анекдот", "Запасной вопрос")
    assert "верн" in msg.lower()
    assert "sql" in msg.lower()


def test_analysis_fallback_on_bad_json():
    analysis = _ensure_analysis_object("невалидный json", fallback_topic_id="python_basics")
    assert analysis.detected_intent == Intent.NORMAL_ANSWER
    assert analysis.correctness == Correctness.UNKNOWN
    assert analysis.topic_id == "python_basics"
