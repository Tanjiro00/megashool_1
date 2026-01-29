from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .schemas import ConversationTurn, FinalFeedback


class InterviewLogger:
    def __init__(self, participant_name: str, logs_dir: Path | str = "logs") -> None:
        self.participant_name = participant_name
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.turns: List[ConversationTurn] = []
        self.final_feedback: FinalFeedback | None = None
        self._created_at = datetime.utcnow().isoformat()

    def add_turn(self, turn: ConversationTurn) -> None:
        self.turns.append(turn)

    def set_final_feedback(self, feedback: FinalFeedback) -> None:
        self.final_feedback = feedback

    def to_dict(self) -> Dict[str, Any]:
        return {
            "participant_name": self.participant_name,
            "created_at_utc": self._created_at,
            "turns": [t.model_dump() for t in self.turns],
            "final_feedback": self.final_feedback.model_dump() if self.final_feedback else None,
        }

    def save(self, filename: str | None = None) -> Path:
        if filename is None:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"interview_log_{ts}.json"
        path = self.logs_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path
