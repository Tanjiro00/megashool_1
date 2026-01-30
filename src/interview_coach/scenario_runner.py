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
    parser.add_argument("--name", default="Тест")
    parser.add_argument("--position", default="Python Developer")
    parser.add_argument("--grade", default="Middle")
    parser.add_argument("--experience", default="3 года")
    args = parser.parse_args()
    run_scenario(args.scenario_path, args.name, args.position, args.grade, args.experience)
