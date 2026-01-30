from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from .topic_catalog import get_backend_topics_for_grade

Priority = Literal["must", "nice"]
Status = Literal["pending", "in_progress", "covered", "skipped"]


class Topic(BaseModel):
    id: str
    name: str
    priority: Priority
    min_questions: int = 1
    tags: List[str] = Field(default_factory=list)
    status: Status = "pending"
    coverage_score: float = 0.0


class TopicRules(BaseModel):
    target_must_coverage: float = 0.85
    max_total_turns: int = 12
    topic_cooldown: int = 2


class TopicPlan(BaseModel):
    role: str
    grade: str
    topics: List[Topic]
    rules: TopicRules
    summary: str = ""


class AskedQuestion(BaseModel):
    turn_id: int
    question: str
    topic_id: str
    difficulty: int


class TopicStats(BaseModel):
    asked: int = 0
    avg_score: float = 0.0  # normalized 0..1
    last_turn: int = -1


class ProgressTracker(BaseModel):
    asked_questions: List[AskedQuestion] = Field(default_factory=list)
    topic_stats: Dict[str, TopicStats] = Field(default_factory=dict)
    overall_coverage: float = 0.0
    must_coverage: float = 0.0
    nice_coverage: float = 0.0
    coverage_threshold: float = 0.7

    @classmethod
    def from_plan(cls, plan: TopicPlan, coverage_threshold: float = 0.7) -> "ProgressTracker":
        stats = {t.id: TopicStats() for t in plan.topics}
        return cls(topic_stats=stats, coverage_threshold=coverage_threshold)


class TopicSelection(BaseModel):
    topic: Topic
    reason: str
    desired_difficulty: int


# ---------- Plan builder ----------

def build_topic_plan(role: str, grade: str, experience_text: str) -> TopicPlan:
    """Construct a topic plan using simple role/grade heuristics (offline)."""
    role_l = role.lower()
    grade_l = grade.lower()
    base_topics = get_backend_topics_for_grade(grade)

    topics = [Topic(**t) for t in base_topics]

    exp_l = experience_text.lower()
    summary_bits: List[str] = []

    if "django" in exp_l or "drf" in exp_l or "orm" in exp_l:
        for t in topics:
            if t.id == "django_framework":
                t.min_questions = max(t.min_questions, 2)
                t.priority = "must"
        summary_bits.append("усилить Django/ORM")

    if "sql" in exp_l and "немного" in exp_l:
        summary_bits.append("SQL с базовых вопросов")

    if grade_l == "junior":
        rules = TopicRules(target_must_coverage=0.85, max_total_turns=10, topic_cooldown=1)
    elif grade_l == "middle":
        rules = TopicRules(target_must_coverage=0.9, max_total_turns=14, topic_cooldown=2)
    else:
        rules = TopicRules(target_must_coverage=0.92, max_total_turns=16, topic_cooldown=2)

    names = ", ".join(t.name for t in topics if t.priority == "must")
    summary = f"План must-тем: {names}." if names else ""
    if summary_bits:
        summary += " Адаптации: " + "; ".join(summary_bits)

    return TopicPlan(role=role, grade=grade, topics=topics, rules=rules, summary=summary)


# ---------- Progress + coverage ----------

def _normalize_score(score: int | float) -> float:
    return max(0.0, min(float(score), 4.0)) / 4.0


def _get_stats(tracker: ProgressTracker, topic_id: str) -> TopicStats:
    if topic_id not in tracker.topic_stats:
        tracker.topic_stats[topic_id] = TopicStats()
    return tracker.topic_stats[topic_id]


