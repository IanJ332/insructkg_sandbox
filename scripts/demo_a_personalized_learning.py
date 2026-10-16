"""Demo A: Integrated Personalized Learning Rehearsal Script.

Demonstration Flow for Prof. Abdussalam Alawini:
1. Select synthetic learner (S001) from the course cohort.
2. Submit a real SQL query triggering an inner-versus-outer join error.
3. Show deterministic grading completing immediately (< 50 ms).
4. Show asynchronous background feedback generation (candidate concepts & lecture references).
5. Inspect learner profile showing updated concept evidence.
6. Trigger an adaptive next-activity recommendation grounded in the updated profile.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

# Ensure default data dir if not set
if "SIIP_DATA_DIR" not in os.environ:
    os.environ["SIIP_DATA_DIR"] = str(ROOT / "artifacts/public-data")

from siip.grader import QUESTIONS, grade
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.recommender import recommend_next_activity
from siip.store import SubmissionRepository


def run_demo_a(dir_path: Path | None = None) -> int:
    print("=" * 72)
    print("SIIP DEMO A: INTEGRATED PERSONALIZED LEARNING")
    print("=" * 72)

    temp_mgr = tempfile.TemporaryDirectory(prefix="siip-demo-a-") if dir_path is None else None
    try:
        active_dir = Path(temp_mgr.name) if temp_mgr else dir_path
        sub_repo = SubmissionRepository(active_dir / "submissions.sqlite3")
        jobs_repo = FeedbackJobRepository(active_dir / "jobs.sqlite3")
        worker = FeedbackWorker(jobs_repo, submission_repo=sub_repo)

        # -------------------------------------------------------------------
        # Step 1: Select Synthetic Learner
        # -------------------------------------------------------------------
        student_id = "S001"
        question_id = "sql_join_02"
        print(f"\n[Step 1] Selected Synthetic Learner: {student_id}")
        print(f"         Target Question: {question_id} - '{QUESTIONS[question_id]['statement']}'")
        print(f"         Required Concepts: {QUESTIONS[question_id].get('concepts', [])}")

        # -------------------------------------------------------------------
        # Step 2: Student SQL Submission (Triggers Inner vs Outer Join error)
        # -------------------------------------------------------------------
        # This query executes successfully but omits Carol (NULL department) due to INNER JOIN
        student_sql = "SELECT e.name, d.department_name FROM Employees e INNER JOIN Departments d ON e.department_id = d.department_id;"
        print("\n[Step 2] Submitted SQL Query:")
        print(f"         {student_sql}")

        # -------------------------------------------------------------------
        # Step 3: Deterministic Grading (< 50 ms target)
        # -------------------------------------------------------------------
        t0 = time.monotonic()
        grading_result = grade(question_id, student_sql)
        grade_latency_ms = (time.monotonic() - t0) * 1000

        print("\n[Step 3] Deterministic Grading Result:")
        print(f"         Status:      {grading_result['status']}")
        print(f"         Score:       {grading_result['score']}")
        print(f"         Observation: {grading_result.get('observation', 'none')}")
        print(f"         Latency:     {grade_latency_ms:.2f} ms")
        assert grading_result["score"] == 0.0, "Expected non-passing score for demonstration"

        # Record submission in historical submission store
        attempt_id = f"demo-a-{student_id}-001"
        sub_repo.process(
            {
                "attempt_id": attempt_id,
                "student_id": student_id,
                "question_id": question_id,
                "submitted_sql": student_sql,
                "timestamp": "2026-10-15T10:00:00Z",
                "source": "synthetic_fixture",
            }
        )

        # -------------------------------------------------------------------
        # Step 4: Asynchronous Feedback Job Enqueued and Processed
        # -------------------------------------------------------------------
        print("\n[Step 4] Enqueueing Asynchronous Feedback Job...")
        job = jobs_repo.enqueue(
            attempt_id=attempt_id,
            student_id=student_id,
            question_id=question_id,
            submitted_sql=student_sql,
            grading=grading_result,
            mode="kg",
        )
        print(f"         Job Enqueued: ID={job.job_id}, Status={job.status}")

        print("         Processing Job via FeedbackWorker...")
        t_worker_0 = time.monotonic()
        completed_job = worker.process_one()
        worker_elapsed_ms = (time.monotonic() - t_worker_0) * 1000

        assert completed_job is not None and completed_job.status == "completed"
        fb_result = completed_job.result or {}
        print(f"         Worker Completed in: {worker_elapsed_ms:.2f} ms")
        print(f"         Model Identifier:    {completed_job.model_identifier}")
        print(f"         Candidate Concepts:  {fb_result.get('candidate_concepts', [])}")
        print(f"         Lecture Evidence:    {fb_result.get('evidence_references', [])}")
        print(f"         Generated Feedback:  {fb_result.get('feedback_text', '')}")

        # -------------------------------------------------------------------
        # Step 5: Inspect Updated Learner Profile
        # -------------------------------------------------------------------
        profile = sub_repo.profile(student_id)
        print(f"\n[Step 5] Updated Learner Profile for {student_id}:")
        print(f"         Total Submissions: {profile.get('total_submissions', 0)}")
        concepts = profile.get("concepts", {})
        for cname, cdata in concepts.items():
            print(
                f"         - {cname}: Mastery={cdata.get('mastery_estimate', 0):.2f} (evidence={cdata.get('attempt_count', 0)})"
            )

        # -------------------------------------------------------------------
        # Step 6: Adaptive Next-Activity Recommendation
        # -------------------------------------------------------------------
        rec = recommend_next_activity(student_id, profile)
        print("\n[Step 6] Adaptive Next-Activity Recommendation (S001):")
        print(
            f"         Recommended Question: {rec['recommended_question_id']} - {rec['question_title']}"
        )
        print(f"         Target Concepts:      {rec['target_concepts']}")
        print(f"         Pedagogical Rationale: {rec['rationale']}")
        print(f"         Triggered Rule:       {rec['rule_id']}")

        # -------------------------------------------------------------------
        # Step 7: Second Student Demonstration (S002 with distinct mastery)
        # -------------------------------------------------------------------
        print("\n[Step 7] Second Student Demonstration (S002):")
        # S002 has successfully mastered inner joins and basic outer joins
        sub_repo.process(
            {
                "attempt_id": "demo-a-s002-001",
                "student_id": "S002",
                "question_id": "sql_join_01",
                "submitted_sql": QUESTIONS["sql_join_01"]["reference_sql"],
                "timestamp": "2026-10-15T09:00:00Z",
                "source": "synthetic_fixture",
            }
        )
        sub_repo.process(
            {
                "attempt_id": "demo-a-s002-002",
                "student_id": "S002",
                "question_id": "sql_join_02",
                "submitted_sql": QUESTIONS["sql_join_02"]["reference_sql"],
                "timestamp": "2026-10-15T09:30:00Z",
                "source": "synthetic_fixture",
            }
        )
        s002_profile = sub_repo.profile("S002")
        s002_rec = recommend_next_activity("S002", s002_profile)

        print("         Learner:              S002 (Foundational Joins Mastered)")
        print(
            f"         Recommended Question: {s002_rec['recommended_question_id']} - {s002_rec['question_title']}"
        )
        print(f"         Target Concepts:      {s002_rec['target_concepts']}")
        print(f"         Pedagogical Rationale: {s002_rec['rationale']}")
        print(f"         Triggered Rule:       {s002_rec['rule_id']}")

        assert rec["recommended_question_id"] != s002_rec["recommended_question_id"], (
            "Recommendations for S001 and S002 must differ based on individual profile history"
        )
        print(
            f"\n[Validation] Differential recommendation verified: S001 -> {rec['recommended_question_id']}, S002 -> {s002_rec['recommended_question_id']}"
        )

        print("\n" + "=" * 72)
        print("DEMO A VERIFICATION: SUCCESS (All 7 stages verified)")
        print("=" * 72)
        return 0
    finally:
        if temp_mgr:
            temp_mgr.cleanup()


if __name__ == "__main__":
    sys.exit(run_demo_a())
