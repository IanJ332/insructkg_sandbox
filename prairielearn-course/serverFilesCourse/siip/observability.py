"""Allowlisted operational events; never SQL, prompts, raw identities or credentials."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

LOGGER = logging.getLogger("siip")
SAFE_FIELDS = frozenset(
    {
        "correlation_id",
        "question_id",
        "student_id",
        "status",
        "score",
        "latency_ms",
        "feedback_status",
        "kg_status",
        "error_type",
        "http_status",
        "method",
        "path",
        "record_count",
        "source",
        "retry",
        "model",
    }
)


def event(name: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
    LOGGER.info(
        json.dumps({"event": name, "timestamp": datetime.now(timezone.utc).isoformat(), **safe})
    )
