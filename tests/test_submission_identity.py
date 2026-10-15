"""Submission identity and idempotency test suite for SIIP async queue.
Verifies authoritative pl-{submission_id} vs provisional prov-{student_id}-{qid}-{event_id},
prevents collapsing identical SQL into single attempts, and tests reconciliation.
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
from siip.jobs import AttemptConflictError, FeedbackJobRepository
from siip.pl_bridge import grade_question
from siip.store import SubmissionRepository


class TestSubmissionIdentityAndIdempotency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "jobs.sqlite3"
        self.sub_db = Path(self.tmp.name) / "sub.sqlite3"
        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.db_path)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ASYNC_FEEDBACK"] = "1"
        os.environ["SIIP_FEEDBACK_PROVIDER"] = "local"

        self.repo = FeedbackJobRepository(self.db_path)
        self.sub_repo = SubmissionRepository(self.sub_db)

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

    def test_identical_sql_generates_distinct_provisional_attempts(self):
        # Two consecutive submissions with identical SQL from the same student
        # MUST generate distinct provisional attempt records, not overwrite each other.
        data1 = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data1, "sql_join_02")
        job_id_1 = data1["feedback"]["siip"]["job_id"]
        attempt_id_1 = data1["feedback"]["siip"]["attempt_id"]

        data2 = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data2, "sql_join_02")
        job_id_2 = data2["feedback"]["siip"]["job_id"]
        attempt_id_2 = data2["feedback"]["siip"]["attempt_id"]

        self.assertNotEqual(job_id_1, job_id_2)
        self.assertNotEqual(attempt_id_1, attempt_id_2)
        self.assertTrue(attempt_id_1.startswith("prov-S001-sql_join_02-"))
        self.assertTrue(attempt_id_2.startswith("prov-S001-sql_join_02-"))
        self.assertEqual(data1["feedback"]["siip"]["attempt_kind"], "provisional")
        self.assertEqual(data2["feedback"]["siip"]["attempt_kind"], "provisional")

        # Verify both jobs exist independently in repository
        job1 = self.repo.get(job_id_1)
        job2 = self.repo.get(job_id_2)
        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertEqual(self.repo.stats()["pending"], 2)

    def test_same_variant_does_not_collapse_distinct_submissions(self):
        # Submissions on the same variant with different SQL must each be preserved
        data1 = {
            "submitted_answers": {"sql": "SELECT 1;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "variant_id": 9999,
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data1, "sql_join_01")

        data2 = {
            "submitted_answers": {"sql": "SELECT 2;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "variant_id": 9999,
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data2, "sql_join_01")

        job_id_1 = data1["feedback"]["siip"]["job_id"]
        job_id_2 = data2["feedback"]["siip"]["job_id"]
        self.assertNotEqual(job_id_1, job_id_2)

    def test_authoritative_submission_id_is_idempotent(self):
        # When an authoritative submission_id is available from core PL,
        # re-submitting identical payload returns the exact same job record.
        data1 = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "submission_id": 54321,
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data1, "sql_join_02")
        job_id_1 = data1["feedback"]["siip"]["job_id"]
        attempt_id_1 = data1["feedback"]["siip"]["attempt_id"]
        self.assertEqual(attempt_id_1, "pl-54321")
        self.assertEqual(data1["feedback"]["siip"]["attempt_kind"], "authoritative")

        # Idempotent re-grading
        data2 = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "submission_id": 54321,
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data2, "sql_join_02")
        job_id_2 = data2["feedback"]["siip"]["job_id"]
        self.assertEqual(job_id_1, job_id_2)
        self.assertEqual(self.repo.stats()["pending"], 1)

    def test_authoritative_attempt_conflict_rejected(self):
        grading = {"status": "ok", "score": 1.0}
        self.repo.enqueue("pl-1111", "S001", "sql_join_01", "SELECT 1;", grading)

        # Conflicting payload under same authoritative attempt ID raises AttemptConflictError
        with self.assertRaises(AttemptConflictError):
            self.repo.enqueue("pl-1111", "S001", "sql_join_01", "SELECT 2;", grading)

    def test_provisional_reconciliation_workflow(self):
        # 1. Enqueue provisional live event
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }
        prov_job = self.repo.enqueue(
            "prov-S001-sql_join_02-event123",
            "S001",
            "sql_join_02",
            "SELECT name FROM Employees;",
            grading,
            attempt_kind="provisional",
        )
        self.assertEqual(prov_job.attempt_kind, "provisional")

        # 2. Later ingestion reconciles provisional event with authoritative submission ID
        reconciled = self.repo.reconcile(
            provisional_attempt_id="prov-S001-sql_join_02-event123",
            authoritative_attempt_id="pl-8888",
        )
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.job_id, prov_job.job_id)
        self.assertEqual(reconciled.attempt_id, "pl-8888")
        self.assertEqual(reconciled.attempt_kind, "reconciled")
        self.assertEqual(reconciled.reconciled_from, "prov-S001-sql_join_02-event123")

        # 3. Can fetch by authoritative attempt ID
        fetched = self.repo.get_by_attempt("pl-8888")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.job_id, prov_job.job_id)

    def test_http_queue_enqueue_and_reconcile(self):
        # Test HTTP POST /api/queue/enqueue
        post_body = json.dumps(
            {
                "student_id": "S001",
                "question_id": "sql_join_02",
                "submitted_sql": "SELECT 1;",
                "grading": {"status": "ok", "score": 1.0, "observation": "correct"},
                "feedback_mode": "kg",
            }
        )
        status, data, _ = self._request(
            "POST",
            "/api/queue/enqueue",
            body=post_body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 201)
        res = json.loads(data.decode("utf-8"))
        job_id = res["job_id"]
        attempt_id = res["attempt_id"]
        ticket = res["ticket"]
        self.assertTrue(attempt_id.startswith("prov-S001-sql_join_02-"))
        self.assertIsNotNone(ticket)

        # Test HTTP POST /api/queue/reconcile
        rec_body = json.dumps(
            {
                "provisional_attempt_id": attempt_id,
                "authoritative_attempt_id": "pl-9999",
            }
        )
        r_status, r_data, _ = self._request(
            "POST",
            "/api/queue/reconcile",
            body=rec_body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r_status, 200)
        rec_res = json.loads(r_data.decode("utf-8"))
        self.assertEqual(rec_res["status"], "reconciled")
        self.assertEqual(rec_res["attempt_id"], "pl-9999")
        self.assertEqual(rec_res["job_id"], job_id)


if __name__ == "__main__":
    unittest.main()
