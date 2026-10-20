"""Cryptographic role-based authorization security and negative test suite.

Verifies strict server-side role separation:
1. Synthetic students are strictly blocked (403 Forbidden) from reviewing, approving,
   or modifying EM Evidence decisions.
2. Synthetic students are strictly blocked (403 Forbidden) from reviewing or approving Dynamic Projects.
3. Reference SQL solutions (grading ground truth) are completely withheld from learner views.
4. Unapproved projects display clear pending approval notices.
5. Technical concept mastery remains strictly independent and isolated from EM evidence reviews.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard import DashboardServer, get_em_repo, get_project_repo
from siip.em_models import EMDimension, EMReviewStatus
from siip.identity import (
    create_signed_session_token,
    generate_csrf_token,
    is_instructor_principal,
    is_student_principal,
    verify_signed_session_token_role,
)
from siip.project_generator import generate_personalized_project
from siip.store import SubmissionRepository


class TestRoleAuthorizationSecurity(unittest.TestCase):
    def test_student_generation_response_and_approval_gate(self):
        status, data, _ = self._request(
            "POST",
            "/api/projects/generate",
            body=json.dumps({"student_id": "S001", "interest": "healthcare"}),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 201)
        payload = json.loads(data)
        self.assertNotIn("reference_sql", json.dumps(payload))
        self.assertEqual(payload["milestones"], [])
        project = self.proj_repo.get_project(payload["project_id"])
        project.instructor_approval_status = "APPROVED"
        self.proj_repo.save_project(project)
        status, data, _ = self._request(
            "GET",
            f"/api/projects?id={project.project_id}",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        approved = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(len(approved["milestones"]), 3)
        self.assertNotIn("reference_sql", json.dumps(approved))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_auth.sqlite3"
        self.em_db = Path(self.tmp.name) / "test_em.sqlite3"
        self.proj_db = Path(self.tmp.name) / "test_proj.sqlite3"

        os.environ["SIIP_DB_PATH"] = str(self.db_path)
        os.environ["SIIP_EM_DB_PATH"] = str(self.em_db)
        os.environ["SIIP_PROJECT_DB_PATH"] = str(self.proj_db)
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.sub_repo = SubmissionRepository(self.db_path)
        self.em_repo = get_em_repo()
        self.proj_repo = get_project_repo()

        # Seed attempt in sub_repo database so attempt existence validation passes
        with closing(self.sub_repo.connect()) as db:
            db.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "att-auth-01",
                    "S001",
                    "sql_join_04",
                    "2026-10-15T10:00:00Z",
                    "synthetic_fixture",
                    "sql-sandbox",
                    json.dumps(
                        {
                            "attempt_id": "att-auth-01",
                            "student_id": "S001",
                            "question_id": "sql_join_04",
                            "submitted_sql": "SELECT 1;",
                            "timestamp": "2026-10-15T10:00:00Z",
                            "concepts": ["LEFT_OUTER_JOIN"],
                            "grading": {"status": "correct", "score": 1, "observation": "Correct"},
                            "diagnosis": {"observed_error": "none"},
                        }
                    ),
                ),
            )
            db.commit()

        # Seed initial EM reflection & evidence record
        self.resp = self.em_repo.record_response(
            student_id="S001",
            question_id="sql_join_04",
            prompt_id="em-prompt-v1",
            attempt_id="att-auth-01",
            response_text="Omitting departments causes misallocated budgets.",
        )
        self.evidence = self.em_repo.create_evidence_record(
            student_id="S001",
            question_id="sql_join_04",
            dimension=EMDimension.CREATING_VALUE,
            relevant_concepts=["LEFT_OUTER_JOIN"],
            evidence_excerpt="Omitting departments causes misallocated budgets.",
            classification_method="student_reflection_provisional",
            response_id=self.resp.response_id,
            attempt_id="att-auth-01",
        )

        # Seed initial Dynamic Project
        self.project = generate_personalized_project(
            student_id="S001",
            interest="healthcare",
            profile=self.sub_repo.profile("S001"),
        )
        self.proj_repo.save_project(self.project)

        # Seed project for S002 to test cross-student isolation
        self.project_s002 = generate_personalized_project(
            student_id="S002",
            interest="transit",
            profile=self.sub_repo.profile("S002"),
        )
        self.proj_repo.save_project(self.project_s002)

        # Generate tokens
        self.student_token = create_signed_session_token("S001", role="student")
        self.student_csrf = generate_csrf_token(self.student_token)
        self.s002_token = create_signed_session_token("S002", role="student")
        self.s002_csrf = generate_csrf_token(self.s002_token)
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
        conn.close()
        return status, data, resp.headers

    # ---------------------------------------------------------------------------
    # Token Role Verification Unit Tests
    # ---------------------------------------------------------------------------
    def test_identity_principal_classifications(self):
        self.assertTrue(is_student_principal("S001"))
        self.assertTrue(is_student_principal("S002"))
        self.assertFalse(is_student_principal("instructor_alawini"))
        self.assertFalse(is_student_principal(None))

        self.assertTrue(is_instructor_principal("instructor_alawini"))
        self.assertTrue(is_instructor_principal("instructor-admin"))
        self.assertFalse(is_instructor_principal("S001"))
        self.assertFalse(is_instructor_principal(None))

    def test_session_token_role_verification(self):
        p_st, r_st = verify_signed_session_token_role(self.student_token)
        self.assertEqual(p_st, "S001")
        self.assertEqual(r_st, "student")

        p_inst, r_inst = verify_signed_session_token_role(self.instructor_token)
        self.assertEqual(p_inst, "instructor_alawini")
        self.assertEqual(r_inst, "instructor")

    # ---------------------------------------------------------------------------
    # EM Review Authorization Tests (Negative & Positive)
    # ---------------------------------------------------------------------------
    def test_student_bearer_token_blocked_from_em_review_403(self):
        """Mandatory negative test: Student bearer token cannot review or edit EM evidence."""
        payload = json.dumps(
            {
                "evidence_id": self.evidence.evidence_id,
                "review_status": "ACCEPTED",
                "instructor_notes": "Self-approved by student attempt.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)
        res = json.loads(data.decode("utf-8"))
        self.assertIn("error", res)
        self.assertIn("Forbidden", res["error"])

        # Verify state did NOT mutate
        ev = self.em_repo.get_evidence(self.evidence.evidence_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.review_status, EMReviewStatus.PROPOSED)

    def test_unauthenticated_endpoints_return_401(self):
        """Mandatory negative tests: Endpoints fail closed with 401 when no credentials provided."""
        # 1. POST /api/em/review without token
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=json.dumps(
                {"evidence_id": self.evidence.evidence_id, "review_status": "ACCEPTED"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 401)

        # 2. POST /api/projects/review without token
        status, data, _ = self._request(
            "POST",
            "/api/projects/review",
            body=json.dumps({"project_id": self.project.project_id, "status": "APPROVED"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 401)

        # 3. GET /projects without token
        status, _, _ = self._request("GET", f"/projects?id={self.project.project_id}")
        self.assertEqual(status, 401)

        # 4. GET /api/projects without token
        status, _, _ = self._request("GET", f"/api/projects?id={self.project.project_id}")
        self.assertEqual(status, 401)

        # 5. GET /em-review without token
        status, _, _ = self._request("GET", "/em-review")
        self.assertEqual(status, 401)

        # 6. GET /students?id=S001 without token
        status, _, _ = self._request("GET", "/students?id=S001")
        self.assertEqual(status, 401)

        # 7. GET /api/cohort-analytics without token
        status, _, _ = self._request("GET", "/api/cohort-analytics")
        self.assertEqual(status, 401)

        # 8. GET /api/recommendation without token
        status, _, _ = self._request("GET", "/api/recommendation?student_id=S001")
        self.assertEqual(status, 401)

        # 9. POST /api/em/reflection without token or ticket
        status, _, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=json.dumps(
                {
                    "student_id": "S001",
                    "question_id": "sql_join_04",
                    "prompt_id": "em-prompt-v1",
                    "attempt_id": "att-auth-01",
                    "reflection_text": "Sample text",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 401)

    def test_invalid_and_expired_credentials_return_401(self):
        """Mandatory negative test: Invalid or expired credentials fail closed with 401."""
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=json.dumps(
                {"evidence_id": self.evidence.evidence_id, "review_status": "ACCEPTED"}
            ),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid.synthetic.token",
            },
        )
        self.assertEqual(status, 401)

        status, data, _ = self._request(
            "GET",
            f"/projects?id={self.project.project_id}",
            headers={"Authorization": "Bearer expired_token"},
        )
        self.assertEqual(status, 401)

    def test_student_reviewer_id_blocked_from_em_review_403(self):
        """Mandatory negative test: Authenticated student sending reviewer_id is rejected with 403."""
        payload = json.dumps(
            {
                "evidence_id": self.evidence.evidence_id,
                "review_status": "ACCEPTED",
                "reviewer_id": "S001",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)
        res = json.loads(data.decode("utf-8"))
        self.assertIn("Forbidden", res["error"])

        # Verify state did NOT mutate
        ev = self.em_repo.get_evidence(self.evidence.evidence_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.review_status, EMReviewStatus.PROPOSED)

    def test_client_supplied_reviewer_id_never_establishes_authority(self):
        """Client-supplied instructor reviewer_id cannot elevate student token to instructor privileges."""
        payload = json.dumps(
            {
                "evidence_id": self.evidence.evidence_id,
                "review_status": "ACCEPTED",
                "reviewer_id": "instructor_alawini",  # Forged client claim
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)

    def test_instructor_token_successfully_reviews_em_evidence(self):
        """Authorized instructor token successfully updates EM evidence status."""
        payload = json.dumps(
            {
                "evidence_id": self.evidence.evidence_id,
                "review_status": "ACCEPTED",
                "instructor_notes": "Pedagogically verified connection to executive decision risk.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/em/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 200)
        res = json.loads(data.decode("utf-8"))
        self.assertEqual(res["review_status"], "ACCEPTED")
        self.assertEqual(res["reviewer_id"], "instructor_alawini")

        # Verify persisted state
        ev = self.em_repo.get_evidence(self.evidence.evidence_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.review_status, EMReviewStatus.ACCEPTED)
        self.assertEqual(ev.reviewer_id, "instructor_alawini")

    # ---------------------------------------------------------------------------
    # Dynamic Project Review Authorization Tests (Negative & Positive)
    # ---------------------------------------------------------------------------
    def test_student_bearer_token_blocked_from_project_review_403(self):
        """Mandatory negative test: Student bearer token cannot approve or review dynamic projects."""
        payload = json.dumps(
            {
                "project_id": self.project.project_id,
                "status": "APPROVED",
                "notes": "Student self-approval attempt.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)
        res = json.loads(data.decode("utf-8"))
        self.assertIn("Forbidden", res["error"])

        # Verify project remains PROVISIONAL
        p = self.proj_repo.get_project(self.project.project_id)
        self.assertIsNotNone(p)
        self.assertEqual(p.instructor_approval_status, "PROVISIONAL")

    def test_student_reviewer_id_blocked_from_project_review_403(self):
        """Mandatory negative test: Student reviewer_id rejected with 403."""
        payload = json.dumps(
            {
                "project_id": self.project.project_id,
                "status": "APPROVED",
                "reviewer_id": "S002",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)

    def test_instructor_token_successfully_approves_project(self):
        """Authorized instructor token successfully approves dynamic project."""
        payload = json.dumps(
            {
                "project_id": self.project.project_id,
                "status": "APPROVED",
                "notes": "Approved for clinical placement cohort study.",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 200)
        res = json.loads(data.decode("utf-8"))
        self.assertEqual(res["instructor_approval_status"], "APPROVED")

        # Verify persisted state
        p = self.proj_repo.get_project(self.project.project_id)
        self.assertIsNotNone(p)
        self.assertEqual(p.instructor_approval_status, "APPROVED")
        self.assertEqual(p.instructor_notes, "Approved for clinical placement cohort study.")

    # ---------------------------------------------------------------------------
    # Answer Key Concealment & Role Views
    # ---------------------------------------------------------------------------
    def test_learner_view_conceals_reference_sql_html(self):
        """Learner view must not leak reference SQL and must show pending notice."""
        status, data, _ = self._request(
            "GET",
            f"/projects?id={self.project.project_id}",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        html_text = data.decode("utf-8")

        # Must NOT contain Reference SQL Solution
        self.assertNotIn("Reference SQL Solution", html_text)
        self.assertNotIn("SELECT physicians.name", html_text)

        # Must display Pending Approval notice for unapproved project
        self.assertIn("Pending Instructor Approval", html_text)

        # Must NOT contain instructor review form controls
        self.assertNotIn('action="/api/projects/review"', html_text)

    def test_instructor_view_displays_reference_sql_and_controls_html(self):
        """Instructor view displays reference SQL and review action buttons."""
        status, data, _ = self._request(
            "GET",
            f"/projects?id={self.project.project_id}",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        html_text = data.decode("utf-8")

        self.assertIn("Reference SQL Solution", html_text)
        self.assertIn("SELECT physicians.name", html_text)
        self.assertIn('action="/api/projects/review"', html_text)

    def test_learner_api_endpoint_strips_reference_sql_json(self):
        """GET /api/projects?id=... for student strips reference_sql from all milestones."""
        status, data, _ = self._request(
            "GET",
            f"/api/projects?id={self.project.project_id}",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(data.decode("utf-8"))

        for m in payload["milestones"]:
            self.assertNotIn("reference_sql", m)
        self.assertIn("learner_notice", payload)
        self.assertIn("Pending Instructor Approval", payload["learner_notice"])

    # ---------------------------------------------------------------------------
    # Cross-Student Isolation & Role Separation
    # ---------------------------------------------------------------------------
    def test_cross_student_access_rejected_403(self):
        """Learners cannot access other learners' private records or projects."""
        # 1. Student S001 cannot view S002's profile
        status, _, _ = self._request(
            "GET",
            "/students?id=S002",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 403)

        # 2. Student S001 cannot view S002's project HTML
        status, _, _ = self._request(
            "GET",
            f"/projects?id={self.project_s002.project_id}",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 403)

        # 3. Student S001 cannot view S002's project JSON
        status, _, _ = self._request(
            "GET",
            f"/api/projects?id={self.project_s002.project_id}",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 403)

        # 4. Student S001 cannot view S002's recommendations
        status, _, _ = self._request(
            "GET",
            "/api/recommendation?student_id=S002",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 403)

        # 5. Student cannot access cohort analytics
        status, _, _ = self._request(
            "GET",
            "/api/cohort-analytics",
            headers={"Authorization": f"Bearer {self.student_token}"},
        )
        self.assertEqual(status, 403)

    # ---------------------------------------------------------------------------
    # EM Reflection Security, Validation & Idempotency
    # ---------------------------------------------------------------------------
    def test_em_reflection_security_and_validation(self):
        """Verify attempt ownership, existence, prompt match, and duplicate idempotency."""
        # 1. Cross-student reflection rejected: S001 token submitting for S002
        status, _, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=json.dumps(
                {
                    "student_id": "S002",
                    "question_id": "sql_join_04",
                    "prompt_id": "em-prompt-v1",
                    "attempt_id": "att-auth-01",
                    "reflection_text": "Impostor reflection",
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 403)

        # 2. Non-existent attempt rejected: 404
        status, _, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=json.dumps(
                {
                    "student_id": "S001",
                    "question_id": "sql_join_04",
                    "prompt_id": "em-prompt-v1",
                    "attempt_id": "nonexistent-att-999",
                    "reflection_text": "Valid text",
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 404)

        # 3. Prompt mismatch rejected: 400
        status, _, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=json.dumps(
                {
                    "student_id": "S001",
                    "question_id": "sql_join_04",
                    "prompt_id": "em-prompt-c1",  # Mismatched prompt for join_04
                    "attempt_id": "att-auth-01",
                    "reflection_text": "Valid text",
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 400)

        # 4. Duplicate request follows idempotency policy: 200 with idempotent: True
        status, data, _ = self._request(
            "POST",
            "/api/em/reflection",
            body=json.dumps(
                {
                    "student_id": "S001",
                    "question_id": "sql_join_04",
                    "prompt_id": "em-prompt-v1",
                    "attempt_id": "att-auth-01",
                    "reflection_text": "Duplicate submission attempt",
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.student_token}",
            },
        )
        self.assertEqual(status, 200)
        res = json.loads(data.decode("utf-8"))
        self.assertTrue(res.get("idempotent"))
        self.assertEqual(res["response_id"], self.resp.response_id)

    # ---------------------------------------------------------------------------
    # CSRF Protection on Synthetic Browser Forms
    # ---------------------------------------------------------------------------
    def test_csrf_protection_on_browser_forms(self):
        """Forms must reject submissions without a valid CSRF token."""
        from urllib.parse import urlencode

        # 1. Missing CSRF on project review form POST -> 403
        payload = urlencode({"project_id": self.project.project_id, "status": "APPROVED"})
        status, _, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 403)

        # 2. Invalid CSRF on project review form POST -> 403
        payload_invalid = urlencode(
            {"project_id": self.project.project_id, "status": "APPROVED", "csrf_token": "bad-csrf"}
        )
        status, _, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload_invalid,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 403)

        # 3. Valid CSRF on project review form POST -> 303 Redirect
        payload_valid = urlencode(
            {
                "project_id": self.project.project_id,
                "status": "APPROVED",
                "csrf_token": self.instructor_csrf,
            }
        )
        status, _, _ = self._request(
            "POST",
            "/api/projects/review",
            body=payload_valid,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.instructor_token}",
            },
        )
        self.assertEqual(status, 303)

    # ---------------------------------------------------------------------------
    # Independence of Technical Concept Mastery from EM Evidence
    # ---------------------------------------------------------------------------
    def test_em_review_does_not_mutate_technical_concept_mastery(self):
        """Technical concept mastery is computed strictly from SQL attempts, never EM reviews."""
        from siip.grader import QUESTIONS

        # 1. Record an incorrect SQL attempt for S001 on sql_join_02
        self.sub_repo.process(
            {
                "attempt_id": "att-auth-test-01",
                "student_id": "S001",
                "question_id": "sql_join_02",
                "submitted_sql": QUESTIONS["sql_join_01"]["reference_sql"],
                "timestamp": "2026-10-15T12:00:00Z",
            }
        )

        prof_before = self.sub_repo.profile("S001")
        concept_mastery_before = prof_before["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]

        # 2. Approve EM reflection for S001 with glowing instructor notes
        self.em_repo.review_evidence(
            self.evidence.evidence_id,
            EMReviewStatus.ACCEPTED,
            notes="Outstanding entrepreneurial curiosity and systemic perspective.",
            reviewer_id="instructor_alawini",
        )

        # 3. Verify concept mastery remains completely invariant
        prof_after = self.sub_repo.profile("S001")
        concept_mastery_after = prof_after["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]

        self.assertEqual(concept_mastery_before, concept_mastery_after)
        self.assertEqual(prof_before["attempt_count"], prof_after["attempt_count"])

    # ---------------------------------------------------------------------------
    # Synthetic Auth Isolation Outside Development Mode
    # ---------------------------------------------------------------------------
    def test_synthetic_login_blocked_outside_dev_mode(self):
        """Synthetic login and session issuance fail closed with 403 outside dev mode."""
        old_auth = os.environ.get("SIIP_ALLOW_SYNTHETIC_AUTH")
        old_env = os.environ.get("SIIP_ENV")
        try:
            os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "0"
            os.environ["SIIP_ENV"] = "production"

            # 1. GET /login returns 403
            status, data, _ = self._request("GET", "/login")
            self.assertEqual(status, 403)
            self.assertIn(b"disabled outside isolated development mode", data)

            # 2. POST /login returns 403
            status, data, _ = self._request(
                "POST",
                "/login",
                body="principal=instructor_alawini&redirect=/",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            self.assertEqual(status, 403)
            self.assertIn(b"disabled outside isolated development mode", data)

            # 3. POST /api/auth/synthetic-session returns 403
            status, data, _ = self._request(
                "POST",
                "/api/auth/synthetic-session",
                body=json.dumps({"student_id": "S001"}),
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(status, 403)
            res = json.loads(data.decode("utf-8"))
            self.assertIn("disabled outside isolated development mode", res["error"])
        finally:
            if old_auth is not None:
                os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = old_auth
            else:
                os.environ.pop("SIIP_ALLOW_SYNTHETIC_AUTH", None)
            if old_env is not None:
                os.environ["SIIP_ENV"] = old_env
            else:
                os.environ.pop("SIIP_ENV", None)


if __name__ == "__main__":
    unittest.main()
