"""Append-only audit logger for BidWise tender evaluation system.

Maintains an immutable, append-only JSONL log of all agent runs and tool executions.
"""

from __future__ import annotations

import datetime
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from config import RUN_LOG_PATH

_LOG_LOCK = threading.Lock()


class RunLogger:
    """Append-only logger writing to logs/run_log.jsonl."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = Path(log_path) if log_path else RUN_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        run_id: str,
        agent: str,
        tool: str,
        input_summary: str,
        output_summary: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Appends a single JSON log record to the run log in append mode ('a')."""
        record: Dict[str, Any] = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "run_id": run_id,
            "agent": agent,
            "tool": tool,
            "input_summary": input_summary,
            "output_summary": output_summary,
        }
        if extra:
            record["extra"] = extra

        serialized = json.dumps(record) + "\n"

        with _LOG_LOCK:
            # Mode 'a' ensures append-only behavior, never truncates or rewrites
            with open(self.log_path, mode="a", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()

        return record

    def get_records(self, run_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """Reads log records from the append-only log file."""
        if not self.log_path.exists():
            return []
        records = []
        with open(self.log_path, mode="r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        if run_id is None or rec.get("run_id") == run_id:
                            records.append(rec)
                    except json.JSONDecodeError:
                        continue
        return records


# Global default logger instance
default_logger = RunLogger()


def log_event(
    run_id: str,
    agent: str,
    tool: str,
    input_summary: str,
    output_summary: str,
    extra: Optional[Dict[str, Any]] = None,
    logger_instance: Optional[RunLogger] = None,
) -> Dict[str, Any]:
    """Convenience functional interface for logging."""
    target = logger_instance or default_logger
    return target.log(
        run_id=run_id,
        agent=agent,
        tool=tool,
        input_summary=input_summary,
        output_summary=output_summary,
        extra=extra,
    )
