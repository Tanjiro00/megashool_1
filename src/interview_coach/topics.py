from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple
import re

from pydantic import BaseModel, Field

from .topic_catalog import get_backend_topics_for_grade

Priority = Literal["must", "nice"]
Status = Literal["pending", "in_progress", "covered", "skipped"]


LANGUAGE_LABELS: Dict[str, str] = {
    "python": "Python",
    "java": "Java",
    "csharp": "C#",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "go": "Go",
    "php": "PHP",
    "ruby": "Ruby",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "rust": "Rust",
}

LANGUAGE_PATTERNS: List[Tuple[str, List[str]]] = [
    ("typescript", [r"\btypescript\b", r"\bts\b"]),
    ("javascript", [r"\bjavascript\b", r"\bnode\.?js\b", r"\bnode\b"]),
    ("python", [r"\bpython\b", r"\bdjango\b", r"\bdrf\b", r"\bfastapi\b", r"\bflask\b"]),
    ("java", [r"\bjava\b", r"\bspring\b"]),
    ("csharp", [r"\bc#\b", r"\bcsharp\b", r"\basp\.?net\b", r"\b\.net\b"]),
    ("go", [r"\bgolang\b", r"\bgo developer\b"]),
    ("php", [r"\bphp\b", r"\blaravel\b", r"\bsymfony\b"]),
    ("ruby", [r"\bruby\b", r"\brails\b"]),
    ("kotlin", [r"\bkotlin\b"]),
    ("scala", [r"\bscala\b"]),
    ("rust", [r"\brust\b"]),
]

FRAMEWORK_KEYWORDS: List[Tuple[str, List[str], List[str]]] = [
    ("Django", ["django", "drf"], [r"\bdjango\b", r"\bdrf\b"]),
    ("FastAPI", ["fastapi"], [r"\bfastapi\b"]),
    ("Flask", ["flask"], [r"\bflask\b"]),
    ("Spring", ["spring", "spring boot"], [r"\bspring\b"]),
    ("ASP.NET Core", ["asp.net", ".net", "aspnet"], [r"\basp\.?net\b", r"\b\.net\b", r"\baspnet\b"]),
    ("Node.js / Express", ["node", "express", "nestjs"], [r"\bnode\.?js\b", r"\bexpress\b", r"\bnest(js)?\b"]),
    ("Laravel", ["laravel"], [r"\blaravel\b"]),
    ("Symfony", ["symfony"], [r"\bsymfony\b"]),
    ("Rails", ["rails"], [r"\brails\b"]),
    ("Gin / Fiber", ["gin", "fiber"], [r"\bgin\b", r"\bfiber\b"]),
]

DEFAULT_FRAMEWORK_BY_LANG: Dict[str, Tuple[str, List[str]]] = {
    "python": ("Django/Flask/FastAPI", ["django", "flask", "fastapi"]),
    "java": ("Spring", ["spring"]),
    "csharp": ("ASP.NET Core", ["asp.net", ".net"]),
    "javascript": ("Node.js/Express", ["node", "express"]),
    "typescript": ("Node.js/Nest", ["node", "nestjs", "typescript"]),
    "go": ("Gin/Fiber", ["gin", "fiber"]),
    "php": ("Laravel/Symfony", ["laravel", "symfony"]),
    "ruby": ("Rails", ["rails"]),
    "kotlin": ("Ktor/Spring", ["ktor", "spring"]),
    "scala": ("Akka/Play", ["akka", "play"]),
    "rust": ("Actix/Rocket", ["actix", "rocket"]),
}


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

    language = _infer_primary_language(role_l, exp_l)
    framework_name, framework_tags, framework_hit = _infer_framework(exp_l, language)
    _apply_language_and_framework(topics, language, framework_name, framework_tags)
    if language:
        summary_bits.append(f"язык={LANGUAGE_LABELS.get(language, language)}")
    if framework_hit:
        summary_bits.append(f"фреймворк={framework_name}")
        for t in topics:
            if t.id == "django_framework":
                t.min_questions = max(t.min_questions, 2)
                t.priority = "must"

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


def _infer_primary_language(role_text: str, experience_text: str) -> str:
    text = f"{role_text} {experience_text}".lower()
    for lang, patterns in LANGUAGE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return lang
    return ""


def _infer_framework(experience_text: str, language: str) -> Tuple[str, List[str], bool]:
    text = experience_text.lower()
    for name, tags, patterns in FRAMEWORK_KEYWORDS:
        for pattern in patterns:
            if re.search(pattern, text):
                return name, tags, True
    if language and language in DEFAULT_FRAMEWORK_BY_LANG:
        name, tags = DEFAULT_FRAMEWORK_BY_LANG[language]
        return name, tags, False
    return "Web framework basics", ["framework", "backend"], False


def _apply_language_and_framework(
    topics: List[Topic],
    language: str,
    framework_name: str,
    framework_tags: List[str],
) -> None:
    lang_label = LANGUAGE_LABELS.get(language, "")
    for t in topics:
        if t.id == "python_basics":
            if lang_label:
                t.name = f"{lang_label} basics"
                t.tags = [tag for tag in t.tags if tag != "python"]
                t.tags = [language] + [tag for tag in t.tags if tag != language]
            else:
                t.name = "Programming language basics"
                t.tags = [tag for tag in t.tags if tag != "python"] + ["language"]
        if t.id == "django_framework":
            t.name = f"{framework_name} / Framework basics"
            t.tags = list(dict.fromkeys((framework_tags or []) + ["framework", "web"]))


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


def _preferred_start_topic(plan: TopicPlan, eligible: List[Topic], current_turn: int) -> Topic | None:
    if current_turn != 1:
        return None
    grade_l = plan.grade.lower()
    if grade_l == "senior":
        preferred_ids = [
            "system_design_advanced",
            "concurrency_deep",
            "system_design",
            "concurrency",
            "performance",
            "reliability",
            "security",
        ]
    elif grade_l == "middle":
        preferred_ids = ["system_design", "concurrency", "http_rest", "db_sql_basics"]
    else:
        return None
    for pid in preferred_ids:
        for topic in eligible:
            if topic.id == pid and topic.status in {"pending", "in_progress"}:
                return topic
    return None


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

    preferred = _preferred_start_topic(plan, eligible, current_turn)
    if preferred:
        stats = tracker.topic_stats.get(preferred.id, TopicStats())
        desired_diff = suggest_difficulty(base_difficulty, stats)
        reason = f"start bias for grade={plan.grade}: picked {preferred.id}"
        return TopicSelection(topic=preferred, reason=reason, desired_difficulty=desired_diff)

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
