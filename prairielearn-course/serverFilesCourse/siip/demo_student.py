"""Thin student-journey orchestration for the isolated SIIP demonstration.

This module deliberately composes the production research-prototype services.  It
does not implement SQL grading, diagnosis, mastery estimation, feedback generation,
or recommendation rules.  Demo records use only the repository's synthetic learner
identities and are intended for a caller-supplied, isolated directory/database.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .demo_authoring import _validate_id
from .em_models import EMResponseStatus
from .em_repository import EMRepository
from .grader import QUESTIONS, public_grade
from .identity import is_student_principal
from .jobs import FeedbackJobRepository
from .recommender import recommend_next_activity
from .store import SubmissionRepository

FIXTURE_HISTORY_LABEL = "SYNTHETIC_FIXTURE_HISTORY"
LIVE_DEMO_LABEL = "ACTUAL_EXECUTION_WITH_SYNTHETIC_LEARNER"

# The intended misconception for sql_join_04.  It has the right projection and
# aggregation but drops unstaffed departments because it uses INNER JOIN.
INNER_JOIN_HEADCOUNT_SQL = (
    "SELECT d.department_name, COUNT(e.employee_id) AS employee_count "
    "FROM Departments d INNER JOIN Employees e "
    "ON d.department_id=e.department_id "
    "GROUP BY d.department_id, d.department_name "
    "ORDER BY d.department_name;"
)


def _load_assignment(value: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, Mapping):
        assignment = dict(value)
    else:
        path = Path(value)
        assignment = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(assignment, dict):
        raise ValueError("Published assignment must be a JSON object")

    required = {
        "assignment_id",
        "course_id",
        "question_id",
        "relevant_kg_node_ids",
        "publication_timestamp",
        "grading_configuration",
        "publication_status",
        "native_prairielearn_publication",
    }
    if not required <= assignment.keys():
        missing = ", ".join(sorted(required - assignment.keys()))
        raise ValueError(f"Published assignment is missing required fields: {missing}")
    if str(assignment["publication_status"]).upper() not in {
        "PUBLISHED_LOCAL_DEMO",
        "PUBLISHED",
    }:
        raise ValueError("Student submissions require a published assignment")
    if assignment["native_prairielearn_publication"] is not False:
        raise ValueError("Demo assignment must preserve native_prairielearn_publication=False")
    if assignment["question_id"] not in QUESTIONS:
        raise ValueError("Published assignment refers to an unknown SIIP question")
    if not isinstance(assignment["assignment_id"], str) or not assignment["assignment_id"]:
        raise ValueError("Published assignment requires a non-empty assignment_id")
    _validate_id(assignment["assignment_id"], "assignment_id")
    _validate_id(assignment["course_id"], "course_id")
    nodes = assignment["relevant_kg_node_ids"]
    if not isinstance(nodes, (list, tuple)) or not nodes:
        raise ValueError("Published assignment requires relevant KG nodes")
    for node in nodes:
        _validate_id(node, "relevant_kg_node_ids")
    if not isinstance(assignment["grading_configuration"], Mapping):
        raise ValueError("Published assignment requires a grading configuration")
    try:
        published_at = datetime.fromisoformat(
            assignment["publication_timestamp"].replace("Z", "+00:00")
        )
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Published assignment requires an ISO8601 publication timestamp") from exc
    if published_at.tzinfo is None:
        raise ValueError("Publication timestamp requires a timezone")
    return assignment


def _attempt_id(
    assignment_id: str,
    student_id: str,
    question_id: str,
    submission_key: str,
) -> str:
    """Return a replay-stable ID without treating the SQL itself as the identity."""
    identity = json.dumps(
        {
            "assignment_id": assignment_id,
            "student_id": student_id,
            "question_id": question_id,
            "submission_key": submission_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"demo-{hashlib.sha256(identity).hexdigest()[:24]}"


class DemoStudentJourney:
    """Orchestrate student demo actions through existing SIIP repositories.

    Pass ``demo_directory`` to get isolated ``submissions.sqlite3`` and
    ``feedback_jobs.sqlite3`` stores, or inject both repositories explicitly.
    The adapter enqueues feedback but never runs a worker in the grading request,
    so provider inference cannot delay or change the deterministic grade.
    """

    def __init__(
        self,
        demo_directory: str | Path | None = None,
        *,
        submission_store: SubmissionRepository | None = None,
        feedback_jobs: FeedbackJobRepository | None = None,
        em_store: EMRepository | None = None,
    ) -> None:
        if demo_directory is None and (submission_store is None or feedback_jobs is None):
            raise ValueError(
                "Supply an isolated demo_directory or both submission_store and feedback_jobs"
            )
        directory = Path(demo_directory) if demo_directory is not None else None
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
        self.submissions = submission_store or SubmissionRepository(
            directory / "submissions.sqlite3"  # type: ignore[operator]
        )
        self.feedback_jobs = feedback_jobs or FeedbackJobRepository(
            directory / "feedback_jobs.sqlite3"  # type: ignore[operator]
        )
        self.em = em_store or (EMRepository(directory / "em.sqlite3") if directory else None)

    def submit(
        self,
        published_assignment: Mapping[str, Any] | str | Path,
        student_id: str,
        submitted_sql: str,
        *,
        submission_key: str = "primary-demo-submission",
        timestamp: str | None = None,
        feedback_mode: str = "kg",
    ) -> dict[str, Any]:
        """Persist, deterministically grade, diagnose, and enqueue one submission.

        ``submission_key`` represents the UI/platform submission event.  Replaying
        the same event is idempotent; callers should use a new key for a genuine
        retry even when its SQL text is identical.
        """
        assignment = _load_assignment(published_assignment)
        if not is_student_principal(student_id):
            raise PermissionError("A recognized synthetic student principal is required")
        if feedback_mode not in {"baseline", "rag", "kg"}:
            raise ValueError("Unknown feedback mode")
        if (
            not isinstance(submitted_sql, str)
            or not submitted_sql.strip()
            or len(submitted_sql) > 12000
        ):
            raise ValueError("submitted_sql must be a non-empty string")
        if not isinstance(submission_key, str) or not submission_key or len(submission_key) > 160:
            raise ValueError("submission_key must be a non-empty string")

        question_id = assignment["question_id"]
        attempt_id = _attempt_id(
            assignment["assignment_id"],
            student_id,
            question_id,
            submission_key,
        )

        # Preserve replay idempotence: the original persisted timestamp wins.
        try:
            saved = self.submissions.attempt_for_student(attempt_id, student_id)
            if saved["submitted_sql"] != submitted_sql:
                raise ValueError("submission_key was replayed with a conflicting SQL payload")
            if (
                saved["assessment_id"] != assignment["assignment_id"]
                or saved["question_id"] != question_id
            ):
                raise ValueError("submission_key was replayed for a conflicting assignment")
        except PermissionError:
            saved = self.submissions.process(
                {
                    "attempt_id": attempt_id,
                    "student_id": student_id,
                    "question_id": question_id,
                    "submitted_sql": submitted_sql,
                    "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                    "source": "synthetic_fixture",
                    "assessment_id": assignment["assignment_id"],
                },
                # Repository persistence requires a feedback mode.  With no
                # provider this is bounded local deterministic work, never LLM
                # inference.  Rich feedback remains asynchronous below.
                mode="baseline",
                provider=None,
            )

        job = self.feedback_jobs.enqueue(
            attempt_id=attempt_id,
            student_id=student_id,
            question_id=question_id,
            submitted_sql=saved["submitted_sql"],
            grading=saved["grading"],
            mode=feedback_mode,
            attempt_kind="authoritative",
            **(
                {"grounding": assignment["feedback_grounding"]}
                if assignment.get("feedback_grounding") is not None
                else {}
            ),
        )
        return {
            "assignment_id": assignment["assignment_id"],
            "publication_status": assignment["publication_status"],
            "native_prairielearn_publication": assignment["native_prairielearn_publication"],
            "student_id": student_id,
            "question_id": question_id,
            "attempt_id": attempt_id,
            "timestamp": saved["timestamp"],
            "submitted_sql": saved["submitted_sql"],
            "grading": public_grade(saved["grading"]),
            "diagnosis": saved["diagnosis"],
            "concepts": saved["concepts"],
            "feedback_job": {
                "job_id": job.job_id,
                "status": job.status,
                "attempt_id": job.attempt_id,
            },
            "history_classification": LIVE_DEMO_LABEL,
            "provenance": {
                "grading": "siip.grader via SubmissionRepository.process",
                "diagnosis": saved["diagnosis"].get("diagnosis_source"),
                "feedback": "durable asynchronous queue; worker not run in submit request",
            },
        }

    def seed_fixture_histories(self) -> dict[str, Any]:
        """Install small, explicit fixture histories for S001 and S002.

        S001 has one failed inner-join fundamentals attempt.  S002 has successful
        inner- and left-join attempts.  Every row is graded and persisted through
        the ordinary repository, rather than injecting mastery estimates.
        """
        fixtures = [
            {
                "attempt_id": "fixture-history-s001-inner-gap-v1",
                "student_id": "S001",
                "question_id": "sql_join_01",
                "submitted_sql": (
                    "SELECT e.name, d.department_name FROM Employees e "
                    "LEFT JOIN Departments d ON e.department_id=d.department_id;"
                ),
                "timestamp": "2026-10-18T14:00:00Z",
                "source": "synthetic_fixture",
                "assessment_id": "fixture-prior-history",
            },
            {
                "attempt_id": "fixture-history-s002-inner-success-v1",
                "student_id": "S002",
                "question_id": "sql_join_01",
                "submitted_sql": QUESTIONS["sql_join_01"]["reference_sql"],
                "timestamp": "2026-10-18T14:05:00Z",
                "source": "synthetic_fixture",
                "assessment_id": "fixture-prior-history",
            },
            {
                "attempt_id": "fixture-history-s002-left-success-v1",
                "student_id": "S002",
                "question_id": "sql_join_02",
                "submitted_sql": QUESTIONS["sql_join_02"]["reference_sql"],
                "timestamp": "2026-10-18T14:10:00Z",
                "source": "synthetic_fixture",
                "assessment_id": "fixture-prior-history",
            },
        ]
        records = self.submissions.process_many(fixtures, mode="baseline", provider=None)
        return {
            "classification": FIXTURE_HISTORY_LABEL,
            "description": (
                "Locally authored synthetic prior attempts for demonstration only; "
                "not empirical student records or measured learning outcomes."
            ),
            "attempt_ids": [record["attempt_id"] for record in records],
        }

    def profiles_and_recommendations(
        self, student_ids: Sequence[str] = ("S001", "S002")
    ) -> dict[str, Any]:
        """Expose profiles and actual recommender outputs from persisted histories."""
        students: dict[str, Any] = {}
        for student_id in student_ids:
            if not is_student_principal(student_id):
                raise PermissionError("A recognized synthetic student principal is required")
            profile = self.submissions.profile(student_id)
            students[student_id] = {
                "profile": profile,
                "recommendation": recommend_next_activity(student_id, profile),
                "history_sources": [
                    {
                        "attempt_id": row["attempt_id"],
                        "classification": (
                            FIXTURE_HISTORY_LABEL
                            if row["attempt_id"].startswith("fixture-history-")
                            else LIVE_DEMO_LABEL
                        ),
                    }
                    for row in profile["history"]
                ],
            }
        return {
            "synthetic": True,
            "fixture_history_label": FIXTURE_HISTORY_LABEL,
            "students": students,
        }

    def em_prompt(self, question_id: str) -> dict[str, Any] | None:
        """Return the existing optional EM prompt for a question, if configured."""
        if self.em is None:
            raise RuntimeError("No EMRepository was supplied for this demo journey")
        prompt = self.em.get_prompt_for_question(question_id)
        return prompt.to_dict() if prompt else None

    def submit_em_reflection(
        self, student_id: str, attempt_id: str, response_text: str
    ) -> dict[str, Any]:
        """Persist an optional response and create review-required EM evidence.

        The existing EM repository creates evidence in ``PROPOSED`` state.  This
        method intentionally does not perform instructor review and does not alter
        the student's technical mastery profile.
        """
        if self.em is None:
            raise RuntimeError("No EMRepository was supplied for this demo journey")
        if not isinstance(response_text, str) or not response_text.strip():
            raise ValueError("response_text must be non-empty")
        attempt = self.submissions.attempt_for_student(attempt_id, student_id)
        prompt = self.em.get_prompt_for_question(attempt["question_id"])
        if prompt is None:
            raise ValueError("This question has no configured optional EM reflection")

        response = self.em.record_response(
            student_id=student_id,
            question_id=attempt["question_id"],
            prompt_id=prompt.prompt_id,
            attempt_id=attempt_id,
            response_text=response_text.strip(),
            status=EMResponseStatus.SUBMITTED,
        )
        evidence = self.em.create_evidence_record(
            student_id=student_id,
            question_id=attempt["question_id"],
            dimension=prompt.dimension,
            relevant_concepts=list(attempt["concepts"]),
            evidence_excerpt=response.response_text,
            classification_method="rule_based_deterministic",
            model_or_rubric_version=prompt.rubric_version,
            response_id=response.response_id,
            attempt_id=attempt_id,
        )
        return {
            "optional": True,
            "technical_mastery_separate": True,
            "prompt": prompt.to_dict(),
            "response": response.to_dict(),
            "evidence": evidence.to_dict(),
        }


__all__ = [
    "DemoStudentJourney",
    "FIXTURE_HISTORY_LABEL",
    "INNER_JOIN_HEADCOUNT_SQL",
    "LIVE_DEMO_LABEL",
]
