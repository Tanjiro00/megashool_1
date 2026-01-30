from interview_coach.main import compute_confidence
from interview_coach.schemas import SessionState
from interview_coach.topics import ProgressTracker, TopicPlan, TopicRules, Topic


def make_state(must_cov: float, overall_cov: float, hallu: bool = False, honesty: int = 0, threshold: float = 0.7) -> SessionState:
    dummy_topic = Topic(id="t1", name="T1", priority="must")
    plan = TopicPlan(role="r", grade="g", topics=[dummy_topic], rules=TopicRules(target_must_coverage=0.85))
    tracker = ProgressTracker.from_plan(plan)
    tracker.must_coverage = must_cov
    tracker.overall_coverage = overall_cov
    state = SessionState(
        participant_name="x",
        position="p",
        grade="g",
        experience="e",
        topic_plan=plan,
        progress=tracker,
        coverage_threshold=threshold,
    )
    state.hallucination_detected = hallu
    state.honesty_count = honesty
    return state


def test_confidence_good_coverage_bonus_honesty():
    state = make_state(0.9, 0.9, hallu=False, honesty=2)
    score = compute_confidence(state)
    assert 90 <= score <= 100
    assert score >= 90  # honesty gives small boost


def test_confidence_penalizes_hallucination_and_low_must():
    state = make_state(0.6, 0.7, hallu=True, honesty=0)
    score = compute_confidence(state)
    # base 70 - penalties (20+15+10) = 25 -> clipped
    assert score <= 40


def test_confidence_low_overall_threshold():
    state = make_state(0.8, 0.65, hallu=False, honesty=0, threshold=0.7)
    score = compute_confidence(state)
    assert score < 70
