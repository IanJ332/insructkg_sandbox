"""Release regressions for reproduced authorization and teaching failures."""

import http.client
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from dashboard import DashboardServer, pretty
from siip import identity
from siip.demo_kg import DemoKGRepository
from siip.feedback import generate_feedback
from siip.grader import QUESTIONS, grade
from siip.identity import create_signed_session_token, get_auth_secret, synthetic_auth_enabled
from siip.jobs import AttemptConflictError, FeedbackJobRepository, FeedbackWorker
from siip.project_generator import ProjectRepository, generate_personalized_project
from siip.store import SubmissionRepository


class ReleaseAuthenticationTests(unittest.TestCase):
    def test_empty_persisted_key_fails_closed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(identity, "DATA_DIR", Path(directory)),
            patch.dict(os.environ),
        ):
            os.environ.pop("SIIP_AUTH_SECRET", None)
            (Path(directory) / "auth_secret.key").write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "key is empty"):
                get_auth_secret()

    def test_persisted_binary_key_is_never_trimmed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(identity, "DATA_DIR", Path(directory)),
            patch.dict(os.environ),
        ):
            os.environ.pop("SIIP_AUTH_SECRET", None)
            key = b"\n" + b"x" * 30 + b"\t"
            (Path(directory) / "auth_secret.key").write_bytes(key)
            self.assertEqual(get_auth_secret(), key)
            token = create_signed_session_token("S001", secret=key)
            self.assertEqual(identity.verify_signed_session_token(token), "S001")

    def test_policy_requires_explicit_development_and_opt_in(self):
        for environment, flag, enabled in (
            (None, None, False),
            (None, "1", False),
            ("production", "1", False),
            ("development", None, False),
            ("development", "0", False),
            ("development", "1", True),
            ("staging", "1", False),
        ):
            with self.subTest(environment=environment, flag=flag), patch.dict(os.environ):
                for key, value in (("SIIP_ENV", environment), ("SIIP_ALLOW_SYNTHETIC_AUTH", flag)):
                    os.environ.pop(key, None)
                    if value is not None:
                        os.environ[key] = value
                self.assertEqual(synthetic_auth_enabled(), enabled)

    def test_production_startup_rejected_with_either_flag(self):
        for flag in ("0", "1"):
            with patch.dict(
                os.environ, {"SIIP_ENV": "production", "SIIP_ALLOW_SYNTHETIC_AUTH": flag}
            ):
                with self.assertRaisesRegex(ValueError, "Hosted authentication is unavailable"):
                    DashboardServer(None, 0)

    def test_blank_signing_key_rejected(self):
        with patch.dict(os.environ, {"SIIP_AUTH_SECRET": "   "}):
            with self.assertRaises(ValueError):
                get_auth_secret()

    def test_http_login_and_credentials_fail_closed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "SIIP_ENV": "development",
                    "SIIP_ALLOW_SYNTHETIC_AUTH": "1",
                    "SIIP_AUTH_SECRET": secrets.token_hex(32),
                    "SIIP_SERVICE_KEY": secrets.token_hex(32),
                },
            ),
        ):
            server = DashboardServer(SubmissionRepository(Path(directory) / "test.sqlite3"), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(method, path, body=None, token=None):
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = "Bearer " + token
                conn.request(method, path, json.dumps(body) if body else None, headers)
                response = conn.getresponse()
                result = response.status, response.read()
                conn.close()
                return result

            try:
                status, body = request(
                    "POST", "/api/auth/synthetic-session", {"instructor_id": "instructor_alawini"}
                )
                self.assertEqual(status, 200)
                token = json.loads(body)["token"]
                self.assertEqual(request("GET", "/api/demo/lessons", token="invalid")[0], 401)
                student = create_signed_session_token("S001")
                self.assertEqual(request("GET", "/api/demo/lessons", token=student)[0], 403)
                self.assertEqual(
                    request("POST", "/api/auth/synthetic-session", {"instructor_id": "arbitrary"})[
                        0
                    ],
                    400,
                )
                for env, flag in (
                    ("production", "1"),
                    ("production", "0"),
                    ("development", "0"),
                    (None, None),
                ):
                    with patch.dict(os.environ):
                        os.environ.pop("SIIP_ENV", None)
                        os.environ.pop("SIIP_ALLOW_SYNTHETIC_AUTH", None)
                        if env:
                            os.environ["SIIP_ENV"] = env
                        if flag:
                            os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = flag
                        self.assertEqual(request("GET", "/login")[0], 403)
                        self.assertEqual(
                            request(
                                "POST",
                                "/api/auth/synthetic-session",
                                {"instructor_id": "instructor_alawini"},
                            )[0],
                            403,
                        )
                        self.assertEqual(request("GET", "/api/demo/lessons", token=token)[0], 401)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class ReleaseFeedbackTests(unittest.TestCase):
    def test_left_join_count_identifier_is_correct(self):
        result = grade("sql_join_04", QUESTIONS["sql_join_04"]["reference_sql"])
        self.assertEqual(result["score"], 1)
        self.assertTrue(
            any(row[1] == 0 for dataset in result["datasets"] for row in dataset["actual"]["rows"])
        )

    def test_historical_misdiagnosis_falls_back_without_changing_grade(self):
        sql = QUESTIONS["sql_join_04"]["reference_sql"].replace("LEFT JOIN", "INNER JOIN")
        result = grade("sql_join_04", sql)
        before = json.dumps(result, sort_keys=True)
        self.assertEqual(result["score"], 0)
        for explanation in (
            "Your INNER JOIN excludes unstaffed departments. Additionally, the COUNT function may not correctly handle NULL values from the right table.",
            "Review your GROUP BY because grouping might be incorrect.",
        ):

            class Provider:
                model = "stored-response-fixture"

                def generate(self, context):
                    return {
                        "feedback_text": explanation,
                        "candidate_concepts": [],
                        "evidence_references": [],
                    }, None

            feedback = generate_feedback(
                "sql_join_04", sql, result, mode="baseline", provider=Provider()
            )
            self.assertEqual(feedback["feedback_quality"], "review_required_fallback")
            self.assertEqual(feedback["inference_status"], "feedback_quality_fallback")
            self.assertNotIn("COUNT", feedback["feedback_text"])
            self.assertEqual(json.dumps(result, sort_keys=True), before)

    def test_accepted_model_guidance_remains_unreviewed(self):
        class Provider:
            model = "fixture"

            def generate(self, context):
                return {
                    "feedback_text": "Consider which departments should remain visible.",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }, None

        feedback = generate_feedback(
            "sql_join_04",
            "SELECT 1",
            {"status": "semantic_error", "score": 0, "observation": "result_mismatch"},
            mode="baseline",
            provider=Provider(),
        )
        self.assertEqual(feedback["feedback_quality"], "model_unreviewed")

    def test_pretty_escapes_once_and_keeps_markup_inert(self):
        rendered = pretty({"source": '<script>alert("x")</script>'})
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("&amp;quot;", rendered)


class ReleaseConsistencyTests(unittest.TestCase):
    def test_instructor_project_review_history_is_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ProjectRepository(Path(directory) / "projects.sqlite3")
            project = generate_personalized_project("S001", "healthcare")
            repository.save_project(project)
            repository.review_project(
                project.project_id, "REVISED", "instructor_alawini", "Clarify scope"
            )
            repository.review_project(
                project.project_id, "APPROVED", "instructor_ta", "Reviewed revision"
            )
            with closing(repository.connect()) as db:
                rows = db.execute(
                    "SELECT decision, reviewer_id FROM instructor_review_history ORDER BY rowid"
                ).fetchall()
            self.assertEqual(
                [tuple(row) for row in rows],
                [("REVISED", "instructor_alawini"), ("APPROVED", "instructor_ta")],
            )

    def test_competing_graph_saves_preserve_every_snapshot(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"SIIP_DEMO_KG_MODE": "synthetic"}),
        ):
            kg = DemoKGRepository(directory)
            graph = kg.generate_candidates(
                {
                    "source_document_id": "lesson",
                    "content": "INNER JOIN predicate. LEFT OUTER JOIN preserves unmatched rows with NULL values.",
                }
            )

            def save(_):
                return DemoKGRepository(directory).save_version(graph["graph_id"])

            with ThreadPoolExecutor(max_workers=4) as executor:
                snapshots = list(executor.map(save, range(8)))
            self.assertEqual(len({snapshot["version"] for snapshot in snapshots}), 8)
            for snapshot in snapshots:
                self.assertEqual(kg.retrieve(graph["graph_id"], snapshot["version"]), snapshot)

    def test_current_and_later_attempts_are_not_prior_history(self):
        with tempfile.TemporaryDirectory() as directory:
            submissions = SubmissionRepository(Path(directory) / "sub.sqlite3")
            queue = FeedbackJobRepository(Path(directory) / "jobs.sqlite3")
            for identifier, timestamp in (
                ("current", "2026-10-19T01:00:00Z"),
                ("later", "2026-10-19T02:00:00Z"),
            ):
                submissions.process(
                    {
                        "attempt_id": identifier,
                        "student_id": "S001",
                        "question_id": "sql_join_04",
                        "submitted_sql": "SELECT 1",
                        "timestamp": timestamp,
                        "source": "synthetic_fixture",
                    }
                )
            job = queue.enqueue(
                "current",
                "S001",
                "sql_join_04",
                "SELECT 1",
                {"status": "semantic_error", "score": 0, "observation": "result_mismatch"},
            )
            FeedbackWorker(queue, submission_repo=submissions).process_one()
            self.assertFalse(queue.get(job.job_id).result["personalized"])

    def test_reconciliation_without_caller_evidence_rejects_cross_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = FeedbackJobRepository(Path(directory) / "jobs.sqlite3")
            result = {"status": "correct", "score": 1, "observation": "correct"}
            queue.enqueue("provisional", "S001", "sql_join_04", "SELECT 1", result)
            queue.enqueue("authoritative", "S002", "sql_join_04", "SELECT 1", result)
            with self.assertRaises(AttemptConflictError):
                queue.reconcile("provisional", "authoritative")


if __name__ == "__main__":
    unittest.main()
