"""Cross-validation regressions. All identities/providers/API responses are synthetic."""

import concurrent.futures
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import ProviderConfig
from siip.extraction import backend_environment
from siip.feedback import CompatibleProvider, generate_feedback, minimize_mastery
from siip.grader import QUESTIONS, grade
from siip.personalization import FeedbackPrincipal, feedback_for_attempt, synthetic_principal
from siip.pl_bridge import grade_question
from siip.sources import APIReadError, AuthorizedPrairieLearnAPISource
from siip.store import SubmissionRepository
from siip.synchronization import SubmissionSynchronizer

QID = "sql_join_02"
GOOD = QUESTIONS[QID]["reference_sql"]
BAD = QUESTIONS["sql_join_01"]["reference_sql"]


def attempt(aid, sid="S001", sql=BAD, timestamp="2026-10-14T11:00:00Z"):
    return {
        "attempt_id": aid,
        "student_id": sid,
        "question_id": QID,
        "submitted_sql": sql,
        "timestamp": timestamp,
    }


def api_row(submission="12", *, user="101", sql=BAD, date="2026-10-14T11:00:00Z", score=0):
    return {
        "submission_id": submission,
        "user_id": user,
        "group_id": None,
        "question_name": QID,
        "assessment_id": "7000",
        "assessment_instance_id": "9000",
        "variant_id": "8000",
        "date": date,
        "submitted_answer": {"sql": sql},
        "score": score,
        "user_name": "SENSITIVE_NAME_NOT_FOR_STORAGE",
        "user_uid": "SENSITIVE_UID_NOT_FOR_STORAGE",
        "true_answer": {"sql": "HIDDEN_REFERENCE_NOT_FOR_STORAGE"},
    }


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = SubmissionRepository(Path(self.tmp.name) / "store.sqlite3")


