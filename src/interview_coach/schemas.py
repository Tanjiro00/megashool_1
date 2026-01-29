from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Intent(str, Enum):
    NORMAL_ANSWER = "NORMAL_ANSWER"
    OFF_TOPIC = "OFF_TOPIC"
    ROLE_REVERSAL = "ROLE_REVERSAL"
    STOP = "STOP"


class Correctness(str, Enum):
    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    INCORRECT = "INCORRECT"
    UNKNOWN = "UNKNOWN"


class ObserverAnalysis(BaseModel):
    detected_intent: Intent
    answer_score: int = Field(..., ge=0, le=4)
    correctness: Correctness
    key_strengths: List[str] = Field(default_factory=list, max_length=3)
    key_gaps: List[str] = Field(default_factory=list, max_length=3)
    hallucination_flags: List[str] = Field(default_factory=list)
    recommended_followup: str
    difficulty_delta: int = Field(..., ge=-1, le=1)
    internal_memo: str = Field(..., max_length=400)

    @field_validator("key_strengths", "key_gaps")
    def trim_items(cls, v: List[str]) -> List[str]:
        return [item.strip() for item in v]


class NextAction(str, Enum):
    ASK_QUESTION = "ASK_QUESTION"
    ANSWER_ROLE_REVERSAL_THEN_ASK = "ANSWER_ROLE_REVERSAL_THEN_ASK"
    REDIRECT_AND_ASK = "REDIRECT_AND_ASK"
    CLARIFY_THEN_ASK = "CLARIFY_THEN_ASK"


class InterviewerPlan(BaseModel):
    next_action: NextAction
    next_question: str
    topic: str
    difficulty: int = Field(..., ge=1, le=5)
    internal_memo: str = Field(..., max_length=300)


class DecisionGrade(str, Enum):
    Junior = "Junior"
    Middle = "Middle"
    Senior = "Senior"


class HiringRecommendation(str, Enum):
    Hire = "Hire"
    NoHire = "NoHire"
    StrongHire = "StrongHire"


class SkillEvidence(BaseModel):
    topic: str
    evidence: str


class KnowledgeGap(BaseModel):
    topic: str
    what_went_wrong: str
    correct_answer: str
    resources: List[str] = Field(default_factory=list)


class Decision(BaseModel):
    grade: DecisionGrade
    hiring_recommendation: HiringRecommendation
    confidence_score: int = Field(..., ge=0, le=100)


class HardSkills(BaseModel):
    confirmed_skills: List[SkillEvidence] = Field(default_factory=list)
    knowledge_gaps: List[KnowledgeGap] = Field(default_factory=list)


class SoftSkills(BaseModel):
    clarity: str
    honesty: str
    engagement: str


class Roadmap(BaseModel):
    next_steps: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)


class FinalFeedback(BaseModel):
    decision: Decision
    hard_skills: HardSkills
    soft_skills: SoftSkills
    roadmap: Roadmap


class ConversationTurn(BaseModel):
    turn_id: int
    agent_visible_message: str
    user_message: str
    internal_thoughts: str


class SessionState(BaseModel):
    participant_name: str
    position: str
    grade: str
    experience: str
    difficulty: int = 2
    history: List[ConversationTurn] = Field(default_factory=list)
    extracted_facts: List[str] = Field(default_factory=list)
    topics_covered: List[str] = Field(default_factory=list)
    last_user_intent: Intent = Intent.NORMAL_ANSWER
    hallucination_detected: bool = False
    needs_clarification: bool = False
    running_summary: str = ""
    recent_scores: List[int] = Field(default_factory=list)

    def remember_recent(self, n: int = 3) -> List[ConversationTurn]:
        return self.history[-n:]
