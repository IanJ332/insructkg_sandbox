"""Supported PL hook. Feedback failure must never change a completed SQL grade."""

import time
import uuid

from .feedback import configured_provider, generate_feedback
from .grader import QUESTIONS, grade
from .observability import event


def generate_question(data, qid):
    data["params"]["statement"] = QUESTIONS[qid]["statement"]
    data["correct_answers"]["sql"] = ""


def grade_question(data, qid):
    started = time.monotonic()
    correlation = str(uuid.uuid4())
    sql = data["submitted_answers"].get("sql", "")
    result = grade(qid, sql)
    latency = round((time.monotonic() - started) * 1000, 3)
    data["score"] = float(result["score"])
    data["partial_scores"]["sql"] = {"score": float(result["score"]), "weight": 1}
    event(
        "grade_completed",
        correlation_id=correlation,
        question_id=qid,
        status=result["status"],
        score=result["score"],
        latency_ms=latency,
    )
    try:
        provider = configured_provider()
        feedback = generate_feedback(qid, sql, result, mode="kg", provider=provider)
    except Exception as exc:
        feedback = generate_feedback(qid, sql, result, mode="baseline")
        feedback["inference_status"] = "feedback_error_fallback"
        feedback["error_details"] = type(exc).__name__
        event("feedback_failed", correlation_id=correlation, error_type=type(exc).__name__)
    data["feedback"].update(
        {
            "status": result["status"],
            "guidance": feedback["feedback_text"],
            "concepts": "Possible concept gaps: " + ", ".join(feedback["candidate_concepts"]),
            "grounding": "Lecture references: "
            + (", ".join(feedback["evidence_references"]) or "unavailable")
            + ". Graph support is provisional; original judgments await instructor review.",
            "inference": feedback["inference_status"] + " · " + feedback["model_identifier"],
            "siip": {
                "question_id": qid,
                "grading_status": result["status"],
                "observation": result["observation"],
                "correlation_id": correlation,
                "grading_latency_ms": latency,
                "feedback": feedback,
            },
        }
    )
