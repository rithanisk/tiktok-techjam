from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .text import safe_session_name


class TraceRecorder:
    """In-memory flight recorder with optional session-isolated NDJSON output."""

    def __init__(self, trace_dir: str | Path | None = None) -> None:
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()
        if self.trace_dir:
            self.trace_dir.mkdir(parents=True, exist_ok=True)

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._events[session_id] = []
            if self.trace_dir:
                path = self.trace_dir / f"{safe_session_name(session_id)}.ndjson"
                path.write_text("", encoding="utf-8")

    def record(self, session_id: str, event: dict[str, Any]) -> None:
        safe_event = json.loads(json.dumps(event, ensure_ascii=True, default=str))
        with self._lock:
            self._events.setdefault(session_id, []).append(safe_event)
            if self.trace_dir:
                path = self.trace_dir / f"{safe_session_name(session_id)}.ndjson"
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(safe_event, sort_keys=True) + "\n")

    def events(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._events.get(session_id, [])))