class PersonalizationTests(RepoCase):
    def feedback(self, aid, sid="S001", **kwargs):
        return feedback_for_attempt(
            self.repo, aid, synthetic_principal(sid, authorized=True), **kwargs
        )

    def seed_contrasting_histories(self):
        self.repo.process(attempt("prior-weak", sql=BAD, timestamp="2026-10-14T09:00:00Z"))
        self.repo.process(
            attempt("prior-strong", sid="S002", sql=GOOD, timestamp="2026-10-14T09:00:00Z")
        )
        self.repo.process(attempt("current-weak"))
        self.repo.process(attempt("current-strong", sid="S002"))

    def test_same_sql_distinct_histories_change_feedback_without_changing_grade(self):
        self.seed_contrasting_histories()
        before = self.repo.records()
        weak = self.feedback("current-weak")
        strong = self.feedback("current-strong", "S002")
        self.assertNotEqual(weak["feedback"]["feedback_text"], strong["feedback"]["feedback_text"])
        self.assertIn("Earlier attempts suggest revisiting", weak["feedback"]["feedback_text"])
        self.assertIn("positive evidence", strong["feedback"]["feedback_text"])
        self.assertEqual(weak["feedback"]["inference_status"], "deterministic_fallback")
        self.assertEqual(self.repo.records(), before)
        self.assertEqual(weak["evidence_receipt"]["prior_attempt_count"], 1)
        self.assertEqual(
            weak["evidence_receipt"]["feedback_origin"], "authorized_post_submission_replay"
        )
        self.assertTrue(all(r["feedback_origin"] == "local_analytics_recomputed" for r in before))

    def test_provider_context_is_minimized_and_subject_isolated(self):
        self.seed_contrasting_histories()
        contexts = []

        class ContractProvider:
            model = "synthetic-contract"

            def generate(self, context):
                contexts.append(context)
                raise TimeoutError("discard body")

        self.feedback("current-weak", provider=ContractProvider())
        context = contexts[0]
        serialized = json.dumps(context)
        self.assertNotIn("S001", serialized)
        self.assertNotIn("S002", serialized)
        self.assertNotIn("prior-", serialized)
        self.assertNotIn("submitted_sql", json.dumps(context["student_mastery"]))
        evidence = context["student_mastery"]["LEFT_OUTER_JOIN"]
        self.assertAlmostEqual(evidence["mastery_estimate"], 1 / 3)
        self.assertEqual(set(evidence), {"mastery_estimate", "evidence_count", "question_count"})

    def test_strict_prior_cutoff_excludes_current_equal_future_and_other_student(self):
        self.repo.process(attempt("prior", timestamp="2026-10-14T09:00:00Z"))
        self.repo.process(attempt("equal", sql=GOOD))
        self.repo.process(attempt("future", sql=GOOD, timestamp="2026-10-15T09:00:00Z"))
        self.repo.process(attempt("other", sid="S002", sql=GOOD, timestamp="2026-10-14T08:00:00Z"))
        self.repo.process(attempt("current"))
        result = self.feedback("current")
        self.assertEqual(result["evidence_receipt"]["prior_attempt_count"], 1)
        self.assertIn("suggest revisiting", result["feedback"]["feedback_text"])

    def test_no_history_is_explicitly_not_personalized(self):
        self.repo.process(attempt("current"))
        result = self.feedback("current")
        self.assertEqual(result["feedback"]["historical_personalization"]["status"], "none")
        self.assertNotIn("Earlier attempts", result["feedback"]["feedback_text"])

    def test_compilation_failures_do_not_become_mastery_evidence(self):
        self.repo.process(attempt("prior", sql="SELEC name", timestamp="2026-10-14T09:00:00Z"))
        self.repo.process(attempt("current"))
        self.assertEqual(
            self.feedback("current")["feedback"]["historical_personalization"]["status"], "none"
        )

    def test_grant_required_and_cross_student_access_denied_without_existence_leak(self):
        with self.assertRaises(PermissionError):
            synthetic_principal("S001")
        with self.assertRaises(PermissionError):
            synthetic_principal("not-a-synthetic-student", authorized=True)
        self.repo.process(attempt("current"))
        for principal in [
            None,
            {"student_id": "S001"},
            FeedbackPrincipal("S001", "untrusted"),
            synthetic_principal("S002", authorized=True),
        ]:
            with (
                self.subTest(principal=type(principal).__name__),
                self.assertRaises(PermissionError),
            ):
                feedback_for_attempt(self.repo, "current", principal)
        with self.assertRaisesRegex(PermissionError, "Feedback access denied"):
            self.feedback("missing")

    def test_pl_hook_ignores_untrusted_identity_and_history_fields(self):
        data = {
            "submitted_answers": {"sql": BAD, "student_id": "S001"},
            "params": {"student_id": "S001", "student_mastery": {"LEFT_OUTER_JOIN": 0}},
            "partial_scores": {},
            "feedback": {},
        }
        with patch("siip.pl_bridge.configured_provider", return_value=None):
            grade_question(data, QID)
        self.assertEqual(data["score"], 0)
        self.assertEqual(data["feedback"]["siip"]["feedback_origin"], "prairielearn_hook_immediate")
        self.assertEqual(
            data["feedback"]["siip"]["feedback"]["historical_personalization"]["status"], "none"
        )

    def test_only_valid_relevant_aggregates_enter_context(self):
        raw = {
            "LEFT_OUTER_JOIN": {
                "mastery_estimate": 0.3,
                "denominator": 1,
                "attempt_count": 2,
                "student_id": "S001",
                "history": ["raw private SQL"],
            },
            "IRRELEVANT": {"mastery_estimate": 0.1, "denominator": 1, "attempt_count": 1},
            "UNMATCHED_ROWS": {
                "mastery_estimate": float("nan"),
                "denominator": 1,
                "attempt_count": 1,
            },
        }
        selected = minimize_mastery(QID, raw)
        self.assertEqual(set(selected), {"LEFT_OUTER_JOIN"})
        self.assertNotIn("private", json.dumps(selected))
        self.assertNotIn("student", json.dumps(selected))

    def test_late_prior_evidence_changes_replay_without_mutating_original_attempt(self):
        self.repo.process(attempt("current"))
        current = self.repo.attempt_for_student("current", "S001")
        first = self.feedback("current")
        self.repo.process(attempt("late-prior", timestamp="2026-10-14T09:00:00Z"))
        replay = self.feedback("current")
        self.assertNotEqual(first["feedback"]["feedback_text"], replay["feedback"]["feedback_text"])
        self.assertEqual(self.repo.attempt_for_student("current", "S001"), current)


