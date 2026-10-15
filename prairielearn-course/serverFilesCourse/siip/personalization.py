"""Authorized post-submission feedback for the synthetic prototype.

A principal is supplied by a trusted application, never inferred from PL hook data.
The synthetic grant factory is not an institutional authentication mechanism.
"""

from dataclasses import dataclass

from .feedback import generate_feedback
from .store import STUDENTS


@dataclass(frozen=True)
class FeedbackPrincipal:
    student_id: str
    scope: str


def synthetic_principal(student_id, *, authorized=False):
    if not authorized or student_id not in STUDENTS:
        raise PermissionError("Explicit synthetic feedback authorization required")
    return FeedbackPrincipal(student_id, "synthetic_profile_feedback")


def feedback_for_attempt(repo, attempt_id, principal, *, provider=None):
    """Use only this student's strictly earlier persisted evidence.

    Current/equal-time/future attempts are excluded. The returned receipt and model
    context contain aggregate concepts, not identifiers or historical SQL.
    """
    if (
        not isinstance(principal, FeedbackPrincipal)
        or principal.scope != "synthetic_profile_feedback"
        or principal.student_id not in STUDENTS
    ):
        raise PermissionError("Feedback access denied")
    record = repo.attempt_for_student(attempt_id, principal.student_id)
    profile = repo.profile(principal.student_id, as_of=record["timestamp"], before=True)
    feedback = generate_feedback(
        record["question_id"],
        record["submitted_sql"],
        record["grading"],
        mode="kg",
        mastery=profile["concepts"],
        provider=provider,
    )
    return {
        "feedback": feedback,
        "evidence_receipt": {
            "scope": "synthetic_only",
            "cutoff": record["timestamp"],
            "policy": "strictly_before_current_timestamp",
            "prior_attempt_count": profile["attempt_count"],
            "eligible_concept_count": feedback["historical_personalization"]["concept_count"],
            "source": "persisted_synthetic_student_profile",
            "profile_version": "beta-heuristic-v1",
            "grade_changed": False,
            "delivery": "post_submission_local_service; not injected into PL",
        },
    }
