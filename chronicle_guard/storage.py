from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _database_path() -> Path:
    configured = os.getenv("VEYLITH_DATA_PATH", "data/veylith.sqlite3")
    path = Path(configured)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS repair_decisions (
            finding_id TEXT PRIMARY KEY,
            decision TEXT NOT NULL,
            status TEXT NOT NULL,
            decided_by TEXT NOT NULL
        )"""
    )
    connection.commit()
    return connection


def get_repair_decision(finding_id: str) -> dict[str, str] | None:
    with _connect() as connection:
        row = connection.execute("SELECT decision, status, decided_by FROM repair_decisions WHERE finding_id = ?", (finding_id,)).fetchone()
    return dict(row) if row else None


def save_repair_decision(finding_id: str, decision: str, status: str, decided_by: str) -> dict[str, str]:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO repair_decisions (finding_id, decision, status, decided_by)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(finding_id) DO UPDATE SET decision=excluded.decision, status=excluded.status, decided_by=excluded.decided_by""",
            (finding_id, decision, status, decided_by),
        )
        connection.commit()
    return {"decision": decision, "status": status, "decided_by": decided_by}
