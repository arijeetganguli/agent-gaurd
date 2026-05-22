"""Telemetry — local-only audit logging (no external telemetry)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentra.models import AuditEntry


class AuditLog:
    """Local-only audit logger. No external telemetry."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or Path(".agentra/audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def flush(self) -> Path:
        """Write entries to a JSON log file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = self.log_dir / f"audit_{ts}.json"
        data = [e.model_dump(mode="json") for e in self.entries]
        log_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        self.entries.clear()
        return log_path

    def load_recent(self, count: int = 100) -> list[dict]:
        """Load recent audit entries from disk."""
        files = sorted(self.log_dir.glob("audit_*.json"), reverse=True)
        entries: list[dict] = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.extend(data)
            if len(entries) >= count:
                break
        return entries[:count]
