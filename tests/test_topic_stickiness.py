from interview_coach.main import _maybe_stay_on_topic
from interview_coach.topics import ProgressTracker, build_topic_plan, record_progress
from interview_coach.schemas import SessionState


def test_stay_on_topic_until_covered():
    plan = build_topic_plan("Backend", "Junior", "")
    tracker = ProgressTracker.from_plan(plan)
    state = SessionState(
        participant_name="t",
        position="p",
        grade="Junior",
        experience="1y",
        topic_plan=plan,
        progress=tracker,
    )
    topic_id = plan.topics[0].id
    # after one high-score answer (min_questions=2) topic isn't covered yet
    record_progress(plan, tracker, topic_id, turn_id=1, question="Q1", score=4, difficulty=2)
    stay = _maybe_stay_on_topic(state, topic_id)
    assert stay is not None
    assert stay.topic.id == topic_id
