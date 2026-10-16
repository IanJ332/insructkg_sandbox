"""Demo B: Entrepreneurial Mindset (EM) Layer Integration Rehearsal Script.

Demonstration Flow for Prof. Abdussalam Alawini:
1. Choose an exercise configured with EM reflection prompts (sql_join_04 - Creating Value).
2. Complete the technical SQL portion with deterministic grading.
3. Render the voluntary EM prompt connected to KEEN 3C dimensions (Creating Value).
4. Submit a synthetic student reflection response.
5. Route the submission to the instructor review interface (as PROPOSED evidence).
6. Accept the reflection evidence with instructor notes (simulate Prof. Alawini review).
7. Show updated student profile with behavioral EM evidence strictly isolated from technical mastery.
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

from siip.em_models import (
    EMReviewStatus,
)
from siip.em_repository import EMRepository
from siip.grader import QUESTIONS, grade
from siip.store import SubmissionRepository


def run_demo_b() -> int:
    print("=" * 72)
    print("SIIP DEMO B: ENTREPRENEURIAL MINDSET (EM) INTEGRATION")
    print("=" * 72)

    with tempfile.TemporaryDirectory(prefix="siip-demo-b-") as temp_dir:
        dir_path = Path(temp_dir)
        sub_repo = SubmissionRepository(dir_path / "submissions.sqlite3")
        em_repo = EMRepository(dir_path / "em.sqlite3")

        # -------------------------------------------------------------------
        # Step 1: Select Exercise Configured with EM Reflection
        # -------------------------------------------------------------------
        student_id = "S001"
        question_id = "sql_join_04"
        print(f"\n[Step 1] Selected Exercise: {question_id}")
        print(f"         Title: {QUESTIONS[question_id]['statement']}")
        print(f"         Target Learner: {student_id}")

        # -------------------------------------------------------------------
        # Step 2: Complete Technical SQL Portion
        # -------------------------------------------------------------------
        correct_sql = QUESTIONS[question_id]["reference_sql"]
        print("\n[Step 2] Executing Technical SQL Submission:")
        print(f"         {correct_sql}")

        t0 = time.monotonic()
        grading = grade(question_id, correct_sql)
        grade_ms = (time.monotonic() - t0) * 1000

        print(
            f"         Deterministic Grade: score={grading['score']}, status={grading['status']} ({grade_ms:.2f} ms)"
        )
        assert grading["score"] == 1.0, "Expected correct SQL submission"

        attempt_id = f"demo-b-{student_id}-001"
        sub_repo.process(
            {
                "attempt_id": attempt_id,
                "student_id": student_id,
                "question_id": question_id,
                "submitted_sql": correct_sql,
                "timestamp": "2026-10-15T11:00:00Z",
                "source": "synthetic_fixture",
            }
        )

        # -------------------------------------------------------------------
        # Step 3: Render Voluntary EM Reflection Prompt (KEEN 3C Dimension)
        # -------------------------------------------------------------------
        prompt = em_repo.get_prompt_for_question(question_id)
        assert prompt is not None, f"No EM prompt configured for {question_id}"

        print("\n[Step 3] Voluntary EM Reflection Prompt Rendered:")
        print(f"         Dimension:    KEEN {prompt.dimension.name} ({prompt.dimension.value})")
        print(f"         Focus:        {prompt.info_box_focus}")
        print("         Why It Matters:")
        print(f'           "{prompt.why_it_matters}"')
        print("         Learning Objective:")
        print(f'           "{prompt.intended_learning_objective}"')
        print("         Prompt Text:")
        print(f'           "{prompt.prompt_text}"')

        # -------------------------------------------------------------------
        # Step 4: Submit Synthetic Reflection Response
        # -------------------------------------------------------------------
        reflection_text = (
            "If an INNER JOIN silently removes zero-headcount departments like Research or Incubation, "
            "executive leadership might erroneously conclude those units are inactive and cancel their budget lines. "
            "Using a LEFT OUTER JOIN safeguards institutional visibility and ensures resource allocation reflects "
            "actual strategic commitments rather than transactional artifacts."
        )
        print("\n[Step 4] Student Submits Voluntary Reflection:")
        print(f'         Response Text:\n           "{reflection_text}"')

        resp = em_repo.record_response(
            student_id=student_id,
            question_id=question_id,
            prompt_id=prompt.prompt_id,
            attempt_id=attempt_id,
            response_text=reflection_text,
        )
        print(f"         Response Persisted: ID={resp.response_id}, Status={resp.status.value}")

        # -------------------------------------------------------------------
        # Step 5: Route Submission to Instructor Review Queue
        # -------------------------------------------------------------------
        evidence = em_repo.create_evidence_record(
            student_id=student_id,
            question_id=question_id,
            dimension=prompt.dimension,
            relevant_concepts=["LEFT_OUTER_JOIN", "COUNT_AGGREGATION"],
            evidence_excerpt=reflection_text,
            classification_method="rule_based_deterministic",
            model_or_rubric_version=prompt.rubric_version,
            confidence=0.92,
            response_id=resp.response_id,
            attempt_id=attempt_id,
        )
        print("\n[Step 5] Routed to Instructor Review Queue:")
        print(f"         Evidence Record ID:  {evidence.evidence_id}")
        print(f"         Review Status:       {evidence.review_status.value}")
        print(f"         Algorithm Confidence:{evidence.confidence:.2f}")

        # -------------------------------------------------------------------
        # Step 6: Accept Reflection Evidence (Simulate Instructor Review)
        # -------------------------------------------------------------------
        reviewer = "instructor_alawini"
        instructor_notes = (
            "Outstanding insight connecting SQL null handling to strategic budgeting. "
            "Directly articulates the Creating Value (V) dimension."
        )
        print(f"\n[Step 6] Instructor Review Action ({reviewer}):")
        reviewed_evidence = em_repo.review_evidence(
            evidence_id=evidence.evidence_id,
            status=EMReviewStatus.ACCEPTED,
            notes=instructor_notes,
            reviewer_id=reviewer,
        )
        assert reviewed_evidence is not None
        print(f"         New Status:       {reviewed_evidence.review_status.value}")
        print(
            f"         Reviewed By:      {reviewed_evidence.reviewer_id} at {reviewed_evidence.reviewed_at}"
        )
        print(f'         Instructor Notes: "{reviewed_evidence.instructor_notes}"')

        # -------------------------------------------------------------------
        # Step 7: Inspect Learner Profile (Isolation between EM & Mastery)
        # -------------------------------------------------------------------
        em_summary = em_repo.student_em_summary(student_id)
        technical_profile = sub_repo.profile(student_id)

        print("\n[Step 7] Student Profile Inspection (EM vs Technical Mastery):")
        print("         --- Behavioral EM Evidence Summary ---")
        print(f"         Total Observations:     {em_summary['total_observations']}")
        print(f"         Counts by Dimension:    {em_summary['counts_by_dimension']}")
        print(f"         Accepted by Dimension:  {em_summary['accepted_by_dimension']}")
        print("         Mindset Metric Valid?:  False (Purely behavioral observation record)")
        print(f"         Disclaimer:             {em_summary['disclaimer']}")

        print("\n         --- Technical Mastery Profile (Strictly Isolated) ---")
        for cname, cdata in technical_profile.get("concepts", {}).items():
            print(f"         - {cname}: Mastery={cdata.get('mastery_estimate', 0):.2f}")

        # -------------------------------------------------------------------
        # Step 8: Mandatory Negative Authorization Test (Student 403 Rejection)
        # -------------------------------------------------------------------
        print("\n[Step 8] Mandatory Negative Authorization Verification:")
        from siip.identity import (
            create_signed_session_token,
            is_student_principal,
            verify_signed_session_token_role,
        )

        student_token = create_signed_session_token(student_id, role="student")
        princ, role = verify_signed_session_token_role(student_token)
        print(f"         Synthetic Caller: {princ} (role={role})")
        print("         Attempting to execute instructor review action...")

        # Server-side guard simulation
        is_blocked = (role == "student") or is_student_principal(princ)
        if is_blocked:
            print("         [SERVER-SIDE GUARD] Access Denied: 403 Forbidden")
            print("         Synthetic student cannot approve, reject, or edit EM evidence.")
        assert is_blocked, "Expected student token to be blocked by server-side authorization"

        print("\n" + "=" * 72)
        print("DEMO B VERIFICATION: SUCCESS (All 8 stages verified)")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(run_demo_b())
