from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional

from .config import get_llm
from .crewai_setup import (
    Crew,
    Process,
    build_agents,
    build_feedback_crew,
    build_turn_crew,
    interviewer_task,
    planner_task,
)
from .logic import (
    classify_intent,
    detect_hallucination,
    extract_facts,
    question_already_covered,
    register_turn,
    update_difficulty,
)
from .logger import InterviewLogger
from .resources import get_resources
from .schemas import ConversationTurn, Intent, SessionState


def _extract_output(result):
    """Normalize CrewAI kickoff result across versions/stubs."""
    # CrewAI >=0.36 returns CrewOutput with tasks_output list
    if hasattr(result, "tasks_output"):
        tasks = result.tasks_output
        if tasks:
            item = tasks[0]
            if hasattr(item, "pydantic") and item.pydantic is not None:
                return item.pydantic
            if hasattr(item, "output"):
                return item.output
            return item
    # Sometimes kickoff already returns a list
    if isinstance(result, list):
        return result[0] if result else result
    return result


def format_feedback(feedback) -> str:
    lines = [
        f"Решение: {feedback.decision.hiring_recommendation} ({feedback.decision.grade}), уверенность {feedback.decision.confidence_score}%",
        "Hard skills:",
    ]
    for sk in feedback.hard_skills.confirmed_skills:
        lines.append(f"- {sk.topic}: {sk.evidence}")
    if feedback.hard_skills.knowledge_gaps:
        lines.append("Пробелы:")
        for gap in feedback.hard_skills.knowledge_gaps:
            res = "; ".join(gap.resources)
            lines.append(f"- {gap.topic}: {gap.what_went_wrong} | Правильно: {gap.correct_answer} | Ресурсы: {res}")
    lines.append("Soft skills:")
    lines.append(f"- Ясность: {feedback.soft_skills.clarity}")
    lines.append(f"- Честность: {feedback.soft_skills.honesty}")
    lines.append(f"- Вовлеченность: {feedback.soft_skills.engagement}")
    if feedback.roadmap.next_steps:
        lines.append("Next steps:")
        for step in feedback.roadmap.next_steps:
            lines.append(f"- {step}")
    if feedback.roadmap.resources:
        lines.append("Resources:")
        for r in feedback.roadmap.resources:
            lines.append(f"- {r}")
    return "\n".join(lines)


def run_interview(
    participant_name: str,
    position: str,
    grade: str,
    experience: str,
    scripted_answers: Optional[Iterable[str]] = None,
    log_filename: Optional[str] = None,
):
    llm, cfg = get_llm()
    observer, interviewer, manager = build_agents(llm)

    state = SessionState(
        participant_name=participant_name,
        position=position,
        grade=grade,
        experience=experience,
    )
    logger = InterviewLogger(participant_name)
    scripted_iter = iter(scripted_answers) if scripted_answers is not None else None
    current_question = f"{participant_name}, расскажите о своем последнем проекте и вашей роли."
    print(f"Интервьюер: {current_question}")

    while True:
        if scripted_iter is not None:
            try:
                user_message = next(scripted_iter)
                print(f"Кандидат (скрипт): {user_message}")
            except StopIteration:
                break
        else:
            try:
                user_message = input("Вы: ")
            except (EOFError, KeyboardInterrupt):
                user_message = "Стоп интервью"

        intent = classify_intent(user_message)
        state.last_user_intent = intent
        if intent == Intent.STOP:
            break

        crew_obs = build_turn_crew(observer, interviewer, state.running_summary, current_question, user_message, state.difficulty)
        obs_output = _extract_output(crew_obs.kickoff())
        state.hallucination_detected = state.hallucination_detected or detect_hallucination(user_message) or bool(
            obs_output.hallucination_flags
        )
        state.difficulty = update_difficulty(state, obs_output)
        extract_facts(state, current_question, user_message)

        plan_task = planner_task(interviewer, obs_output, state.running_summary, state.difficulty)
        plan = _extract_output(Crew(agents=[interviewer], tasks=[plan_task], process=Process.sequential).kickoff())

        inter_task = interviewer_task(interviewer, plan)
        visible_message = _extract_output(Crew(agents=[interviewer], tasks=[inter_task], process=Process.sequential).kickoff())
        if isinstance(visible_message, str) and question_already_covered(state, visible_message):
            visible_message = "Расскажите о сложном баге, который вы недавно исправили, и о вашем подходе."

        internal = f"[Observer]: {obs_output.internal_memo} [Interviewer]: {plan.internal_memo}"
        turn = ConversationTurn(
            turn_id=len(state.history) + 1,
            agent_visible_message=current_question,
            user_message=user_message,
            internal_thoughts=internal,
        )
        logger.add_turn(turn)
        register_turn(state, turn)
        current_question = visible_message if isinstance(visible_message, str) else plan.next_question
        print(f"Интервьюер: {current_question}")

    feedback_crew = build_feedback_crew(manager, state.running_summary, state)
    feedback = _extract_output(feedback_crew.kickoff())
    for gap in feedback.hard_skills.knowledge_gaps:
        if not gap.resources:
            gap.resources = get_resources(gap.topic)
    logger.set_final_feedback(feedback)
    log_path = logger.save(filename=log_filename)

    print("\n=== Финальный отчет ===")
    print(format_feedback(feedback))
    print(f"\nЛог сохранен в: {log_path}")
    if cfg.mock_mode:
        print("(Запуск в mock-режиме: установите OPENAI_API_KEY/ANTHROPIC_API_KEY/OPENROUTER_API_KEY для реальных ответов)")
    return feedback, log_path


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-Agent Interview Coach (CrewAI)")
    parser.add_argument("--name", dest="participant_name")
    parser.add_argument("--position")
    parser.add_argument("--grade", default="Middle")
    parser.add_argument("--experience", default="3 года")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None):
    args = parse_args(argv or sys.argv[1:])
    name = args.participant_name or input("Введите имя кандидата: ")
    position = args.position or input("Целевая позиция: ")
    grade = args.grade or input("Грейд (Junior/Middle/Senior): ")
    experience = args.experience or input("Опыт (кратко): ")
    run_interview(name, position, grade, experience)


if __name__ == "__main__":
    main()
