from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .main import run_interview


def load_scenario(path: str | Path) -> List[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "messages" in data:
        return data["messages"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported scenario format; expected list or {messages: []}")


def run_scenario(
    path: str | Path,
    participant_name: str = "Тест",
    position: str = "Python Developer",
    grade: str = "Middle",
    experience: str = "3 года",
):
    messages = load_scenario(path)
    scenario_name = Path(path).stem
    log_filename = f"{scenario_name}_log.json"
    feedback, log_path = run_interview(
        participant_name,
        position,
        grade,
        experience,
        scripted_answers=messages,
        log_filename=log_filename,
    )
    print(f"Сценарий завершён. Лог: {log_path}")
    return feedback, log_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run scripted interview scenario")
    parser.add_argument("scenario_path", help="Path to JSON scenario file")
    parser.add_argument("--name")
    parser.add_argument("--position")
    parser.add_argument("--grade")
    parser.add_argument("--experience")
    args = parser.parse_args()

    def _prompt_required(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("Поле обязательно. Повторите ввод.")

    name = args.name or _prompt_required("Введите имя кандидата: ")
    position = args.position or _prompt_required("Целевая позиция: ")
    grade = args.grade or _prompt_required("Грейд (Junior/Middle/Senior): ")
    experience = args.experience or _prompt_required("Опыт (кратко): ")
    run_scenario(args.scenario_path, name, position, grade, experience)
