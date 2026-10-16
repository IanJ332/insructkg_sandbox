"""Unit and Integration Tests for Phase 5.2: Adaptive Learning and Dynamic Projects.

Verifies:
1. Deterministic adaptive activity recommender across all prerequisite mastery levels.
2. 3-stage dynamic project generator, SQLite in-memory DDL execution, and reference query validation.
3. Task decomposition, InstructKG concept depth, and milestone difficulty rankings.
4. Project repository persistence and instructor approval lifecycles.
5. End-to-end HTTP integration with dashboard views and JSON APIs.
"""

from __future__ import annotations

import http.client
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from dashboard import DashboardServer
from siip.identity import create_signed_session_token, generate_csrf_token
from siip.jobs import FeedbackJobRepository
from siip.project_generator import (
    ProjectRepository,
    generate_personalized_project,
    verify_project_schema_and_queries,
)
from siip.project_models import ProjectMilestone, ProjectSpecification, StudentInterest
from siip.recommender import recommend_next_activity
from siip.store import SubmissionRepository


class TestAdaptiveRecommender(unittest.TestCase):
    """Tests deterministic rule-based next-activity recommendation policy."""

    def test_recommends_inner_join_when_inner_mastery_low(self):
        profile = {
            "concepts": {
                "INNER_JOIN": {"mastery_estimate": 0.40, "attempt_count": 2},
                "LEFT_OUTER_JOIN": {"mastery_estimate": 0.50, "attempt_count": 0},
            }
        }
        rec = recommend_next_activity("S001", profile)
        self.assertEqual(rec["recommended_question_id"], "sql_join_01")
        self.assertEqual(rec["rule_id"], "RULE_PREREQ_INNER_JOIN")
        self.assertIn("INNER_JOIN mastery is 0.40", rec["rationale"])

    def test_recommends_left_join_when_inner_mastered_but_outer_low(self):
        profile = {
            "concepts": {
                "INNER_JOIN": {"mastery_estimate": 0.80, "attempt_count": 3},
                "LEFT_OUTER_JOIN": {"mastery_estimate": 0.45, "attempt_count": 1},
            }
        }
        rec = recommend_next_activity("S001", profile)
        self.assertEqual(rec["recommended_question_id"], "sql_join_02")
        self.assertEqual(rec["rule_id"], "RULE_PREREQ_LEFT_OUTER_JOIN")
        self.assertIn("INNER_JOIN is mastered (0.80)", rec["rationale"])

    def test_recommends_null_semantics_when_outer_mastered_but_nulls_low(self):
        profile = {
            "concepts": {
                "INNER_JOIN": {"mastery_estimate": 0.85, "attempt_count": 3},
                "LEFT_OUTER_JOIN": {"mastery_estimate": 0.75, "attempt_count": 2},
                "NULL_SEMANTICS": {"mastery_estimate": 0.35, "attempt_count": 2},
            }
        }
        rec = recommend_next_activity("S001", profile)
        self.assertEqual(rec["recommended_question_id"], "sql_join_03")
        self.assertEqual(rec["rule_id"], "RULE_PREREQ_NULL_SEMANTICS")
        self.assertIn("NULL_SEMANTICS mastery is 0.35", rec["rationale"])

    def test_recommends_aggregation_when_join_mechanics_mastered_but_aggregation_low(self):
        profile = {
            "concepts": {
                "INNER_JOIN": {"mastery_estimate": 0.85, "attempt_count": 3},
                "LEFT_OUTER_JOIN": {"mastery_estimate": 0.75, "attempt_count": 2},
                "NULL_SEMANTICS": {"mastery_estimate": 0.70, "attempt_count": 2},
                "COUNT_AGGREGATION": {"mastery_estimate": 0.30, "attempt_count": 1},
            }
        }
        rec = recommend_next_activity("S001", profile)
        self.assertEqual(rec["recommended_question_id"], "sql_join_04")
        self.assertEqual(rec["rule_id"], "RULE_PREREQ_COUNT_AGGREGATION")
        self.assertIn("COUNT_AGGREGATION", rec["rationale"])

    def test_recommends_synthesis_when_all_concepts_mastered(self):
        profile = {
            "concepts": {
                "INNER_JOIN": {"mastery_estimate": 0.90, "attempt_count": 4},
                "LEFT_OUTER_JOIN": {"mastery_estimate": 0.85, "attempt_count": 3},
                "NULL_SEMANTICS": {"mastery_estimate": 0.80, "attempt_count": 3},
                "COUNT_AGGREGATION": {"mastery_estimate": 0.75, "attempt_count": 2},
            }
        }
        rec = recommend_next_activity("S001", profile)
        self.assertEqual(rec["rule_id"], "RULE_MASTERY_SYNTHESIS")
        self.assertIn(
            "All core relational concepts exceed the 0.60 mastery threshold", rec["rationale"]
        )


