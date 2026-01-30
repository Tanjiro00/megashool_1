from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

TopicDef = Dict[str, object]


BACKEND_BASE_TOPICS: List[TopicDef] = [
    {"id": "python_basics", "name": "Python basics", "priority": "must", "min_questions": 2, "tags": ["python", "basics", "syntax"]},
    {"id": "oop_principles", "name": "OOP principles", "priority": "must", "min_questions": 2, "tags": ["oop", "classes", "inheritance", "polymorphism"]},
    {"id": "http_rest", "name": "HTTP & REST", "priority": "must", "min_questions": 2, "tags": ["http", "rest", "requests", "responses"]},
    {"id": "db_sql_basics", "name": "DB & SQL basics", "priority": "must", "min_questions": 2, "tags": ["sql", "database", "queries"]},
    {"id": "git_basics", "name": "Git basics", "priority": "must", "min_questions": 2, "tags": ["git", "version control"]},
    {"id": "django_framework", "name": "Django / Framework basics", "priority": "must", "min_questions": 2, "tags": ["django", "framework", "orm"]},
    {"id": "debug_testing", "name": "Debugging & testing basics", "priority": "must", "min_questions": 2, "tags": ["testing", "debug", "pytest"]},
]

BACKEND_MIDDLE_TOPICS: List[TopicDef] = [
    {"id": "system_design", "name": "System design fundamentals", "priority": "must", "min_questions": 2, "tags": ["architecture", "design", "scalability"]},
    {"id": "concurrency", "name": "Concurrency & async", "priority": "must", "min_questions": 2, "tags": ["async", "threads", "processes"]},
    {"id": "performance", "name": "Performance & profiling", "priority": "nice", "min_questions": 1, "tags": ["performance", "profiling", "optimization"]},
    {"id": "caching", "name": "Caching", "priority": "nice", "min_questions": 1, "tags": ["cache", "redis", "ttl"]},
    {"id": "security", "name": "Security basics", "priority": "nice", "min_questions": 1, "tags": ["security", "auth", "owasp"]},
    {"id": "ci_cd", "name": "CI/CD", "priority": "nice", "min_questions": 1, "tags": ["ci", "cd", "pipelines"]},
]

BACKEND_SENIOR_TOPICS: List[TopicDef] = [
    {"id": "system_design_advanced", "name": "System design (advanced)", "priority": "must", "min_questions": 2, "tags": ["architecture", "tradeoffs", "capacity"]},
    {"id": "concurrency_deep", "name": "Concurrency scaling", "priority": "must", "min_questions": 2, "tags": ["locks", "queues", "asyncio"]},
    {"id": "reliability", "name": "Reliability & observability", "priority": "nice", "min_questions": 1, "tags": ["logging", "metrics", "tracing"]},
]

def get_backend_topics_for_grade(grade: str) -> List[TopicDef]:
    g = grade.lower()
    topics = deepcopy(BACKEND_BASE_TOPICS)
    if g in {"middle", "senior"}:
        topics.extend(deepcopy(BACKEND_MIDDLE_TOPICS))
    if g == "senior":
        topics.extend(deepcopy(BACKEND_SENIOR_TOPICS))
    return topics


TOPIC_CATALOG: Dict[str, List[TopicDef]] = {
    "backend": BACKEND_BASE_TOPICS,
}
