"""Supported PL hook. Feedback failure must never change a completed SQL grade.
Decouples deterministic SQL grading from synchronous generative LLM inference.
Enforces safe synthetic student identity resolution and fail-closed personalization.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid

from .feedback import configured_provider, generate_feedback
from .grader import QUESTIONS, grade
from .identity import resolve_student_identity
from .observability import event


def generate_question(data, qid):
    data["params"]["statement"] = QUESTIONS[qid]["statement"]
    data["correct_answers"]["sql"] = ""


def grade_question(data, qid):
    started = time.monotonic()
    correlation = str(uuid.uuid4())
    sql = data.get("submitted_answers", {}).get("sql", "")
    result = grade(qid, sql)
    latency = round((time.monotonic() - started) * 1000, 3)
    data["score"] = float(result["score"])
    data["partial_scores"] = data.get("partial_scores", {})
    data["partial_scores"]["sql"] = {"score": float(result["score"]), "weight": 1}
    event(
        "grade_completed",
        correlation_id=correlation,
        question_id=qid,
        status=result["status"],
        score=result["score"],
        latency_ms=latency,
    )

    job_id = None
    job_repo_path = os.environ.get("SIIP_FEEDBACK_JOBS_DB")
    async_enabled = os.environ.get("SIIP_ASYNC_FEEDBACK") == "1" or bool(job_repo_path)

    try:
        provider = configured_provider()
        if async_enabled and provider is not None:
            # Asynchronous path: deterministic grading finishes immediately.
            # Generative inference is enqueued as a durable feedback job.
            from .jobs import FeedbackJobRepository

            repo_path = (
                job_repo_path
                or (
                    os.environ.get("SIIP_DATA_DIR")
                    and f"{os.environ['SIIP_DATA_DIR']}/feedback_jobs.sqlite3"
                )
                or "artifacts/feedback_jobs.sqlite3"
            )
            job_repo = FeedbackJobRepository(repo_path)

            student_id, is_trusted, id_reason = resolve_student_identity(data)
            if is_trusted and student_id:
                # Deterministic stable attempt ID from submission_id or student/question/sql/variant hash
                sub_id = data.get("submission_id") or data.get("variant_id")
                if sub_id:
                    attempt_id = f"pl-{sub_id}"
                else:
                    variant_seed = data.get("variant_seed", 0)
                    sig = hashlib.sha256(
                        f"{student_id}:{qid}:{sql}:{variant_seed}".encode()
                    ).hexdigest()[:20]
                    attempt_id = f"sub-{sig}"

                job = job_repo.enqueue(
                    attempt_id=attempt_id,
                    student_id=student_id,
                    question_id=qid,
                    submitted_sql=sql,
                    grading=result,  # job_repo minimizes this to public_grade
                    mode="kg",
                )
                job_id = job.job_id
                feedback = generate_feedback(qid, sql, result, mode="baseline")
                feedback["inference_status"] = "async_job_queued"
                feedback["job_id"] = job_id
                feedback["personalization_status"] = "personalized_async_queued"
                feedback["student_id"] = student_id
            else:
                # Fail closed: trusted identity unavailable. Return clearly labeled non-personalized feedback.
                feedback = generate_feedback(qid, sql, result, mode="baseline")
                feedback["inference_status"] = "immediate_baseline_non_personalized"
                feedback["personalization_status"] = f"non_personalized_{id_reason}"
                feedback["student_id"] = None
                job_id = None
        else:
            student_id, is_trusted, id_reason = resolve_student_identity(data)
            mode = "kg" if is_trusted else "baseline"
            feedback = generate_feedback(qid, sql, result, mode=mode, provider=provider)
            feedback["personalization_status"] = (
                "personalized_synchronous" if is_trusted else f"non_personalized_{id_reason}"
            )
            feedback["student_id"] = student_id
    except Exception as exc:
        feedback = generate_feedback(qid, sql, result, mode="baseline")
        feedback["inference_status"] = "feedback_error_fallback"
        feedback["error_details"] = type(exc).__name__
        feedback["personalization_status"] = "non_personalized_error_fallback"
        feedback["student_id"] = None
        event("feedback_failed", correlation_id=correlation, error_type=type(exc).__name__)

    data["feedback"] = data.get("feedback", {})
    data["feedback"].update(
        {
            "status": result["status"],
            "guidance": feedback["feedback_text"],
            "concepts": "Possible concept gaps: " + ", ".join(feedback["candidate_concepts"]),
            "grounding": "Lecture references: "
            + (", ".join(feedback["evidence_references"]) or "unavailable")
            + ". Graph support is provisional; original judgments await instructor review.",
            "inference": feedback["inference_status"] + " · " + feedback["model_identifier"],
            "job_id": job_id,
            "student_id": feedback.get("student_id"),
            "siip": {
                "feedback_origin": "prairielearn_hook_immediate",
                "question_id": qid,
                "grading_status": result["status"],
                "observation": result["observation"],
                "correlation_id": correlation,
                "grading_latency_ms": latency,
                "feedback": feedback,
                "job_id": job_id,
                "student_id": feedback.get("student_id"),
                "personalization_status": feedback.get("personalization_status"),
            },
        }
    )
