from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .prompts import HIRING_MANAGER_PROMPT, INTERVIEWER_SYSTEM_PROMPT, OBSERVER_SYSTEM_PROMPT
from .schemas import (
    ConversationTurn,
    FinalFeedback,
    InterviewerPlan,
    ObserverAnalysis,
)
from .topics import TopicSelection
from .tooling import SEARCH_TOOL_NAME, search_tool

try:
    from crewai_tools import tool as tool_decorator  # optional dependency
except Exception:
    tool_decorator = None

try:
    from crewai import Agent, Crew, Process, Task
    try:
        from duckduckgo_search import DDGS
    except Exception:  # optional dependency for tool
        DDGS = None
except ImportError:  # Lightweight stubs to allow offline execution
    class Agent:
        def __init__(self, role: str, goal: str, backstory: str, verbose: bool, llm: Any, **kwargs: Any):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.verbose = verbose
            self.llm = llm

    class Task:
        def __init__(
            self,
            description: str,
            agent: Agent,
            inputs: Dict[str, Any] | None = None,
            output_pydantic: Any | None = None,
            expected_output: str | None = None,
            **kwargs: Any,
        ):
            self.description = description
            self.agent = agent
            self.inputs = inputs or {}
            self.output_pydantic = output_pydantic
            self.expected_output = expected_output

        def execute(self, context: Dict[str, Any] | None = None):
            payload = [{"role": "user", "content": self.description}]
            resp = self.agent.llm.chat_completion(payload) if hasattr(self.agent.llm, "chat_completion") else self.agent.llm(payload)
            content = getattr(resp, "content", str(resp))
            if self.output_pydantic:
                try:
                    return self.output_pydantic.model_validate_json(content)
                except Exception:
                    try:
                        data = json.loads(content)
                        return self.output_pydantic.model_validate(data)
                    except Exception:
                        return self.output_pydantic.model_validate(self.output_pydantic().model_dump())
            return content

    class Process:
        sequential = "sequential"

    class Crew:
        def __init__(self, agents: List[Agent], tasks: List[Task], process: str = Process.sequential, **kwargs: Any):
            self.agents = agents
            self.tasks = tasks

        def kickoff(self, inputs: Dict[str, Any] | None = None):
            outputs = []
            for task in self.tasks:
                outputs.append(task.execute(inputs or {}))
            return outputs

    # make DDGS usable in stub mode
    class DummyDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query: str, max_results: int = 3):
            return []

    DDGS = DummyDDGS

from .logic import question_already_covered


def build_agents(llm) -> Tuple[Any, Any, Any]:
    tools = []
    if tool_decorator:
        try:
            wrapped = tool_decorator("Поиск в вебе (DuckDuckGo/Tavily)")(search_tool)
            tools.append(wrapped)
        except Exception:
            tools = []
    observer = Agent(
        role="Observer",
        goal="Evaluate answers and guide next steps",
        backstory=OBSERVER_SYSTEM_PROMPT,
        verbose=False,
        llm=llm,
    )
    interviewer = Agent(
        role="Interviewer",
        goal="Conduct the interview and ask the right next question",
        backstory=INTERVIEWER_SYSTEM_PROMPT,
        verbose=False,
        llm=llm,
        tools=tools,
    )
    manager = Agent(
        role="Hiring Manager",
        goal="Summarize the interview and give final decision",
        backstory=HIRING_MANAGER_PROMPT,
        verbose=False,
        llm=llm,
    )
    return observer, interviewer, manager


# ---------- Tools ----------

