"""Authorized student identity resolution and safety boundaries.
Prevents hardcoded student IDs, enforces fail-closed semantics for untrusted or
missing identities, excludes student-controlled form fields, and isolates group assessments.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
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


_EPHEMERAL_SECRET: Optional[bytes] = None
_EPHEMERAL_SERVICE_KEY: Optional[str] = None


def get_auth_secret() -> bytes:
    """Return local authentication secret bytes from environment, untracked key file, or secure random."""
    global _EPHEMERAL_SECRET
    custom = os.environ.get("SIIP_AUTH_SECRET")
    if custom:
        return custom.strip().encode("utf-8")
    secret_file = DATA_DIR / "auth_secret.key"
    if secret_file.exists():
        try:
            val = secret_file.read_bytes().strip()
            if val:
                return val
        except OSError:
            pass
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_bytes(32)
        secret_file.write_bytes(generated)
        return generated
    except OSError:
        pass
    if _EPHEMERAL_SECRET is None:
        _EPHEMERAL_SECRET = secrets.token_bytes(32)
    return _EPHEMERAL_SECRET


def get_service_key() -> str:
    """Return shared service-to-service authentication key for queue operations."""
    global _EPHEMERAL_SERVICE_KEY
    custom = os.environ.get("SIIP_SERVICE_KEY")
    if custom:
        return custom.strip()
    key_file = DATA_DIR / "service.key"
    if key_file.exists():
        try:
            val = key_file.read_text().strip()
            if val:
                return val
        except OSError:
            pass
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        key_file.write_text(generated)
        return generated
    except OSError:
        pass
    if _EPHEMERAL_SERVICE_KEY is None:
        _EPHEMERAL_SERVICE_KEY = secrets.token_hex(32)
    return _EPHEMERAL_SERVICE_KEY


def verify_service_request(headers: Any) -> bool:
    """Verify that a request originates from an authorized internal service caller."""
    expected_key = get_service_key()
    if not expected_key:
        return False
    srv_header = headers.get("X-SIIP-Service-Key")
    if srv_header and hmac.compare_digest(srv_header.strip(), expected_key):
        return True
    auth_header = headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if hmac.compare_digest(token, expected_key):
            return True
    return False


def create_signed_ticket(
    student_id: str, job_id: str, secret: Optional[bytes] = None, ttl_seconds: float = 3600.0
) -> str:
    """Generate a tamper-evident signed ticket granting access to a specific job."""
    sec = secret if secret is not None else get_auth_secret()
    expires_at = int(time.time() + ttl_seconds)
    payload = f"{student_id}:{job_id}:{expires_at}"
    sig = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{student_id}.{job_id}.{expires_at}.{sig}"


def verify_signed_ticket(ticket: str, job_id: str, secret: Optional[bytes] = None) -> Optional[str]:
    """
    Verify ticket signature, job binding, and expiration.
    Returns authorized student_id if valid, or None if invalid/expired.
    """
    if not isinstance(ticket, str):
        return None
    parts = ticket.strip().split(".")
    if len(parts) != 4:
        return None
    student_id, ticket_job_id, expires_str, provided_sig = parts
    if ticket_job_id != job_id:
        return None
    try:
        expires_at = int(expires_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    sec = secret if secret is not None else get_auth_secret()
    payload = f"{student_id}:{job_id}:{expires_at}"
    expected_sig = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected_sig, provided_sig):
        return None
    return student_id


STUDENT_PRINCIPALS = {"S001", "S002", "S003", "S004", "S005"}
INSTRUCTOR_PRINCIPALS = {
    "instructor_alawini",
    "prof-alawini",
    "instructor-01",
    "instructor_ta",
    "instructor_audit",
    "instructor-admin",
}


def is_student_principal(principal: Optional[str]) -> bool:
    """Return True if principal is a recognized synthetic student."""
    return bool(principal and principal in STUDENT_PRINCIPALS)


def is_instructor_principal(principal: Optional[str]) -> bool:
    """Return True if principal is an authorized instructor."""
    if not principal or not isinstance(principal, str):
        return False
    if is_student_principal(principal):
        return False
    p = principal.lower().strip()
    return p in INSTRUCTOR_PRINCIPALS or p.startswith("instructor") or p.startswith("prof")


def create_signed_session_token(
    student_id: str,
    secret: Optional[bytes] = None,
    ttl_seconds: float = 86400.0,
    role: str = "student",
) -> str:
    """Generate a tamper-evident synthetic session token for a principal with a specified role."""
    sec = secret if secret is not None else get_auth_secret()
    expires_at = int(time.time() + ttl_seconds)
    payload = f"{student_id}:{role}:{expires_at}"
    sig = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{student_id}.{role}.{expires_at}.{sig}"


def verify_signed_session_token_role(
    token: str, secret: Optional[bytes] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Verify session token signature and expiration, returning (principal, role).
    Supports both 4-part tokens (principal.role.expires.sig) and legacy 3-part tokens (principal.expires.sig).
    Returns (principal, role) if valid, or (None, None) if invalid/expired.
    """
    if not isinstance(token, str):
        return None, None
    parts = token.strip().split(".")
    sec = secret if secret is not None else get_auth_secret()

    if len(parts) == 4:
        principal, role, expires_str, provided_sig = parts
        try:
            expires_at = int(expires_str)
        except ValueError:
            return None, None
        if time.time() > expires_at:
            return None, None
        payload = f"{principal}:{role}:{expires_at}"
        expected_sig = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None, None
        return principal, role

    if len(parts) == 3:
        principal, expires_str, provided_sig = parts
        try:
            expires_at = int(expires_str)
        except ValueError:
            return None, None
        if time.time() > expires_at:
            return None, None
        payload = f"{principal}:{expires_at}"
        expected_sig = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None, None
        return principal, "student"

    return None, None


def verify_signed_session_token(token: str, secret: Optional[bytes] = None) -> Optional[str]:
    """
    Verify session token signature and expiration.
    Returns authorized principal if valid, or None if invalid/expired.
    """
    principal, _ = verify_signed_session_token_role(token, secret)
    return principal