class TestProjectGeneratorAndVerification(unittest.TestCase):
    """Verifies schema DDL, query correctness, and milestone depth progression."""

    def test_all_domain_templates_execute_in_sqlite(self):
        for domain_name in [
            StudentInterest.HEALTHCARE.value,
            StudentInterest.PUBLIC_TRANSIT.value,
            StudentInterest.GAMING.value,
        ]:
            proj = generate_personalized_project("S001", interest=domain_name)
            self.assertTrue(proj.generation_provenance["verified_in_memory"])
            self.assertEqual(len(proj.milestones), 3)

            # Manually verify SQLite execution
            conn = sqlite3.connect(":memory:")
            conn.executescript(proj.schema_ddl)
            for m in proj.milestones:
                res = conn.execute(m.reference_sql).fetchall()
                self.assertIsInstance(res, list)
                self.assertGreater(
                    len(res), 0, f"Milestone query returned 0 rows in domain {domain_name}"
                )
            conn.close()

    def test_milestone_difficulty_ranking_and_depth(self):
        proj = generate_personalized_project("S001", interest=StudentInterest.HEALTHCARE.value)
        m1, m2, m3 = proj.milestones

        # Difficulty rank progression: 1 < 2 < 3
        self.assertEqual(m1.difficulty_rank, 1)
        self.assertEqual(m2.difficulty_rank, 2)
        self.assertEqual(m3.difficulty_rank, 3)

        # Concept depth progression: 1 <= 2 <= 3
        self.assertLessEqual(m1.concept_depth, m2.concept_depth)
        self.assertLessEqual(m2.concept_depth, m3.concept_depth)

    def test_verifier_rejects_invalid_queries(self):
        bad_milestone = ProjectMilestone(
            milestone_index=1,
            title="Bad Query",
            task_description="Query non-existent column",
            target_concepts=["INNER_JOIN"],
            difficulty_rank=1,
            concept_depth=1,
            reference_sql="SELECT non_existent_column FROM clinics;",
            evaluation_rubric="Fails",
        )
        bad_proj = ProjectSpecification(
            project_id="proj-bad",
            student_id="S001",
            domain_interest="healthcare",
            title="Bad Project",
            scenario_narrative="test",
            schema_ddl="CREATE TABLE clinics (clinic_id INT);",
            milestones=[bad_milestone],
            target_concepts=["INNER_JOIN"],
            generation_provenance={},
            created_at="2026-10-15T00:00:00Z",
        )
        self.assertFalse(verify_project_schema_and_queries(bad_proj))


