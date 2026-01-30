from interview_coach.topics import ProgressTracker, build_topic_plan, record_progress


def test_build_topic_plan_backend_junior():
    plan = build_topic_plan("Backend", "Junior", "немного SQL")
    must_ids = {t.id for t in plan.topics if t.priority == "must"}
    expected = {
        "python_basics",
        "oop_principles",
        "http_rest",
        "db_sql_basics",
        "git_basics",
        "django_framework",
        "debug_testing",
    }
    assert expected.issubset(must_ids)


def test_progress_marks_topic_covered():
    plan = build_topic_plan("Backend", "Junior", "")
    tracker = ProgressTracker.from_plan(plan)
    topic_id = plan.topics[0].id
    record_progress(plan, tracker, topic_id, turn_id=1, question="Test", score=4, difficulty=2)
    topic = next(t for t in plan.topics if t.id == topic_id)
    assert topic.status in {"pending", "in_progress"}
    # second high-quality answer should cover the must-topic (min_questions >=2)
    record_progress(plan, tracker, topic_id, turn_id=2, question="Test2", score=4, difficulty=2)
    assert topic.status == "covered"
    assert topic.coverage_score >= tracker.coverage_threshold
