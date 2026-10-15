"""Cryptographic authorization tests for SIIP learner feedback endpoints.
Verifies HMAC signed tickets, synthetic session tokens, zero identity leakage,
and response payload minimization.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard import DashboardServer
from siip.identity import (
    create_signed_ticket,
)
from siip.jobs import FeedbackJobRepository
from siip.store import SubmissionRepository


class TestLearnerAuthorization(unittest.TestCase):
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

        # Enqueue sample jobs for S001 and S002
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }
        self.job1 = self.jobs_repo.enqueue(
            attempt_id="att-s001-1",
            student_id="S001",
            question_id="sql_join_02",
            submitted_sql="SELECT name FROM Employees;",
            grading=grading,
            mode="kg",
        )
        self.jobs_repo.complete(
            job_id=self.job1.job_id,
            result={
                "feedback_text": "Check which rows should be preserved.",
                "candidate_concepts": ["LEFT_OUTER_JOIN"],
                "evidence_references": ["lec-01"],
                "personalized": False,
                "history_provenance": "none",
            },
            latency_ms=15.0,
            model_identifier="test-model",
            prompt_version="v1",
            graph_version="g1",
            lease_token=self.jobs_repo.claim("worker-test").lease_token,
        )

        self.job2 = self.jobs_repo.enqueue(
            attempt_id="att-s002-1",
            student_id="S002",
            question_id="sql_join_02",
            submitted_sql="SELECT name FROM Employees;",
            grading=grading,
            mode="kg",
        )

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

    def test_signed_ticket_success(self):
        # Generate valid signed ticket for S001 on job1
        ticket = create_signed_ticket("S001", self.job1.job_id)
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&ticket={ticket}"
        )
        self.assertEqual(status, 200)
        payload = json.loads(data.decode("utf-8"))
        self.assertEqual(payload["job_id"], self.job1.job_id)
        self.assertEqual(payload["status"], "completed")
        self.assertIn("feedback", payload)
        self.assertEqual(
            payload["feedback"]["feedback_text"], "Check which rows should be preserved."
        )

    def test_unsigned_or_raw_student_id_rejected_with_401(self):
        # Passing raw student_id query param without signature MUST be rejected
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&student_id=S001"
        )
        self.assertEqual(status, 401)
        resp = json.loads(data.decode("utf-8"))
        self.assertIn("error", resp)
        self.assertIn("Authentication required", resp["error"])

        # Passing unsigned header without signature MUST be rejected
        status, data, _ = self._request(
            "GET",
            f"/api/feedback?job_id={self.job1.job_id}",
            headers={"X-Synthetic-Student-Id": "S001"},
        )
        self.assertEqual(status, 401)

    def test_tampered_or_expired_ticket_rejected_with_401(self):
        ticket = create_signed_ticket("S001", self.job1.job_id)
        parts = ticket.split(".")
        # Tamper the signature part
        bad_sig_ticket = f"{parts[0]}.{parts[1]}.{parts[2]}.bad_signature_0000000000000000"
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&ticket={bad_sig_ticket}"
        )
        self.assertEqual(status, 401)

        # Expired ticket
        expired_ticket = create_signed_ticket("S001", self.job1.job_id, ttl_seconds=-10.0)
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&ticket={expired_ticket}"
        )
        self.assertEqual(status, 401)

    def test_ticket_job_binding_enforced(self):
        # Ticket created for job1 used to query job2 MUST fail with 401
        ticket = create_signed_ticket("S001", self.job1.job_id)
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job2.job_id}&ticket={ticket}"
        )
        self.assertEqual(status, 401)

    def test_cross_student_ticket_forbidden_with_zero_leakage(self):
        # Ticket created for S002 used to access S001's job MUST return 403 Forbidden
        ticket_s002 = create_signed_ticket("S002", self.job1.job_id)
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&ticket={ticket_s002}"
        )
        self.assertEqual(status, 403)
        resp = json.loads(data.decode("utf-8"))

        # Zero existence/ownership leakage: MUST NOT mention S001 or job owner
        error_msg = resp["error"]
        self.assertNotIn("S001", error_msg)
        self.assertNotIn("belongs to", error_msg.lower())
        self.assertEqual(
            error_msg, "Forbidden: You do not have permission to view this feedback job."
        )

    def test_session_token_authentication(self):
        # 1. Create synthetic session token via POST /api/auth/synthetic-session
        post_status, post_data, _ = self._request(
            "POST",
            "/api/auth/synthetic-session",
            body=json.dumps({"student_id": "S001"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(post_status, 200)
        session_info = json.loads(post_data.decode("utf-8"))
        token = session_info["token"]
        self.assertEqual(session_info["student_id"], "S001")

        # 2. Access S001's job with Bearer token
        get_status, get_data, _ = self._request(
            "GET",
            f"/api/feedback?job_id={self.job1.job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(get_status, 200)
        job_view = json.loads(get_data.decode("utf-8"))
        self.assertEqual(job_view["job_id"], self.job1.job_id)

        # 3. Access S002's job with S001's Bearer token -> 403 Forbidden
        cross_status, cross_data, _ = self._request(
            "GET",
            f"/api/feedback?job_id={self.job2.job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(cross_status, 403)
        cross_err = json.loads(cross_data.decode("utf-8"))
        self.assertNotIn("S002", cross_err["error"])

    def test_learner_payload_minimization(self):
        ticket = create_signed_ticket("S001", self.job1.job_id)
        status, data, _ = self._request(
            "GET", f"/api/feedback?job_id={self.job1.job_id}&ticket={ticket}"
        )
        self.assertEqual(status, 200)
        view = json.loads(data.decode("utf-8"))

        # Authorized learner-visible keys
        expected_keys = {
            "job_id",
            "status",
            "question_id",
            "submitted_sql",
            "grading",
            "feedback",
            "created_at",
            "completed_at",
            "error",
            "provenance",
        }
        self.assertEqual(set(view.keys()), expected_keys)

        # Internal operational fields MUST NOT be disclosed to learners
        self.assertNotIn("lease_token", view)
        self.assertNotIn("claimed_by", view)
        self.assertNotIn("lease_expires_at", view)
        self.assertNotIn("retries", view)
        self.assertNotIn("max_retries", view)
        self.assertNotIn("version", view)

    def test_synthetic_session_blocked_outside_dev_mode(self):
        # Disable development mode
        old_auth = os.environ.get("SIIP_ALLOW_SYNTHETIC_AUTH")
        old_env = os.environ.get("SIIP_ENV")
        try:
            os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "0"
            os.environ["SIIP_ENV"] = "production"

            status, data, _ = self._request(
                "POST",
                "/api/auth/synthetic-session",
                body=json.dumps({"student_id": "S001"}),
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(status, 403)
            resp = json.loads(data.decode("utf-8"))
            self.assertIn("disabled outside isolated development mode", resp["error"].lower())
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