def recalc_coverage(plan: TopicPlan, tracker: ProgressTracker) -> None:
    must_scores: List[float] = []
    nice_scores: List[float] = []
    for topic in plan.topics:
        stats = tracker.topic_stats.get(topic.id, TopicStats())
        completion = min(stats.asked / max(topic.min_questions, 1), 1.0)
        coverage = completion * max(0.0, min(stats.avg_score, 1.0))
        topic.coverage_score = coverage
        if stats.asked > 0 and topic.status == "pending":
            topic.status = "in_progress"
        if topic.status != "covered" and stats.asked >= topic.min_questions and stats.avg_score >= tracker.coverage_threshold:
            topic.status = "covered"
        if topic.priority == "must":
            must_scores.append(coverage)
        else:
            nice_scores.append(coverage)
    if must_scores:
        tracker.must_coverage = sum(must_scores) / len(must_scores)
    if nice_scores:
        tracker.nice_coverage = sum(nice_scores) / len(nice_scores)
    all_scores = must_scores + nice_scores
    if all_scores:
        tracker.overall_coverage = sum(all_scores) / len(all_scores)


def record_progress(
    plan: TopicPlan,
    tracker: ProgressTracker,
    topic_id: str,
    turn_id: int,
    question: str,
    score: int | float,
    difficulty: int,
) -> None:
    stats = _get_stats(tracker, topic_id)
    normalized = _normalize_score(score)
    stats.asked += 1
    stats.avg_score = ((stats.avg_score * (stats.asked - 1)) + normalized) / stats.asked
    stats.last_turn = turn_id
    tracker.asked_questions.append(AskedQuestion(turn_id=turn_id, question=question, topic_id=topic_id, difficulty=difficulty))
    recalc_coverage(plan, tracker)


# ---------- Topic selection ----------

def _eligible_topics(plan: TopicPlan, tracker: ProgressTracker, current_turn: int) -> List[Topic]:
    eligible: List[Topic] = []
    for topic in plan.topics:
        stats = tracker.topic_stats.get(topic.id, TopicStats())
        on_cooldown = (
            topic.status == "covered"
            and plan.rules.topic_cooldown > 0
            and stats.last_turn >= 0
            and (current_turn - stats.last_turn) <= plan.rules.topic_cooldown
        )
        if on_cooldown:
            continue
        eligible.append(topic)
    return eligible


def _topic_sort_key(topic: Topic, tracker: ProgressTracker) -> Tuple:
    stats = tracker.topic_stats.get(topic.id, TopicStats())
    completion = stats.asked / max(topic.min_questions, 1)
    return (
        0 if topic.priority == "must" else 1,
        completion,
        stats.avg_score,
        stats.last_turn if stats.last_turn >= 0 else -999,
    )


def suggest_difficulty(base_difficulty: int, stats: TopicStats) -> int:
    if stats.asked == 0:
        return base_difficulty
    if stats.avg_score >= 0.75:
        return min(5, base_difficulty + 1)
    if stats.avg_score <= 0.4:
        return max(1, base_difficulty - 1)
    return base_difficulty


def select_next_topic(plan: TopicPlan, tracker: ProgressTracker, current_turn: int, base_difficulty: int) -> TopicSelection:
    eligible = _eligible_topics(plan, tracker, current_turn)
    if not eligible:
        eligible = plan.topics  # fallback if everything on cooldown

    must_target = plan.rules.target_must_coverage
    must_need = tracker.must_coverage < must_target

    must_candidates = [t for t in eligible if t.priority == "must" and t.status in {"pending", "in_progress"}]
    pool = must_candidates if must_need and must_candidates else eligible

    sorted_pool = sorted(pool, key=lambda t: _topic_sort_key(t, tracker))
    chosen = sorted_pool[0]

    stats = tracker.topic_stats.get(chosen.id, TopicStats())
    desired_diff = suggest_difficulty(base_difficulty, stats)
    reason = (
        f"must coverage={tracker.must_coverage:.2f} target={must_target:.2f}; "
        f"picked {chosen.id} (asked={stats.asked}, avg={stats.avg_score:.2f})"
    )
    return TopicSelection(topic=chosen, reason=reason, desired_difficulty=desired_diff)


def coverage_snapshot(plan: TopicPlan, tracker: ProgressTracker) -> Dict[str, object]:
    return {
        "overall": round(tracker.overall_coverage, 3),
        "must": round(tracker.must_coverage, 3),
        "nice": round(tracker.nice_coverage, 3),
        "topics": {t.id: t.coverage_score for t in plan.topics},
    }
