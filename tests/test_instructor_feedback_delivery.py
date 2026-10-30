from __future__ import annotations

import http.client
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))
import dashboard
from siip.demo_student import INNER_JOIN_HEADCOUNT_SQL
from siip.grader import QUESTIONS
from siip.identity import create_signed_session_token, create_signed_ticket
from siip.jobs import FeedbackJobRepository
from siip.store import SubmissionRepository


class InstructorDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "SIIP_ENV": "development",
                    "SIIP_ALLOW_SYNTHETIC_AUTH": "1",
                    "SIIP_AUTH_SECRET": secrets.token_hex(32),
                    "SIIP_DEMO_STATE_DIR": str(directory / "demo"),
                    "SIIP_FEEDBACK_JOBS_DB": str(directory / "jobs.sqlite3"),
                },
            )
        )
        self.stack.enter_context(patch.object(dashboard, "DEMO_AUTHORING", None))
        self.registry = dashboard.get_demo_authoring()
        for course in ("course-a", "course-b"):
            self.registry.create_assignment(
                assignment_id="assignment-" + course,
                course_id=course,
                question_ids=["sql_join_04"],
                kg_node_ids=["LEFT_OUTER_JOIN"],
                grading_config={"engine": "deterministic_sql"},
            )
        self.repo = SubmissionRepository(directory / "sub.sqlite3")
        self.jobs = FeedbackJobRepository(directory / "jobs.sqlite3")
        self.a = self.attempt("a1", "course-a", INNER_JOIN_HEADCOUNT_SQL, "2026-10-19T19:00:00Z")
        self.attempt(
            "a2", "course-a", QUESTIONS["sql_join_04"]["reference_sql"], "2026-10-19T20:00:00Z"
        )
        self.attempt("b1", "course-b", INNER_JOIN_HEADCOUNT_SQL, "2026-10-19T21:00:00Z")
        self.job = self.enqueue(self.a, "course-a")
        claimed = self.jobs.claim("test-worker")
        self.jobs.complete(
            job_id=self.job.job_id,
            lease_token=claimed.lease_token,
            result={
                "feedback_text": "Actual completed model feedback",
                "candidate_concepts": ["LEFT_OUTER_JOIN"],
                "inference_status": "live",
                "model_digest": "digest",
                "provider_identifier": "ollama",
            },
            latency_ms=12,
            model_identifier="qwen3:8b",
            prompt_version="v1",
            graph_version="1",
        )
        self.pending = self.enqueue(self.repo.attempt_for_student("b1", "S001"), "course-b")
        self.server = dashboard.DashboardServer(self.repo, 0, host="127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.instructor = create_signed_session_token("instructor_alawini", role="instructor")
        self.student = create_signed_session_token("S001", role="student")

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def attempt(self, aid, course, sql, timestamp):
        return self.repo.process(
            {
                "attempt_id": aid,
                "student_id": "S001",
                "question_id": "sql_join_04",
                "timestamp": timestamp,
                "submitted_sql": sql,
                "source": "synthetic_fixture",
                "assessment_id": "assignment-" + course,
                "course_id": course,
            },
            mode="baseline",
        )

    def enqueue(self, attempt, course):
        return self.jobs.enqueue(
            attempt_id=attempt["attempt_id"],
            student_id=attempt["student_id"],
            question_id=attempt["question_id"],
            submitted_sql=attempt["submitted_sql"],
            grading=attempt["grading"],
            grounding={
                "course_id": course,
                "assignment_id": "assignment-" + course,
                "graph_id": "g",
                "graph_version": 1,
                "source_document_id": "d",
                "source_version": 1,
                "source_sha256": "a" * 64,
            },
        )

    def request(self, path, token=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        conn.request("GET", path, headers={"Authorization": "Bearer " + token} if token else {})
        response = conn.getresponse()
        status, body = response.status, response.read()
        conn.close()
        return status, json.loads(body)

    def test_actual_completed_job_matches_learner_and_is_minimized(self):
        path = "/api/instructor/feedback?" + urlencode(
            {"course_id": "course-a", "attempt_id": "a1"}
        )
        status, instructor = self.request(path, self.instructor)
        self.assertEqual(status, 200)
        ticket = create_signed_ticket("S001", self.job.job_id)
        status, learner = self.request(
            "/api/feedback?" + urlencode({"job_id": self.job.job_id, "ticket": ticket})
        )
        self.assertEqual(status, 200)
        self.assertEqual(instructor["job"], learner)
        self.assertEqual(learner["feedback"]["feedback_text"], "Actual completed model feedback")
        self.assertNotEqual(
            learner["feedback"]["feedback_text"], self.a["feedback"]["feedback_text"]
        )
        self.assertNotIn("reference_sql", json.dumps(instructor))
        self.assertNotIn("lease_token", json.dumps(instructor))
        self.assertEqual(instructor["assignment_id"], "assignment-course-a")

    def test_scope_authorization_pending_and_inconsistent_grounding(self):
        path = "/api/instructor/feedback?course_id=course-a&attempt_id=a1"
        self.assertEqual(self.request(path)[0], 401)
        self.assertEqual(self.request(path, self.student)[0], 403)
        self.assertEqual(
            self.request(
                "/api/instructor/feedback?course_id=course-b&attempt_id=a1", self.instructor
            )[0],
            404,
        )
        self.assertEqual(
            self.request(
                "/api/instructor/feedback?course_id=unknown&attempt_id=a1", self.instructor
            )[0],
            404,
        )
        status, body = self.request(
            "/api/instructor/feedback?course_id=course-b&attempt_id=b1", self.instructor
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["status"], "pending")
        self.assertIsNone(body["job"]["feedback"])
        with closing(self.jobs.connect()) as db:
            row = db.execute(
                "SELECT grading FROM feedback_jobs WHERE job_id=?", (self.pending.job_id,)
            ).fetchone()
            grading = json.loads(row[0])
            grading["_grounding"]["course_id"] = "course-a"
            db.execute(
                "UPDATE feedback_jobs SET grading=? WHERE job_id=?",
                (json.dumps(grading), self.pending.job_id),
            )
            db.commit()
        self.assertEqual(
            self.request(
                "/api/instructor/feedback?course_id=course-b&attempt_id=b1", self.instructor
            )[0],
            404,
        )

    def test_scoped_analytics_evidence_and_aggregate_compatibility(self):
        path = "/api/instructor/analytics?course_id=course-a"
        self.assertEqual(self.request(path, self.student)[0], 403)
        self.assertEqual(
            self.request("/api/instructor/analytics?course_id=unknown", self.instructor)[0], 404
        )
        status, data = self.request(path, self.instructor)
        self.assertEqual(status, 200)
        self.assertEqual(data["attempt_ids"], ["a1", "a2"])
        self.assertEqual(data["attempt_count"], 2)
        self.assertEqual(data["correct"], 1)
        self.assertEqual(data["improvements"][0]["from_attempt_id"], "a1")
        self.assertEqual(data["improvements"][0]["to_attempt_id"], "a2")
        self.assertIn("a1", sum(data["observed_errors"].values(), []))
        self.assertEqual(self.request("/api/analytics", self.instructor)[1]["attempt_count"], 3)


if __name__ == "__main__":
    unittest.main()
