import json
from pathlib import Path

from interview_coach.main import run_interview


def test_log_structure(tmp_path: Path):
    # run with scripted short answers
    _, log_path = run_interview(
        participant_name="TestUser",
        position="Engineer",
        grade="Junior",
        experience="1y",
        scripted_answers=["Привет", "Стоп интервью"],
    )
    data = json.loads(Path(log_path).read_text(encoding="utf-8"))
    assert "participant_name" in data
    assert isinstance(data.get("turns"), list)
    assert data["turns"], "at least one turn logged"
    first_turn = data["turns"][0]
    assert {"turn_id", "agent_visible_message", "user_message", "internal_thoughts"} <= set(first_turn.keys())
    assert data["final_feedback"] is not None