class TestProjectRepository(unittest.TestCase):
    """Verifies durable SQLite storage and review status changes for projects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "proj_test.sqlite3"
        self.repo = ProjectRepository(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_retrieve_and_review(self):
        proj = generate_personalized_project("S002", interest=StudentInterest.PUBLIC_TRANSIT.value)
        self.assertEqual(proj.instructor_approval_status, "PROVISIONAL")

        # Save to DB
        self.repo.save_project(proj)

        # Retrieve and verify
        fetched = self.repo.get_project(proj.project_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.project_id, proj.project_id)
        self.assertEqual(fetched.domain_interest, StudentInterest.PUBLIC_TRANSIT.value)
        self.assertEqual(len(fetched.milestones), 3)

        # Instructor approves project
        fetched.instructor_approval_status = "APPROVED"
        fetched.instructor_notes = "Approved for autonomous project track."
        self.repo.save_project(fetched)

        # Re-fetch from restarted repository instance
        restarted_repo = ProjectRepository(self.db_path)
        approved = restarted_repo.get_project(proj.project_id)
        self.assertIsNotNone(approved)
        self.assertEqual(approved.instructor_approval_status, "APPROVED")
        self.assertEqual(approved.instructor_notes, "Approved for autonomous project track.")


class TestDashboardAdaptiveAndProjectIntegration(unittest.TestCase):
    """Integration test verifying dashboard UI and JSON APIs for adaptive recommendations and dynamic projects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sub_db = Path(self.tmp.name) / "sub.sqlite3"
        self.jobs_db = Path(self.tmp.name) / "jobs.sqlite3"
        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.sub_repo = SubmissionRepository(self.sub_db)
        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.proj_repo = ProjectRepository(self.sub_db)

        self.student_token = create_signed_session_token("S001", role="student")
        self.student_csrf = generate_csrf_token(self.student_token)
        self.instructor_token = create_signed_session_token("instructor_alawini", role="instructor")
        self.instructor_csrf = generate_csrf_token(self.instructor_token)

        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def _request(
        self, method: str, path: str, body: str | None = None, headers: dict | None = None
    ):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        hdrs = headers or {}
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        status = resp.status
        resp_headers = dict(resp.getheaders())
        conn.close()
        return status, data, resp_headers

    def test_student_profile_displays_recommendation_and_projects(self):
        status, data, _ = self._request(
            "GET",
            "/students?id=S001",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Adaptive Next-Activity Recommendation", html_str)
        self.assertIn("Personalized Dynamic Project", html_str)
        self.assertIn("Healthcare &amp; Clinical Operations", html_str)

    def test_adaptive_recommendation_api(self):
        status, data, _ = self._request(
            "GET",
            "/api/recommendation?student_id=S001",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        rec = json.loads(data.decode("utf-8"))
        self.assertEqual(rec["student_id"], "S001")
        self.assertIn("recommended_question_id", rec)
        self.assertIn("rule_id", rec)
        self.assertIn("mastery_snapshot", rec)

    def test_generate_and_review_project_lifecycle(self):
        # 1. Generate project via form POST (authenticated as student S001)
        gen_payload = urlencode(
            {
                "student_id": "S001",
                "interest": "healthcare",
                "csrf_token": self.student_csrf,
            }
        )
        status, _, headers = self._request(
            "POST",
            "/api/projects/generate",
            body=gen_payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 303)
        proj_url = headers.get("Location", "")
        self.assertIn("/projects?id=", proj_url)
        proj_id = proj_url.split("id=")[-1]

        # 2. View generated project page as instructor
        status, data, _ = self._request(
            "GET",
            f"/projects?id={proj_id}",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Clinical Operations and Patient Placement Intelligence", html_str)
        self.assertIn("CREATE TABLE clinics", html_str)
        self.assertIn("Milestone 1:", html_str)
        self.assertIn("Status: PROVISIONAL", html_str)

        # 3. Instructor approves project
        rev_payload = urlencode(
            {
                "project_id": proj_id,
                "status": "APPROVED",
                "notes": "Excellent clinical operational challenge.",
                "csrf_token": self.instructor_csrf,
            }
        )
        status, _, headers = self._request(
            "POST",
            "/api/projects/review",
            body=rev_payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 303)

        # 4. Re-fetch project page as instructor and verify APPROVED badge
        status, data, _ = self._request(
            "GET",
            f"/projects?id={proj_id}",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Status: APPROVED", html_str)

        # 5. Fetch project list via JSON API as instructor
        status, data, _ = self._request(
            "GET",
            f"/api/projects?id={proj_id}",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        proj_data = json.loads(data.decode("utf-8"))
        self.assertEqual(proj_data["project_id"], proj_id)
        self.assertEqual(proj_data["instructor_approval_status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
