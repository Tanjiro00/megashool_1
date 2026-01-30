import json
from pathlib import Path

from interview_coach.scenario_runner import run_scenario


def test_scenario_runner_creates_log_and_feedback(tmp_path: Path):
    scenarios = [
        "example_secret_scenario.json",
        "role_reversal.json",
        "off_topic.json",
        "hallucination_trap.json",
    ]
    for name in scenarios:
        scenario_path = Path("scenarios") / name
        feedback, log_path = run_scenario(
            scenario_path, participant_name="Scripted", position="Dev", grade="Middle", experience="5y"
        )
        assert Path(log_path).exists()
        data = json.loads(Path(log_path).read_text(encoding="utf-8"))
        assert data["participant_name"] == "Scripted"
        assert data["final_feedback"] is not None
        assert isinstance(feedback.decision.confidence_score, int)