class MockAPIBase(RepoCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.server.requests.append((self.path, self.headers.get("Private-Token")))
                if self.server.failure is not None:
                    self.server.failure()
                self.send_response(self.server.response_status)
                for key, value in self.server.extra_headers.items():
                    self.send_header(key, value)
                self.end_headers()
                body = self.server.body
                self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        super().setUp()
        self.server.body, self.server.response_status, self.server.extra_headers = [], 200, {}
        self.server.requests, self.server.failure = [], None
        self.source = AuthorizedPrairieLearnAPISource(
            f"http://127.0.0.1:{self.server.server_port}",
            "synthetic-contract",
            5000,
            9000,
            {"101": "S001", "102": "S002"},
            authorized=True,
            assessment_id=7000,
        )
        self.sync = SubmissionSynchronizer(self.repo, self.source)


class SynchronizationTests(MockAPIBase):
    def test_api_sync_to_profiles_to_distinct_authorized_feedback(self):
        self.server.body = [
            api_row("1", date="2026-10-14T09:00:00Z"),
            api_row("2", user="102", sql=GOOD, score=1, date="2026-10-14T09:00:00Z"),
            api_row("3"),
            api_row("4", user="102"),
        ]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 4)
        feedbacks = []
        for sid, number in [("S001", "3"), ("S002", "4")]:
            aid = "pl-api-" + self.source.scope[:20] + "-" + number
            feedbacks.append(
                feedback_for_attempt(self.repo, aid, synthetic_principal(sid, authorized=True))
            )
        self.assertNotEqual(
            feedbacks[0]["feedback"]["feedback_text"], feedbacks[1]["feedback"]["feedback_text"]
        )
        self.assertEqual([r["evidence_receipt"]["prior_attempt_count"] for r in feedbacks], [1, 1])
        self.assertTrue(
            all(r["feedback"]["inference_status"] == "deterministic_fallback" for r in feedbacks)
        )

    def test_supported_get_and_identity_minimization(self):
        self.server.body = [api_row()]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 1)
        self.assertEqual(
            self.server.requests[0][0],
            "/pl/api/v1/course_instances/5000/assessment_instances/9000/submissions",
        )
        self.assertEqual(self.server.requests[0][1], "synthetic-contract")
        saved = self.repo.records()[0]
        self.assertEqual(saved["student_id"], "S001")
        self.assertNotIn("SENSITIVE", json.dumps(saved))
        self.assertNotIn("HIDDEN_REFERENCE", json.dumps(saved))

    def test_identical_duplicates_and_repeat_poll_are_idempotent(self):
        self.server.body = [api_row(), api_row()]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 1)
        state = self.repo.checkpoint_state(self.source.scope)
        self.assertEqual(self.sync.sync_once()["inserted_count"], 0)
        self.assertEqual(len(self.repo.records()), 1)
        self.assertEqual(self.repo.checkpoint_state(self.source.scope), state)

    def test_conflicting_duplicate_aborts_everything(self):
        self.server.body = [api_row(), api_row(user="102")]
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
            self.sync.sync_once()
        self.assertEqual(self.repo.records(), [])
        self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_incremental_ingestion_and_profile_updates(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        first = self.repo.profile("S001")["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]
        self.server.body += [api_row("13", sql=GOOD, score=1, date="2026-10-14T12:00:00Z")]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 1)
        self.assertGreater(
            self.repo.profile("S001")["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"], first
        )
        self.assertEqual(self.repo.profile("S002")["history"], [])

    def test_late_lower_id_not_lost_by_high_water_and_event_time_wins(self):
        self.server.body = [api_row("20", sql=GOOD, score=1, date="2026-10-14T12:00:00Z")]
        self.sync.sync_once()
        self.server.body = [api_row("3", date="2026-10-14T09:00:00Z"), *self.server.body]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 1)
        self.assertAlmostEqual(
            self.repo.profile("S001")["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"], 2 / 3
        )

    def test_pending_grade_deferred_and_revisited(self):
        self.server.body = [api_row(score=None)]
        self.assertEqual(self.sync.sync_once()["deferred_count"], 1)
        self.assertEqual(self.repo.records(), [])
        self.server.body = [api_row()]
        self.assertEqual(self.sync.sync_once()["inserted_count"], 1)

    def test_missing_mapping_or_scope_and_groups_fail_closed(self):
        for row in [
            api_row(user="999"),
            {**api_row(), "assessment_instance_id": "9999"},
            {**api_row(), "assessment_id": "9999"},
            {**api_row(), "group_id": "88"},
            {**api_row(), "user_id": None},
            {**api_row(), "submission_id": True},
        ]:
            self.server.body = [row]
            with self.subTest(row=list(row)), self.assertRaises(ValueError):
                self.sync.sync_once()
            self.assertEqual(self.repo.records(), [])
            self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_permissions_failure_preserves_committed_checkpoint(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        prior = self.repo.checkpoint_state(self.source.scope)
        for status in [401, 403]:
            self.server.response_status = status
            self.server.body = {"error": "SENSITIVE_API_BODY"}
            with self.assertRaises(PermissionError) as error:
                self.sync.sync_once()
            self.assertNotIn("SENSITIVE", str(error.exception))
            self.assertEqual(self.repo.checkpoint_state(self.source.scope), prior)
        self.assertEqual(len(self.repo.records()), 1)

    def test_http_json_shape_pagination_and_redirect_failures_do_not_advance(self):
        cases = [
            (500, b"private error body", {}),
            (200, b"{", {}),
            (200, {}, {}),
            (200, [], {"Link": "<https://example.invalid/next>; rel=next"}),
            (302, [], {"Location": "https://example.invalid/redirect"}),
        ]
        for status, body, headers in cases:
            self.server.response_status, self.server.body, self.server.extra_headers = (
                status,
                body,
                headers,
            )
            with self.subTest(status=status), self.assertRaises(APIReadError):
                self.sync.sync_once()
            self.assertEqual(self.repo.records(), [])
            self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_transport_failure_is_sanitized(self):
        with patch(
            "urllib.request.OpenerDirector.open", side_effect=TimeoutError("SENSITIVE_API_BODY")
        ):
            with self.assertRaises(APIReadError) as error:
                self.sync.sync_once()
        self.assertNotIn("SENSITIVE", str(error.exception))
        self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_bad_later_row_and_score_mismatch_are_atomic(self):
        for second in [{**api_row("13"), "score": 0.5}, api_row("13", score=1)]:
            self.server.body = [api_row(), second]
            with self.assertRaises(ValueError):
                self.sync.sync_once()
            self.assertEqual(self.repo.records(), [])
            self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_changed_existing_submission_requires_reconciliation_not_silent_regrade(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        prior = self.repo.checkpoint_state(self.source.scope)
        self.server.body = [api_row(sql=GOOD, score=1)]
        with self.assertRaises(ValueError):
            self.sync.sync_once()
        self.assertEqual(self.repo.records()[0]["grading"]["score"], 0)
        self.assertEqual(self.repo.checkpoint_state(self.source.scope), prior)

    def test_checkpoint_failure_rolls_back_attempt_inserts(self):
        with closing(self.repo.connect()) as db:
            db.executescript(
                "CREATE TRIGGER reject_checkpoint BEFORE INSERT ON sync_checkpoints BEGIN SELECT RAISE(ABORT,'synthetic failure'); END;"
            )
        self.server.body = [api_row()]
        with self.assertRaises(sqlite3.IntegrityError):
            self.sync.sync_once()
        self.assertEqual(self.repo.records(), [])
        self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_checkpoint_compare_and_set_rejects_stale_poll(self):
        self.server.body = [api_row()]
        original = self.repo.process_many

        def raced(*args, **kwargs):
            with closing(self.repo.connect()) as db:
                db.execute(
                    "INSERT INTO sync_checkpoints VALUES(?,?)",
                    (self.source.scope, json.dumps({"other_poll": True})),
                )
                db.commit()
            return original(*args, **kwargs)

        with patch.object(self.repo, "process_many", side_effect=raced):
            with self.assertRaisesRegex(ValueError, "checkpoint changed"):
                self.sync.sync_once()
        self.assertEqual(self.repo.records(), [])
        self.assertEqual(self.repo.checkpoint_state(self.source.scope), {"other_poll": True})

    def test_concurrent_same_snapshot_does_not_duplicate(self):
        self.server.body = [api_row()]

        def poll(_):
            try:
                return self.sync.sync_once()["inserted_count"]
            except ValueError as exc:
                if "checkpoint changed" not in str(exc):
                    raise
                return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(poll, range(2))), 1)
        self.assertEqual(len(self.repo.records()), 1)

    def test_empty_snapshot_does_not_delete_local_history(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        self.server.body = []
        self.assertEqual(self.sync.sync_once()["inserted_count"], 0)
        self.assertEqual(len(self.repo.records()), 1)

    def test_restart_retains_checkpoint_and_attempts(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        other = SubmissionRepository(self.repo.path)
        self.assertEqual(
            other.checkpoint_state(self.source.scope), self.repo.checkpoint_state(self.source.scope)
        )
        self.assertEqual(
            SubmissionSynchronizer(other, self.source).sync_once()["inserted_count"], 0
        )

    def test_scope_namespaces_ids_across_course_instances(self):
        self.server.body = [api_row()]
        self.sync.sync_once()
        other = AuthorizedPrairieLearnAPISource(
            f"http://127.0.0.1:{self.server.server_port}",
            "synthetic-contract",
            5001,
            9000,
            {"101": "S001"},
            authorized=True,
            assessment_id=7000,
        )
        self.assertEqual(SubmissionSynchronizer(self.repo, other).sync_once()["inserted_count"], 1)
        self.assertEqual(len({r["attempt_id"] for r in self.repo.records()}), 2)

    def test_csv_api_overlap_requires_explicit_scope_alias(self):
        old = {
            **attempt("local-pl-12"),
            "source": "local_prairielearn_export",
            "assessment_id": "sql-sandbox",
            "external_links": {
                "submission_id": "12",
                "assessment_instance_number": "1",
                "variant_number": "1",
            },
            "external_score": 0,
        }
        self.repo.process(old)
        self.server.body = [api_row()]
        with self.assertRaisesRegex(ValueError, "Ambiguous CSV/API overlap"):
            self.sync.sync_once()
        sync = SubmissionSynchronizer(
            self.repo, self.source, legacy_attempt_ids={"12": "local-pl-12"}
        )
        result = sync.sync_once()
        self.assertEqual((result["inserted_count"], result["reconciled_csv_count"]), (0, 1))
        self.assertEqual(len(self.repo.records()), 1)
        self.assertEqual(self.repo.records()[0]["source"], "local_prairielearn_export")

    def test_wrong_csv_alias_cannot_cross_subjects(self):
        self.repo.process(
            {
                **attempt("legacy", sid="S002"),
                "source": "local_prairielearn_export",
                "external_score": 0,
                "external_links": {"submission_id": "12"},
            }
        )
        self.server.body = [api_row()]
        with self.assertRaises(PermissionError):
            SubmissionSynchronizer(
                self.repo, self.source, legacy_attempt_ids={"12": "legacy"}
            ).sync_once()
        self.assertIsNone(self.repo.checkpoint_state(self.source.scope))

    def test_authorization_and_completed_scope_required(self):
        with self.assertRaises(PermissionError):
            AuthorizedPrairieLearnAPISource("http://localhost:3000", "", 1, 1, {})
        self.source.assessment_id = None
        with self.assertRaises(ValueError):
            SubmissionSynchronizer(self.repo, self.source)


class LocalBackendTests(unittest.TestCase):
    def test_local_extraction_backends_need_no_paid_credential(self):
        for provider in ["local", "hf", "huggingface", "vllm", "hf_legacy"]:
            plan = backend_environment(
                {"LLM_PROVIDER": provider, "SIIP_EXTRACTION_MODEL": "synthetic-model"},
                authorized_model_usage=True,
            )
            self.assertNotIn("OPENAI_API_KEY", plan)
            self.assertNotIn("ANTHROPIC_API_KEY", plan)
            self.assertEqual(plan["HF_TRUST_REMOTE_CODE"], "0")

    def test_local_compatible_extraction_has_placeholder_not_paid_key(self):
        plan = backend_environment(
            {
                "LLM_PROVIDER": "openai",
                "SIIP_EXTRACTION_MODEL": "synthetic-model",
                "OPENAI_BASE_URL": "http://host.docker.internal:11434/v1",
            },
            authorized_model_usage=True,
        )
        self.assertEqual(plan["OPENAI_API_KEY"], "local-placeholder")

    def test_remote_extraction_requires_consent_and_authorization(self):
        env = {"LLM_PROVIDER": "openai", "SIIP_EXTRACTION_MODEL": "synthetic-model"}
        with self.assertRaises(PermissionError):
            backend_environment(env)
        with self.assertRaises(PermissionError):
            backend_environment(env, authorized_model_usage=True)
        for endpoint in ["http://example.invalid/v1", "http://username:password@localhost/v1"]:
            with self.assertRaises(ValueError):
                backend_environment(
                    {**env, "OPENAI_BASE_URL": endpoint}, authorized_model_usage=True
                )

    def test_compatible_wire_supports_model_identifier_json_mode_and_limits(self):
        captured = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self, size):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "feedback_text": "Consider preservation of unmatched rows.",
                                            "candidate_concepts": [],
                                            "evidence_references": [],
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode()

        def send(req, timeout):
            captured.append(json.loads(req.data))
            return Response()

        result = grade(QID, BAD)
        provider = CompatibleProvider(
            "http://localhost:11434/v1", "synthetic-local-model", max_tokens=350
        )
        with patch("urllib.request.OpenerDirector.open", side_effect=send):
            feedback = generate_feedback(QID, BAD, result, provider=provider)
        self.assertEqual(captured[0]["model"], "synthetic-local-model")
        self.assertEqual(captured[0]["response_format"], {"type": "json_object"})
        self.assertEqual(captured[0]["max_tokens"], 350)
        self.assertEqual(feedback["inference_status"], "live_success")  # mocked transport only
        self.assertEqual(result["score"], 0)

    def test_metadata_probe_is_get_only_and_not_inference(self):
        spec = importlib.util.spec_from_file_location(
            "local_model_probe", ROOT / "scripts/check_local_model.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self, size):
                return b'{"data":[{"id":"synthetic-local-model"}]}'

        requests = []

        def send(req, timeout):
            requests.append(req)
            return Response()

        config = ProviderConfig(
            provider="local", base_url="http://localhost:11434/v1", model="synthetic-local-model"
        )
        with patch("urllib.request.OpenerDirector.open", side_effect=send):
            report = module.probe_models(config)
        self.assertEqual(report, {"status": "model_listed", "inference_verified": False})
        self.assertEqual(requests[0].get_method(), "GET")
        self.assertTrue(requests[0].full_url.endswith("/v1/models"))
        self.assertIsNone(requests[0].data)


class ShutdownContractTests(unittest.TestCase):
    def run_isolated_stop(self, ready, running=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "scripts").mkdir()
            (root / "artifacts").mkdir()
            binary = root / "bin"
            binary.mkdir()
            shutil.copyfile(ROOT / "scripts/manage.py", root / "scripts/manage.py")
            fake = binary / "docker"
            fake.write_text(
                "#!" + sys.executable + "\n"
                "import json,os,sys\n"
                "args=sys.argv[1:]\n"
                "with open(os.environ['SIIP_STOP_TEST_LOG'],'a') as stream: stream.write(json.dumps(args)+'\\n')\n"
                "if 'ps' in args: print('owned-synthetic-container' if os.environ['SIIP_STOP_TEST_RUNNING']=='1' else '')\n"
                "if 'pg_isready' in args: sys.exit(int(os.environ['SIIP_STOP_TEST_READY']))\n"
            )
            fake.chmod(0o755)
            log = root / "commands.jsonl"
            subprocess.run(
                [sys.executable, str(root / "scripts/manage.py"), "stop"],
                cwd=root,
                check=True,
                env={
                    **os.environ,
                    "PATH": str(binary) + os.pathsep + os.environ.get("PATH", ""),
                    "SIIP_STOP_TEST_LOG": str(log),
                    "SIIP_STOP_TEST_READY": str(ready),
                    "SIIP_STOP_TEST_RUNNING": "1" if running else "0",
                },
                capture_output=True,
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertTrue(all(str(root / "infrastructure/compose.yaml") in row for row in calls))
            return calls

    def test_ready_bundled_postgres_stops_before_container(self):
        calls = self.run_isolated_stop(0)
        graceful = next(
            i for i, row in enumerate(calls) if "/PrairieLearn/scripts/start_postgres.sh" in row
        )
        final = next(i for i, row in enumerate(calls) if row[-1] == "stop" and "exec" not in row)
        self.assertLess(graceful, final)
        self.assertFalse(any("-v" in row or "down" in row for row in calls))

    def test_absent_or_unready_postgres_never_runs_graceful_stop(self):
        for running in [False, True]:
            calls = self.run_isolated_stop(1, running)
            self.assertFalse(any("/PrairieLearn/scripts/start_postgres.sh" in row for row in calls))
            self.assertEqual(calls[-1][-1], "stop")


if __name__ == "__main__":
    unittest.main()
