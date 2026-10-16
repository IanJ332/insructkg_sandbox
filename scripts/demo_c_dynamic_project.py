"""Demo C: Personalized Project Generation Rehearsal Script.

Demonstration Flow for Prof. Abdussalam Alawini:
1. Select a learner with documented interests (S001 -> Healthcare & Medical Devices).
2. Trigger the 3-stage dynamic project generator.
3. Validate that generated milestones, schemas, and queries conform to the verified schema
   and pass sandbox in-memory SQLite execution checks.
4. Present the generated project in the instructor review view.
5. Simulate instructor approving the project with pedagogical notes and revisions.
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

from siip.project_generator import (
    STUDENT_INTEREST_PROFILES,
    ProjectRepository,
    generate_personalized_project,
    verify_project_schema_and_queries,
)
from siip.project_models import StudentInterest


def run_demo_c() -> int:
    print("=" * 72)
    print("SIIP DEMO C: PERSONALIZED PROJECT GENERATION")
    print("=" * 72)

    with tempfile.TemporaryDirectory(prefix="siip-demo-c-") as temp_dir:
        dir_path = Path(temp_dir)
        proj_repo = ProjectRepository(dir_path / "projects.sqlite3")

        # -------------------------------------------------------------------
        # Step 1: Learner Selection and Documented Interests
        # -------------------------------------------------------------------
        student_id = "S001"
        profile_data = STUDENT_INTEREST_PROFILES.get(student_id, {})
        interest = profile_data.get("interest", StudentInterest.HEALTHCARE.value)
        goals = profile_data.get("career_goals", "Clinical data analytics")

        print("\n[Step 1] Learner Interest Profile Selected:")
        print(f"         Student ID:   {student_id}")
        print(f"         Domain:       {interest.upper()}")
        print(f"         Career Goals: {goals}")
        print(
            f"         Background:   {profile_data.get('background', 'Undergraduate Engineering')}"
        )

        # -------------------------------------------------------------------
        # Step 2: Trigger 3-Stage Dynamic Project Generator
        # -------------------------------------------------------------------
        print("\n[Step 2] Triggering 3-Stage Dynamic Project Generator...")
        t0 = time.monotonic()
        project = generate_personalized_project(student_id=student_id, interest=interest)
        gen_elapsed_ms = (time.monotonic() - t0) * 1000

        print(f"         Generation Time:      {gen_elapsed_ms:.2f} ms")
        print(f"         Generated Project ID: {project.project_id}")
        print(f'         Title:                "{project.title}"')
        print(f"         Target Concepts:      {project.target_concepts}")
        print(f"         Approval Status:      {project.instructor_approval_status}")

        # -------------------------------------------------------------------
        # Step 3: Sandboxed Execution & Verification (In-Memory SQLite)
        # -------------------------------------------------------------------
        print("\n[Step 3] Sandboxed DDL and Query Verification (In-Memory SQLite):")
        t_ver_0 = time.monotonic()
        is_verified = verify_project_schema_and_queries(project)
        ver_elapsed_ms = (time.monotonic() - t_ver_0) * 1000

        print(f"         Schema & Query Validated: {is_verified} ({ver_elapsed_ms:.2f} ms)")
        assert is_verified, "Project failed schema/query in-memory execution test!"

        # -------------------------------------------------------------------
        # Step 4: Present Generated Project in Instructor Review View
        # -------------------------------------------------------------------
        print("\n[Step 4] Project Specification for Instructor Review:")
        print(f'         Scenario Narrative:\n           "{project.scenario_narrative}"')
        print("\n         Relational Schema DDL Preview:")
        for line in project.schema_ddl.strip().splitlines()[:6]:
            print(f"           {line}")
        print(f"           ... ({len(project.schema_ddl.splitlines())} lines total)")

        print(f"\n         Decomposed Milestones ({len(project.milestones)} milestones):")
        for m in project.milestones:
            print(
                f"           [Milestone {m.milestone_index}] {m.title} (Difficulty: {m.difficulty_rank}/3)"
            )
            print(f"             Concepts:      {m.target_concepts}")
            print(f"             Task:          {m.task_description}")
            print(f"             Reference SQL: {m.reference_sql}")
            print(f"             Rubric:        {m.evaluation_rubric}")

        # -------------------------------------------------------------------
        # Step 5: Simulate Instructor Approval and Customization
        # -------------------------------------------------------------------
        print("\n[Step 5] Simulating Instructor Review & Approval:")
        # Save project initially in repository
        proj_repo.save_project(project)

        # Instructor updates approval status with pedagogical notes
        reviewer = "instructor_alawini"
        instructor_edits = (
            "Approved for clinical track. Excellent progression from patient-encounter joins to "
            "unassigned bed audits (LEFT OUTER JOIN + IS NULL) and department census aggregation."
        )
        project.instructor_approval_status = "APPROVED"
        project.generation_provenance["approved_by"] = reviewer
        project.generation_provenance["approval_notes"] = instructor_edits
        project.generation_provenance["approved_at"] = "2026-10-15T15:00:00Z"

        proj_repo.save_project(project)
        retrieved = proj_repo.get_project(project.project_id)
        assert retrieved is not None
        assert retrieved.instructor_approval_status == "APPROVED"

        print(f"         Status Updated:   {retrieved.instructor_approval_status}")
        print(f"         Approved By:      {retrieved.generation_provenance.get('approved_by')}")
        print(
            f'         Instructor Notes: "{retrieved.generation_provenance.get("approval_notes")}"'
        )

        print("\n" + "=" * 72)
        print("DEMO C VERIFICATION: SUCCESS (All 5 stages verified)")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(run_demo_c())
