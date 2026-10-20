"""Deterministic Unit Tests for Phase 5.1 Entrepreneurial Mindset (EM) Vertical Slice.

Tests EM graph schema, reflection prompts, student responses, evidence persistence,
instructor review, and separation of technical mastery from mindset observations.
"""

import http.client
import json
import os
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
from siip.em_models import (
    EMDimension,
    EMResponseStatus,
    EMReviewStatus,
)
from siip.em_repository import DEFAULT_PROMPTS, EMRepository
from siip.identity import (
    create_signed_session_token,
    create_signed_ticket,
    generate_csrf_token,
)
from siip.jobs import FeedbackJobRepository
from siip.store import SubmissionRepository


class TestEMModelsAndGraphSchema(unittest.TestCase):
    """Verifies KEEN 3C dimensions, review states, and model invariants."""

    def test_dimensions_and_review_states(self):
        self.assertEqual(EMDimension.CURIOSITY.value, "C")
        self.assertEqual(EMDimension.CONNECTIONS.value, "X")
        self.assertEqual(EMDimension.CREATING_VALUE.value, "V")

        self.assertEqual(EMReviewStatus.PROPOSED.value, "PROPOSED")
        self.assertEqual(EMReviewStatus.ACCEPTED.value, "ACCEPTED")
        self.assertEqual(EMReviewStatus.REJECTED.value, "REJECTED")
        self.assertEqual(EMReviewStatus.NEEDS_REVISION.value, "NEEDS_REVISION")

    def test_default_prompts_cover_three_dimensions(self):
        dims = {p.dimension for p in DEFAULT_PROMPTS}
        self.assertEqual(
            dims, {EMDimension.CURIOSITY, EMDimension.CONNECTIONS, EMDimension.CREATING_VALUE}
        )

        # Check prompt text contains non-revealing guidance
        for p in DEFAULT_PROMPTS:
            self.assertNotIn("SELECT", p.prompt_text)
            self.assertTrue(len(p.prompt_text) > 30)
            self.assertTrue(len(p.why_it_matters) > 30)


