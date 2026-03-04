"""Session logging — write each agent step to a JSONL file."""

import json
import time
from pathlib import Path


LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"


class SessionLogger:
    """Log agent steps to logs/<session_id>.jsonl."""

    def __init__(self, session_id: str):
        LOGS_DIR.mkdir(exist_ok=True)
        self._path = LOGS_DIR / f"{session_id}.jsonl"
        self._step = 0
        self._step_start: float = 0

    def start_step(self):
        """Mark the start of a new step for duration tracking."""
        self._step += 1
        self._step_start = time.monotonic()

    def log(
        self,
        command: str,
        action: dict,
        safety_level: str = "safe",
        blocked: bool = False,
    ):
        """Write one step entry to the log file."""
        duration_ms = int((time.monotonic() - self._step_start) * 1000) if self._step_start else 0

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "step": self._step,
            "command": command,
            "thought": action.get("thought", ""),
            "action": action.get("action", ""),
            "params": action.get("params", {}),
            "done": action.get("done", False),
            "safety_level": safety_level,
            "blocked": blocked,
            "duration_ms": duration_ms,
        }

        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    @property
    def path(self) -> Path:
        return self._path
