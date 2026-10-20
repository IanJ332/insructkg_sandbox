"""Append-only instructor decisions, committed with their current-state update."""

import uuid
from datetime import datetime, timezone


def record_review(db, entity_type, entity_id, decision, reviewer_id, notes):
    db.execute(
        "CREATE TABLE IF NOT EXISTS instructor_review_history ("
        "review_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, "
        "decision TEXT NOT NULL, reviewer_id TEXT NOT NULL, notes TEXT, reviewed_at TEXT NOT NULL)"
    )
    db.execute(
        "INSERT INTO instructor_review_history VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            uuid.uuid4().hex,
            entity_type,
            entity_id,
            decision,
            reviewer_id,
            notes,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