def search_tool(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    # Deprecated shim: left for backward compatibility
    from .tooling import search_tool as _st

    return _st(query, max_results)


def observer_task(
    observer_agent,
    state_summary: str,
    recent_qa: str,
    known_facts: str,
    last_question: str,
    user_message: str,
    topic_id: str | None,
    extra_hint: str = "",
) -> Task:
    description = (
        f"{OBSERVER_SYSTEM_PROMPT}\n\n"
        f"Last interviewer question: {last_question}\n"
        f"User answer: {user_message}\n"
        f"Recent Q/A (last turns): {recent_qa or '—'}\n"
        f"Known facts so far: {known_facts or '—'}\n"
        f"Topic in focus: {topic_id or 'general'} (верни topic_id в JSON)\n"
        f"State summary: {state_summary}\n"
        "Return ObserverAnalysis JSON."
    )
    if extra_hint:
        description += f"\n{extra_hint}"
    return Task(
        description=description,
        expected_output="Valid JSON for ObserverAnalysis schema.",
        agent=observer_agent,
        output_pydantic=ObserverAnalysis,
    )


def planner_task(
    interviewer_agent,
    analysis: ObserverAnalysis,
    state_summary: str,
    difficulty: int,
    selection: TopicSelection,
    coverage_hint: dict,
    recent_qa: str,
    known_facts: str,
    candidate_profile: str | None = None,
    extra_hint: str = "",
) -> Task:
    # Guidance for next_action to make behaviour deterministic
    next_action_rules = (
        "Определи next_action: "
        "если intent=ROLE_REVERSAL => ANSWER_ROLE_REVERSAL_THEN_ASK; "
        "если intent=OFF_TOPIC => REDIRECT_AND_ASK; "
        "если нужен уточняющий вопрос или ответ неясен => CLARIFY_THEN_ASK; "
        "иначе ASK_QUESTION. Всегда задавай конкретный следующий вопрос."
    )
    profile_line = f"Candidate profile: {candidate_profile}\n" if candidate_profile else ""
    description = (
        f"{INTERVIEWER_SYSTEM_PROMPT}\n"
        f"{profile_line}"
        f"Observer memo: {analysis.internal_memo}\n"
        f"Detected intent: {analysis.detected_intent}\n"
        f"Correctness: {analysis.correctness}, answer_score: {analysis.answer_score}\n"
        f"Key gaps: {', '.join(analysis.key_gaps) if analysis.key_gaps else '—'}\n"
        f"Recommended follow-up: {analysis.recommended_followup}\n"
        f"Desired difficulty: {difficulty}\n"
        f"Selected topic (fixed): {selection.topic.name} [{selection.topic.id}] priority={selection.topic.priority}\n"
        f"Topic tags: {', '.join(selection.topic.tags)}\n"
        f"Coverage: must={coverage_hint.get('must', 0):.2f} overall={coverage_hint.get('overall', 0):.2f}\n"
        f"Recent Q/A: {recent_qa or '—'}\n"
        f"Known facts: {known_facts or '—'}\n"
        f"{next_action_rules}\n"
        f"State summary: {state_summary}\n"
        "Если ответ неверный/неполный/UNKNOWN — начни next_question с короткой корректировки или подсказки (1 предложение), затем задай проверочный вопрос. "
        "Stay within the selected topic; do not switch topics. Варьируй формулировки, не повторяй дословно предыдущие вопросы. "
        "Сформируй InterviewerPlan JSON с topic_id, next_action и конкретным next_question."
    )
    if extra_hint:
        description += f"\n{extra_hint}"
    return Task(
        description=description,
        expected_output="Valid JSON for InterviewerPlan schema.",
        agent=interviewer_agent,
        output_pydantic=InterviewerPlan,
    )


def interviewer_task(interviewer_agent, plan: InterviewerPlan, last_user_message: str, candidate_profile: str | None = None) -> Task:
    profile_line = f"Candidate profile: {candidate_profile}\n" if candidate_profile else ""
    description = (
        f"{INTERVIEWER_SYSTEM_PROMPT}\n"
        f"{profile_line}"
        f"Plan: next_action={plan.next_action}, topic={plan.topic} ({getattr(plan, 'topic_id', None)}), difficulty={plan.difficulty}\n"
        f"Next question draft: {plan.next_question}\n"
        f"Last user message (for role-reversal/redirect/clarify): {last_user_message}\n"
        "Собери финальное сообщение для кандидата, строго следуя next_action:\n"
        "- ANSWER_ROLE_REVERSAL_THEN_ASK: кратко ответь на вопрос кандидата (1–2 предложения, без домыслов), затем задай новый технический вопрос.\n"
        "- REDIRECT_AND_ASK: мягко верни беседу к теме и задай релевантный вопрос.\n"
        "- CLARIFY_THEN_ASK: попроси уточнить конкретную деталь, затем задай технический вопрос.\n"
        "- ASK_QUESTION: задай только технический вопрос.\n"
        "Не добавляй пояснения о правилах. Верни только финальный текст для кандидата."
    )
    return Task(description=description, expected_output="Single interviewer message.", agent=interviewer_agent)


def build_turn_crew(
    observer,
    interviewer,
    state_summary: str,
    recent_qa: str,
    known_facts: str,
    last_question: str,
    user_message: str,
    difficulty: int,
    topic_id: str | None,
) -> Crew:
    obs_task = observer_task(observer, state_summary, recent_qa, known_facts, last_question, user_message, topic_id)
    # placeholder plan; actual plan uses observer output after kickoff? With sequential process, outputs list in order
    # We rebuild plan task after observer result inside calling code to ensure latest data.
    # So here we only include obs_task; planner/interviewer tasks built dynamically after observer output.
    return Crew(agents=[observer, interviewer], tasks=[obs_task], process=Process.sequential)


def build_feedback_crew(manager, summary: str, state) -> Crew:
    coverage_line = ""
    try:
        if getattr(state, "progress", None) and getattr(state, "topic_plan", None):
            covered = [t.id for t in state.topic_plan.topics if t.status == "covered"]
            pending = [t.id for t in state.topic_plan.topics if t.status != "covered"]
            coverage_line = (
                f"Topic coverage: must={state.progress.must_coverage:.2f}, overall={state.progress.overall_coverage:.2f}; "
                f"covered={covered}; not_covered={pending}. "
            )
    except Exception:
        coverage_line = ""
    description = (
        f"{HIRING_MANAGER_PROMPT}\n"
        f"Candidate profile: {state.participant_name}, position={state.position}, grade={state.grade}, experience={state.experience}\n"
        f"Conversation summary: {summary}\n"
        f"{coverage_line}"
        "Generate FinalFeedback JSON."
    )
    task = Task(
        description=description,
        expected_output="Valid JSON for FinalFeedback schema.",
        agent=manager,
        output_pydantic=FinalFeedback,
    )
    return Crew(agents=[manager], tasks=[task], process=Process.sequential)
