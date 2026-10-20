"""Real HTTP authorization checks against an isolated dashboard and temporary stores.

These tests do not substitute for the browser lifecycle acceptance test.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

import dashboard
from siip.demo_student import INNER_JOIN_HEADCOUNT_SQL
from siip.identity import create_signed_session_token, generate_csrf_token
from siip.store import SubmissionRepository


class DemoHTTPAuthorizationTests(unittest.TestCase):
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
                    "SIIP_DB_PATH": str(directory / "submissions.sqlite3"),
                    "SIIP_EM_DB_PATH": str(directory / "em.sqlite3"),
                    "SIIP_PROJECT_DB_PATH": str(directory / "projects.sqlite3"),
                    "SIIP_FEEDBACK_JOBS_DB": str(directory / "jobs.sqlite3"),
                    "SIIP_DEMO_STATE_DIR": str(directory / "demo"),
                    "SIIP_DEMO_ARTIFACT_DIR": str(directory / "timeline"),
                    "SIIP_AUTH_SECRET": "isolated-demo-test-secret",
                    "SIIP_SERVICE_KEY": "isolated-demo-test-service-key",
                },
            )
        )
        for name in ("DEMO_AUTHORING", "DEMO_KG", "DEMO_OBSERVABILITY"):
            self.stack.enter_context(patch.object(dashboard, name, None))
        self.registry = dashboard.get_demo_authoring()
        for assignment_id in ("draft", "published"):
            self.registry.create_assignment(
                assignment_id=assignment_id,
                course_id="course",
                question_ids=["sql_join_04"],
                kg_node_ids=["LEFT_OUTER_JOIN"],
                grading_config={"engine": "deterministic_sql"},
            )
        self.registry.publish_assignment("published")
        self.repo = SubmissionRepository(directory / "submissions.sqlite3")
        self.server = dashboard.DashboardServer(self.repo, 0, host="127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.student = create_signed_session_token("S001", role="student")
        self.instructor = create_signed_session_token("instructor_alawini", role="instructor")

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, *, token=None, fields=None, headers=None):
        request_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        connection.request(
            method,
            path,
            body=urlencode(fields or {}) if method == "POST" else None,
            headers=request_headers,
        )
        response = connection.getresponse()
        result = response.status, response.read().decode("utf-8")
        connection.close()
        return result

    def test_unauthenticated_authoring_reads_and_writes_fail_closed(self):
        for path in (
            "/authoring",
            "/demo-graph",
            "/api/demo/lessons",
            "/api/demo/graphs",
            "/api/demo/events",
            "/timeline",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 401)
        for path in (
            "/api/demo/lessons/upload",
            "/api/demo/kg/generate",
            "/api/demo/kg/review",
            "/api/demo/kg/save",
            "/api/demo/assignments/create",
            "/api/demo/assignments/publish",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path)[0], 401)

    def test_student_cannot_approve_graph_or_publish_assignment(self):
        for path in (
            "/api/demo/lessons/upload",
            "/api/demo/kg/generate",
            "/api/demo/kg/review",
            "/api/demo/kg/save",
            "/api/demo/assignments/create",
            "/api/demo/assignments/publish",
        ):
            with self.subTest(path=path):
                status, _ = self.request(
                    "POST",
                    path,
                    token=self.student,
                    fields={"assignment_id": "draft", "decision": "APPROVE"},
                )
                self.assertEqual(status, 403)
        self.assertEqual(self.registry.get_assignment("draft").publication_status, "DRAFT")
        self.assertEqual(self.registry.list_lessons(), [])

    def test_instructor_cookie_actions_require_session_bound_csrf(self):
        status, _ = self.request(
            "POST",
            "/api/demo/assignments/publish",
            token=self.instructor,
            fields={"assignment_id": "draft"},
        )
        self.assertEqual(status, 403)
        status, _ = self.request(
            "POST",
            "/api/demo/assignments/publish",
            token=self.instructor,
            fields={"assignment_id": "draft", "csrf_token": generate_csrf_token(self.student)},
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.registry.get_assignment("draft").publication_status, "DRAFT")

    def test_draft_assignments_are_hidden_and_cannot_be_submitted(self):
        status, body = self.request("GET", "/api/demo/assignments", token=self.student)
        self.assertEqual(status, 200)
        self.assertEqual([row["assignment_id"] for row in json.loads(body)], ["published"])
        status, _ = self.request(
            "POST",
            "/practice",
            token=self.student,
            fields={
                "assignment_id": "draft",
                "question_id": "sql_join_04",
                "sql": INNER_JOIN_HEADCOUNT_SQL,
                "csrf_token": generate_csrf_token(self.student),
            },
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.repo.records(), [])

    def test_cross_student_profiles_and_recommendations_are_forbidden(self):
        for path in (
            "/students?id=S002",
            "/api/recommendation?student_id=S002",
            "/api/em/summary?student_id=S002",
            "/api/cohort-analytics",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path, token=self.student)[0], 403)

    def test_legacy_feedback_lab_and_cohort_exports_are_instructor_only(self):
        for path in ("/compare", "/graph", "/api/analytics"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 401)
                self.assertEqual(self.request("GET", path, token=self.student)[0], 403)
                self.assertEqual(self.request("GET", path, token=self.instructor)[0], 200)

    def test_legacy_attempt_ingestion_enforces_signed_ownership(self):
        fields = {"student_id": "S002", "question_id": "sql_join_04", "sql": "SELECT 1"}
        self.assertEqual(self.request("POST", "/attempt", fields=fields)[0], 401)
        self.assertEqual(
            self.request("POST", "/attempt", token=self.student, fields=fields)[0], 403
        )
        self.assertEqual(self.repo.records(), [])

    def test_extraction_failure_persists_failed_source_state(self):
        lesson = self.registry.upload_lesson(
            (ROOT / "demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md").read_bytes(),
            source_document_id="failed-source",
            course_id="sql-demo",
            original_filename="failed.md",
        )
        with patch.object(
            dashboard.get_demo_kg(),
            "generate_candidates",
            side_effect=RuntimeError("injected unavailable extractor"),
        ):
            status, _ = self.request(
                "POST",
                "/api/demo/kg/generate",
                token=self.instructor,
                fields={
                    "source_document_id": lesson.source_document_id,
                    "version": lesson.version,
                    "csrf_token": generate_csrf_token(self.instructor),
                },
            )
        self.assertEqual(status, 503)
        self.assertEqual(
            self.registry.get_lesson(lesson.source_document_id, lesson.version).processing_status,
            "FAILED",
        )

    def test_cross_origin_publication_rejected_before_mutation(self):
        status, _ = self.request(
            "POST",
            "/api/demo/assignments/publish",
            token=self.instructor,
            fields={"assignment_id": "draft", "csrf_token": generate_csrf_token(self.instructor)},
            headers={"Origin": "https://untrusted.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.registry.get_assignment("draft").publication_status, "DRAFT")

    def test_forged_role_and_signature_cannot_establish_authority(self):
        for token in (
            self.instructor + "tampered",
            create_signed_session_token("S001", role="instructor"),
            create_signed_session_token("unrecognized", role="instructor"),
        ):
            with self.subTest(token_kind=token.split(".")[0]):
                self.assertEqual(self.request("GET", "/api/demo/lessons", token=token)[0], 401)


if __name__ == "__main__":
    unittest.main()
