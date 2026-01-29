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

try:
    from crewai import Agent, Crew, Process, Task
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

from .logic import question_already_covered


def build_agents(llm) -> Tuple[Any, Any, Any]:
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
    )
    manager = Agent(
        role="Hiring Manager",
        goal="Summarize the interview and give final decision",
        backstory=HIRING_MANAGER_PROMPT,
        verbose=False,
        llm=llm,
    )
    return observer, interviewer, manager


def observer_task(observer_agent, state_summary: str, last_question: str, user_message: str) -> Task:
    description = (
        f"{OBSERVER_SYSTEM_PROMPT}\n\n"
        f"Last interviewer question: {last_question}\n"
        f"User answer: {user_message}\n"
        f"State summary: {state_summary}\n"
        "Return ObserverAnalysis JSON."
    )
    return Task(
        description=description,
        expected_output="Valid JSON for ObserverAnalysis schema.",
        agent=observer_agent,
        output_pydantic=ObserverAnalysis,
    )


def planner_task(interviewer_agent, analysis: ObserverAnalysis, state_summary: str, difficulty: int) -> Task:
    description = (
        f"{INTERVIEWER_SYSTEM_PROMPT}\n"
        f"Observer memo: {analysis.internal_memo}\n"
        f"Detected intent: {analysis.detected_intent}\n"
        f"Recommended follow-up: {analysis.recommended_followup}\n"
        f"Desired difficulty: {difficulty}\n"
        f"State summary: {state_summary}\n"
        "Produce InterviewerPlan JSON."
    )
    return Task(
        description=description,
        expected_output="Valid JSON for InterviewerPlan schema.",
        agent=interviewer_agent,
        output_pydantic=InterviewerPlan,
    )


def interviewer_task(interviewer_agent, plan: InterviewerPlan) -> Task:
    description = (
        f"{INTERVIEWER_SYSTEM_PROMPT}\n"
        f"Plan: next_action={plan.next_action}, topic={plan.topic}, difficulty={plan.difficulty}\n"
        f"Next question draft: {plan.next_question}\n"
        "Return the exact user-facing question/message only."
    )
    return Task(description=description, expected_output="Single interviewer message.", agent=interviewer_agent)


def build_turn_crew(observer, interviewer, state_summary: str, last_question: str, user_message: str, difficulty: int) -> Crew:
    obs_task = observer_task(observer, state_summary, last_question, user_message)
    # placeholder plan; actual plan uses observer output after kickoff? With sequential process, outputs list in order
    # We rebuild plan task after observer result inside calling code to ensure latest data.
    # So here we only include obs_task; planner/interviewer tasks built dynamically after observer output.
    return Crew(agents=[observer, interviewer], tasks=[obs_task], process=Process.sequential)


def build_feedback_crew(manager, summary: str, state) -> Crew:
    description = (
        f"{HIRING_MANAGER_PROMPT}\n"
        f"Candidate profile: {state.participant_name}, position={state.position}, grade={state.grade}, experience={state.experience}\n"
        f"Conversation summary: {summary}\n"
        "Generate FinalFeedback JSON."
    )
    task = Task(
        description=description,
        expected_output="Valid JSON for FinalFeedback schema.",
        agent=manager,
        output_pydantic=FinalFeedback,
    )
    return Crew(agents=[manager], tasks=[task], process=Process.sequential)
