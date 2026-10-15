"""Read-only input boundaries; no fabricated PrairieLearn submission writes."""

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from .configuration import LOCAL_HOSTS
from .grader import QUESTIONS


class APIReadError(RuntimeError):
    """Sanitized read failure; response bodies and tokens are never propagated."""


def pl_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Invalid PrairieLearn identifier")
    value = str(value)
    if not value.isascii() or not value.isdigit() or not 0 < int(value) or len(value) > 20:
        raise ValueError("Invalid PrairieLearn identifier")
    return str(int(value))


class SubmissionSource(Protocol):
    def records(self): ...


class SyntheticFixtureSource:
    def __init__(self, path):
        self.path = Path(path)

    def records(self):
        return json.loads(self.path.read_text())


def normalize_pl(record, identity_map):
    """Fields verified against official SubmissionDataSchema. Never persist names/UID/UIN."""
    if not isinstance(record, dict) or record.get("group_id") is not None:
        raise ValueError("Individual submissions only; group identity is not authorized")
    sid = identity_map.get(pl_id(record.get("user_id")))
    if sid is None:
        raise ValueError(
            "Missing authorized pseudonymous identity mapping; team records need separate approval"
        )
    qid = record.get("question_name")
    if qid not in QUESTIONS:
        raise ValueError("Question outside sandbox allowlist")
    answer = record.get("submitted_answer")
    if not isinstance(answer, dict) or not isinstance(answer.get("sql"), str):
        raise ValueError("Unsupported submitted_answer mapping")
    return {
        "student_id": sid,
        "question_id": qid,
        "attempt_id": "pl-" + pl_id(record["submission_id"]),
        "timestamp": record["date"],
        "submitted_sql": answer["sql"],
        "assessment_id": pl_id(record["assessment_id"]),
        "external_links": {
            k: pl_id(record[k]) for k in ["assessment_instance_id", "variant_id", "submission_id"]
        },
        "external_score": record.get("score"),
    }


class LocalPrairieLearnSource:
    """Consumes authorized export files, not a connection to PL's internal database."""

    def __init__(self, path, identity_map):
        self.path, self.identity_map = Path(path), identity_map

    def records(self):
        return [
            {**normalize_pl(row, self.identity_map), "source": "local_prairielearn_export"}
            for row in json.loads(self.path.read_text())
        ]


class AuthorizedPrairieLearnAPISource:
    def __init__(
        self,
        base_url,
        token,
        course_instance_id,
        assessment_instance_id,
        identity_map,
        authorized=False,
        assessment_id=None,
    ):
        if not authorized:
            raise PermissionError("Explicit authorization and course-instance scope required")
        course_instance_id, assessment_instance_id = (
            pl_id(course_instance_id),
            pl_id(assessment_instance_id),
        )
        if not isinstance(token, str) or not token or any(c in token for c in "\r\n"):
            raise ValueError("Authorized read token required")
        from .store import STUDENTS

        if (
            not isinstance(identity_map, dict)
            or len(identity_map) != 1
            or any(pl_id(k) != k or v not in STUDENTS for k, v in identity_map.items())
        ):
            raise ValueError(
                "One explicitly mapped synthetic owner per assessment instance required"
            )
        parsed = urlparse(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid API endpoint")
        if parsed.scheme != "https" and parsed.hostname not in LOCAL_HOSTS:
            raise ValueError("Nonlocal API endpoints require HTTPS")
        self.url = (
            base_url.rstrip("/")
            + "/pl/api/v1/course_instances/"
            + str(course_instance_id)
            + "/assessment_instances/"
            + str(assessment_instance_id)
            + "/submissions"
        )
        self.token, self.identity_map = token, identity_map
        self.assessment_instance_id = assessment_instance_id
        self.assessment_id = pl_id(assessment_id) if assessment_id is not None else None
        self.scope = hashlib.sha256(self.url.encode()).hexdigest()

    def records(self):
        return self.read_snapshot()[0]

    def read_snapshot(self):
        request = urllib.request.Request(self.url, headers={"Private-Token": self.token})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        try:
            with opener.open(request, timeout=10) as response:
                if response.headers.get("Link"):
                    raise APIReadError("Unsupported API pagination; no checkpoint advanced")
                body = response.read(8_388_609)
                if len(body) > 8_388_608:
                    raise APIReadError("API response exceeds local safety bound")
                rows = json.loads(body)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise PermissionError("API read permission denied") from None
            raise APIReadError("API HTTP status " + str(exc.code)) from None
        except (OSError, ValueError):
            raise APIReadError("API unavailable or malformed JSON") from None
        if not isinstance(rows, list) or len(rows) > 10_000:
            raise APIReadError("Expected bounded API submission array")
        records = []
        deferred_count = 0
        for row in rows:
            normalized = normalize_pl(row, self.identity_map)
            if (
                normalized["external_links"]["assessment_instance_id"]
                != self.assessment_instance_id
            ):
                raise ValueError("Submission outside authorized assessment-instance scope")
            if self.assessment_id and normalized["assessment_id"] != self.assessment_id:
                raise ValueError("Submission outside authorized assessment scope")
            # A null grade is pending, never a zero. Revisit it on the next full poll.
            from .store import SubmissionRepository

            if normalized["external_score"] is None:
                SubmissionRepository.normalize(
                    {k: v for k, v in normalized.items() if k != "external_score"}
                )
                deferred_count += 1
                continue
            normalized["attempt_id"] = (
                "pl-api-" + self.scope[:20] + "-" + normalized["external_links"]["submission_id"]
            )
            records.append(
                SubmissionRepository.normalize(
                    {**normalized, "source": "authorized_prairielearn_api"}
                )
            )
        return records, deferred_count


def pseudonym(user_id, secret):
    if len(secret) < 32:
        raise ValueError("Use an approved secret of at least 32 bytes")
    return hmac.new(secret, str(user_id).encode(), hashlib.sha256).hexdigest()[:24]