class TestEMRepository(unittest.TestCase):
    """Verifies durable persistence, review lifecycles, and student EM profiles."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="siip-em-test-")
        self.db_path = Path(self.temp_dir.name) / "em_test.sqlite3"
        self.repo = EMRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seeded_prompts_available(self):
        p_c = self.repo.get_prompt_for_question("sql_join_03")
        self.assertIsNotNone(p_c)
        self.assertEqual(p_c.dimension, EMDimension.CURIOSITY)

        p_x = self.repo.get_prompt_for_question("sql_join_02")
        self.assertIsNotNone(p_x)
        self.assertEqual(p_x.dimension, EMDimension.CONNECTIONS)

        p_v = self.repo.get_prompt_for_question("sql_join_04")
        self.assertIsNotNone(p_v)
        self.assertEqual(p_v.dimension, EMDimension.CREATING_VALUE)

        # Baseline question sql_join_01 has no EM prompt attached (deterministic non-universal rule)
        p_none = self.repo.get_prompt_for_question("sql_join_01")
        self.assertIsNone(p_none)

    def test_reflection_submission_and_evidence_creation(self):
        # 1. Student submits reflection
        resp = self.repo.record_response(
            student_id="S001",
            question_id="sql_join_03",
            prompt_id="em-prompt-c1",
            attempt_id="att-test-01",
            response_text="Missing department IDs might indicate contractors or pending HR onboarding.",
            status=EMResponseStatus.SUBMITTED,
        )
        self.assertTrue(resp.response_id.startswith("em-resp-"))
        self.assertEqual(resp.status, EMResponseStatus.SUBMITTED)

        # 2. System creates evidence record in PROPOSED status
        ev = self.repo.create_evidence_record(
            student_id="S001",
            question_id="sql_join_03",
            dimension=EMDimension.CURIOSITY,
            relevant_concepts=["LEFT_OUTER_JOIN", "NULL_SEMANTICS"],
            evidence_excerpt=resp.response_text,
            classification_method="rule_based_deterministic",
            confidence=0.88,
            response_id=resp.response_id,
            attempt_id=resp.attempt_id,
        )
        self.assertTrue(ev.evidence_id.startswith("em-ev-"))
        self.assertEqual(ev.review_status, EMReviewStatus.PROPOSED)

        # Verify summary before review reports insufficient evidence for validated claims
        summary_before = self.repo.student_em_summary("S001")
        self.assertEqual(summary_before["total_observations"], 1)
        self.assertEqual(summary_before["counts_by_status"]["PROPOSED"], 1)
        self.assertEqual(summary_before["counts_by_status"]["ACCEPTED"], 0)
        self.assertTrue(summary_before["has_insufficient_evidence"])

        # 3. Instructor reviews and accepts evidence
        reviewed = self.repo.review_evidence(
            ev.evidence_id,
            EMReviewStatus.ACCEPTED,
            notes="Thoughtful hypothesis regarding HR onboarding latency.",
            reviewer_id="instructor-alawini",
        )
        self.assertEqual(reviewed.review_status, EMReviewStatus.ACCEPTED)
        self.assertEqual(reviewed.reviewer_id, "instructor-alawini")
        self.assertIsNotNone(reviewed.reviewed_at)

        # Verify summary after review
        summary_after = self.repo.student_em_summary("S001")
        self.assertEqual(summary_after["counts_by_status"]["ACCEPTED"], 1)
        self.assertEqual(summary_after["accepted_by_dimension"]["C"], 1)
        self.assertFalse(summary_after["has_insufficient_evidence"])

    def test_persistence_across_service_restart(self):
        # Write record
        resp = self.repo.record_response(
            student_id="S002",
            question_id="sql_join_04",
            prompt_id="em-prompt-v1",
            attempt_id="att-test-02",
            response_text="Omitting 0-staff departments causes executives to defund nascent initiatives.",
            status=EMResponseStatus.SUBMITTED,
        )
        ev = self.repo.create_evidence_record(
            student_id="S002",
            question_id="sql_join_04",
            dimension=EMDimension.CREATING_VALUE,
            relevant_concepts=["COUNT_AGGREGATION", "LEFT_OUTER_JOIN"],
            evidence_excerpt=resp.response_text,
            response_id=resp.response_id,
            attempt_id=resp.attempt_id,
        )
        self.repo.review_evidence(
            ev.evidence_id, EMReviewStatus.ACCEPTED, reviewer_id="prof-alawini"
        )

        # Simulate service restart by creating fresh EMRepository pointing to same SQLite database
        restarted_repo = EMRepository(self.db_path)
        fetched = restarted_repo.get_evidence(ev.evidence_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.review_status, EMReviewStatus.ACCEPTED)
        self.assertEqual(fetched.reviewer_id, "prof-alawini")
        self.assertIn("Omitting 0-staff", fetched.evidence_excerpt)

    def test_skipped_reflection(self):
        resp = self.repo.record_response(
            student_id="S003",
            question_id="sql_join_02",
            prompt_id="em-prompt-x1",
            attempt_id="att-test-03",
            response_text="",
            status=EMResponseStatus.SKIPPED,
        )
        self.assertEqual(resp.status, EMResponseStatus.SKIPPED)
        prior = self.repo.get_response_for_student_question("S003", "sql_join_02")
        self.assertIsNotNone(prior)
        self.assertEqual(prior.status, EMResponseStatus.SKIPPED)


class TestEMDashboardIntegration(unittest.TestCase):
    """End-to-end integration tests for Phase 5.1 EM vertical slice HTTP workflow.

    Workflow verified:
    Student submission -> Grading & feedback -> EM prompt display ->
    Reflection submission -> Provisional evidence creation -> Instructor review ->
    Accepted evidence reflected in student profile.
    """

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
        self.em_repo = EMRepository(self.sub_db)

        # Enqueue a completed job for S001 on sql_join_02 (which has EM Connections prompt)
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }
        self.job = self.jobs_repo.enqueue(
            attempt_id="att-em-s001-1",
            student_id="S001",
            question_id="sql_join_02",
            submitted_sql="SELECT Employees.name, Departments.name FROM Employees INNER JOIN Departments ON Employees.department_id = Departments.id;",
            grading=grading,
            mode="kg",
        )
        self.jobs_repo.complete(
            job_id=self.job.job_id,
            result={
                "feedback_text": "Remember that LEFT OUTER JOIN preserves rows from the left table even when no match exists.",
                "candidate_concepts": ["LEFT_OUTER_JOIN"],
                "evidence_references": ["Lecture 4: Join semantics"],
                "personalized": False,
                "history_provenance": "none",
            },
            latency_ms=12.5,
            model_identifier="test-model",
            prompt_version="v1",
            graph_version="g1",
            lease_token=self.jobs_repo.claim("worker-test").lease_token,
        )

        self.student_token = create_signed_session_token("S001", role="student")
        self.s002_token = create_signed_session_token("S002", role="student")
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

    def test_complete_em_lifecycle(self):
        # 1. Access feedback page with valid signed ticket
        ticket = create_signed_ticket("S001", self.job.job_id)
        status, data, _ = self._request(
            "GET", f"/feedback?job_id={self.job.job_id}&ticket={ticket}"
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Entrepreneurial Mindset (EM) Reflection", html_str)
        self.assertIn("Connections (X)", html_str)
        self.assertIn('action="/api/em/reflection"', html_str)

        # 2. Student submits reflection via form POST
        form_payload = urlencode(
            {
                "student_id": "S001",
                "question_id": "sql_join_02",
                "prompt_id": "em-prompt-x1",
                "attempt_id": "att-em-s001-1",
                "reflection_text": "Using a LEFT OUTER JOIN protects payroll and building access workflows so unassigned employees do not lose system access.",
                "job_id": self.job.job_id,
                "ticket": ticket,
            }
        )
        status, _, headers = self._request(
            "POST",
            "/api/em/reflection",
            body=form_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 303)
        self.assertIn(
            f"/feedback?job_id={self.job.job_id}&ticket={ticket}", headers.get("Location", "")
        )

        # 3. Verify feedback page now displays the submitted reflection with PROPOSED status
        status, data, _ = self._request(
            "GET", f"/feedback?job_id={self.job.job_id}&ticket={ticket}"
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Status: PROPOSED", html_str)
        self.assertIn("protects payroll and building access", html_str)

        # 4. Instructor views /em-review
        status, data, _ = self._request(
            "GET",
            "/em-review",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Instructor Entrepreneurial Mindset (EM) Evidence Review", html_str)
        self.assertIn("S001", html_str)
        self.assertIn("PROPOSED", html_str)

        # Get evidence ID from repo
        ev_records = self.em_repo.get_evidence_for_student("S001")
        self.assertEqual(len(ev_records), 1)
        ev = ev_records[0]
        self.assertEqual(ev.review_status, EMReviewStatus.PROPOSED)

        # 5. Instructor accepts the evidence
        review_payload = urlencode(
            {
                "evidence_id": ev.evidence_id,
                "review_status": "ACCEPTED",
                "instructor_notes": "Identifies cross-functional risk to payroll systems accurately.",
                "csrf_token": self.instructor_csrf,
            }
        )
        status, _, headers = self._request(
            "POST",
            "/api/em/review",
            body=review_payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/em-review")

        # 6. Check student profile at /students?id=S001 (authenticated as S001)
        status, data, _ = self._request(
            "GET",
            "/students?id=S001",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("OBSERVED_EVIDENCE_RECORDED", html_str)
        self.assertIn("Connections (X) accepted", html_str)
        self.assertIn("instructor_alawini", html_str)
        self.assertIn("Methodological Boundary:", html_str)

        # 7. Check JSON API /api/em/summary
        status, data, _ = self._request(
            "GET",
            "/api/em/summary?student_id=S001",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        summary = json.loads(data.decode("utf-8"))
        self.assertEqual(summary["accepted_by_dimension"]["X"], 1)
        self.assertFalse(summary["has_insufficient_evidence"])
        self.assertIn("disclaimer", summary)

    def test_json_reflection_and_review_api(self):
        # Seed attempt for student S002
        self.sub_repo.process(
            {
                "attempt_id": "att-json-01",
                "student_id": "S002",
                "question_id": "sql_join_03",
                "submitted_sql": "SELECT 1;",
                "timestamp": "2026-10-15T12:00:00Z",
            }
        )
        # Student submits via JSON API
        body = json.dumps(
            {
                "student_id": "S002",
                "question_id": "sql_join_03",
                "prompt_id": "em-prompt-c1",
                "attempt_id": "att-json-01",
                "reflection_text": "Investigating whether NULLs stem from employee transfers vs database migration errors.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.s002_token}",
            },
        )
        self.assertEqual(status, 201)
        res = json.loads(data.decode("utf-8"))
        self.assertEqual(res["status"], "recorded")
        self.assertEqual(res["dimension"], "C")
        self.assertEqual(res["review_status"], "PROPOSED")
        ev_id = res["evidence_id"]

        # Profile before review shows INSUFFICIENT_EVIDENCE
        status, data, _ = self._request(
            "GET",
            "/students?id=S002",
            headers={"Authorization": f"Bearer {self.s002_token}"},
        )
        self.assertEqual(status, 200)
        self.assertIn("INSUFFICIENT_EVIDENCE", data.decode("utf-8"))

        # Instructor reviews via JSON API
        review_body = json.dumps(
            {
                "evidence_id": ev_id,
                "review_status": "ACCEPTED",
                "instructor_notes": "Strong investigative inquiry.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=review_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 200)
        rev_res = json.loads(data.decode("utf-8"))
        self.assertEqual(rev_res["review_status"], "ACCEPTED")
        self.assertEqual(rev_res["reviewer_id"], "instructor_alawini")

        # Test filter view as instructor
        status, data, _ = self._request(
            "GET",
            "/em-review?status=ACCEPTED",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        self.assertIn("S002", data.decode("utf-8"))

        # Test invalid review status returns 400
        bad_review = json.dumps(
            {
                "evidence_id": ev_id,
                "review_status": "INVALID_STATUS",
            }
        )
        status, _, _ = self._request(
            "POST",
            "/api/em/review",
            body=bad_review,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
