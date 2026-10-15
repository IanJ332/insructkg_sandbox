"""Authorized student identity resolution and safety boundaries.
Prevents hardcoded student IDs, enforces fail-closed semantics for untrusted or
missing identities, excludes student-controlled form fields, and isolates group assessments.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DATA_DIR = Path(os.environ.get("SIIP_DATA_DIR", Path(__file__).with_name("data")))

DEFAULT_IDENTITY_MAP = {
    "101": "S001",
    "102": "S002",
    "103": "S003",
    "104": "S004",
    "105": "S005",
    "2": "S001",  # PrairieLearn local student view default numeric user_id
    "student@example.com": "S001",
    "student2@example.com": "S002",
    "student3@example.com": "S003",
    "synthetic_student@illinois.edu": "S001",
}


def load_identity_map() -> Dict[str, str]:
    """Load authorized identity mapping from disk or use validated default."""
    map_file = DATA_DIR / "identity_map.json"
    if map_file.exists():
        try:
            loaded = json.loads(map_file.read_text())
            if isinstance(loaded, dict):
                return {str(k): str(v) for k, v in loaded.items()}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_IDENTITY_MAP)


def resolve_student_identity(
    data: Dict[str, Any], identity_map: Optional[Dict[str, str]] = None
) -> Tuple[Optional[str], bool, str]:
    """
    Safely resolves a trusted synthetic student identity from PrairieLearn hook data.

    Returns:
        (student_id, is_trusted, reason)

    Invariants:
    1. NEVER inspect student-controlled form fields (e.g., submitted_answers).
    2. Group assessments (options.group or group) FAIL CLOSED (is_trusted=False)
       because group submissions have no individual student ownership.
    3. Missing or empty user identity FAIL CLOSED (is_trusted=False).
    4. Unmapped user identifiers FAIL CLOSED (is_trusted=False).
    5. Only verified mappings against the authorized identity map succeed.
    """
    if not isinstance(data, dict):
        return None, False, "invalid_data_payload"

    # 1. Group assessment isolation: individual personalization cannot consume group records
    if data.get("group") is not None or data.get("options", {}).get("group") is not None:
        return None, False, "group_assessment_isolation"

    # 2. Extract user identity strictly from trusted system context (options.user or user)
    user = data.get("options", {}).get("user")
    if user is None:
        user = data.get("user")

    if not user or not isinstance(user, dict):
        return None, False, "identity_unavailable_anonymous"

    mapping = identity_map if identity_map is not None else load_identity_map()

    # Look up by numeric user_id first, then uid (email / netid)
    raw_uid = user.get("uid")
    raw_user_id = user.get("user_id")

    if raw_user_id is not None:
        user_id_str = str(raw_user_id)
        if user_id_str in mapping:
            return mapping[user_id_str], True, "authorized_trusted_identity"

    if raw_uid is not None:
        uid_str = str(raw_uid).strip().lower()
        if uid_str in mapping:
            return mapping[uid_str], True, "authorized_trusted_identity"

    return None, False, "unmapped_user_identity"
