import os
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.jobs import (
    AttemptConflictError,
    FeedbackJobRepository,
    FeedbackWorker,
    JobQueueFullError,
    StaleLeaseError,
    UnauthorizedJobAccessError,
)
from siip.pl_bridge import grade_question


class TestFeedbackJobRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_jobs.sqlite3"
        self.repo = FeedbackJobRepository(self.db_path, max_queue_size=5)

    def tearDown(self):
        self.tmp.cleanup()

    def test_enqueue_and_idempotence(self):
        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        job1 = self.repo.enqueue("att-001", "S001", "sql_join_02", "SELECT 1;", grading, mode="kg")
        self.assertEqual(job1.status, "pending")
        self.assertEqual(job1.attempt_id, "att-001")
        self.assertEqual(job1.retries, 0)

        # Re-enqueuing the same attempt_id with identical payload must return the existing job (idempotent)
        job2 = self.repo.enqueue("att-001", "S001", "sql_join_02", "SELECT 1;", grading, mode="kg")
        self.assertEqual(job1.job_id, job2.job_id)
        self.assertEqual(self.repo.stats()["pending"], 1)

    def test_conflicting_payload_rejected_for_duplicate_attempt(self):
        grading = {"status": "ok", "score": 1, "observation": "correct"}
        self.repo.enqueue("att-conflict-01", "S001", "sql_join_01", "SELECT 1;", grading)

        # Different SQL for same attempt_id must raise AttemptConflictError
        with self.assertRaises(AttemptConflictError):
            self.repo.enqueue("att-conflict-01", "S001", "sql_join_01", "SELECT 2;", grading)

        # Different student for same attempt_id must raise AttemptConflictError
        with self.assertRaises(AttemptConflictError):
            self.repo.enqueue("att-conflict-01", "S002", "sql_join_01", "SELECT 1;", grading)

    def test_queue_capacity_bound(self):
        grading = {"status": "ok", "score": 1}
        for i in range(5):
            self.repo.enqueue(f"att-{i}", "S001", "sql_join_01", "SELECT 1;", grading)

        # 6th job exceeds capacity of 5
        with self.assertRaises(JobQueueFullError):
            self.repo.enqueue("att-overflow", "S001", "sql_join_01", "SELECT 1;", grading)

    def test_claim_fifo_order(self):
        grading = {"status": "ok", "score": 1}
        self.repo.enqueue("att-first", "S001", "sql_join_01", "SELECT 1;", grading)
        self.repo.enqueue("att-second", "S001", "sql_join_02", "SELECT 2;", grading)

        claimed1 = self.repo.claim("worker-A")
        self.assertIsNotNone(claimed1)
        self.assertEqual(claimed1.attempt_id, "att-first")
        self.assertEqual(claimed1.status, "processing")
        self.assertIsNotNone(claimed1.lease_token)

        claimed2 = self.repo.claim("worker-B")
        self.assertIsNotNone(claimed2)
        self.assertEqual(claimed2.attempt_id, "att-second")

        # No more pending jobs
        self.assertIsNone(self.repo.claim("worker-A"))

    def test_claim_lease_recovery(self):
        grading = {"status": "ok", "score": 1}
        self.repo.enqueue("att-stale", "S001", "sql_join_01", "SELECT 1;", grading)
        job = self.repo.claim("worker-dead", lease_seconds=10.0)
        self.assertIsNotNone(job)

        # Immediately claiming with 60s lease returns None (job still within 10s lease)
        self.assertIsNone(self.repo.claim("worker-alive", lease_seconds=60.0))

        # Manually backdate lease_expires_at to simulate expired lease
        with closing(self.repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET lease_expires_at = '2026-01-01T00:00:00Z' WHERE job_id = ?",
                (job.job_id,),
            )
            db.commit()

        # Expired lease is recovered by new worker
        recovered = self.repo.claim("worker-alive", lease_seconds=60.0)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.job_id, job.job_id)
        self.assertNotEqual(recovered.lease_token, job.lease_token)

    def test_fencing_token_rejects_stale_worker_complete(self):
        grading = {"status": "ok", "score": 1}
        self.repo.enqueue("att-fence", "S001", "sql_join_01", "SELECT 1;", grading)

        # Worker A claims job
        worker_a_job = self.repo.claim("worker-A", lease_seconds=0.01)
        self.assertIsNotNone(worker_a_job)

        # Simulate Worker A slow/hung; lease expires
        with closing(self.repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET lease_expires_at = '2026-01-01T00:00:00Z' WHERE job_id = ?",
                (worker_a_job.job_id,),
            )
            db.commit()

        # Worker B re-claims the job with a new lease token
        worker_b_job = self.repo.claim("worker-B", lease_seconds=60.0)
        self.assertIsNotNone(worker_b_job)
        self.assertNotEqual(worker_a_job.lease_token, worker_b_job.lease_token)

        # Worker A wakes up and attempts to complete with its stale lease token -> must be rejected
        with self.assertRaises(StaleLeaseError):
            self.repo.complete(
                job_id=worker_a_job.job_id,
                result={"feedback_text": "Stale result from Worker A"},
                latency_ms=9000.0,
                model_identifier="qwen3:8b",
                prompt_version="v1",
                graph_version="v1",
                lease_token=worker_a_job.lease_token,
            )

        # Worker B completes validly
        completed_b = self.repo.complete(
            job_id=worker_b_job.job_id,
            result={"feedback_text": "Valid result from Worker B"},
            latency_ms=2500.0,
            model_identifier="qwen3:8b",
            prompt_version="v1",
            graph_version="v1",
            lease_token=worker_b_job.lease_token,
        )
        self.assertEqual(completed_b.status, "completed")
        self.assertEqual(completed_b.result["feedback_text"], "Valid result from Worker B")

    def test_complete_records_provenance(self):
        grading = {"status": "ok", "score": 1}
        self.repo.enqueue("att-comp", "S001", "sql_join_01", "SELECT 1;", grading)
        claimed = self.repo.claim("worker-1")

        result_payload = {"feedback_text": "Great job!", "candidate_concepts": []}
        completed = self.repo.complete(
            job_id=claimed.job_id,
            result=result_payload,
            latency_ms=125.5,
            model_identifier="qwen3:8b",
            prompt_version="siip-feedback-v3",
            graph_version="c34a7786",
            lease_token=claimed.lease_token,
        )
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.latency_ms, 125.5)
        self.assertEqual(completed.model_identifier, "qwen3:8b")
        self.assertEqual(completed.result["feedback_text"], "Great job!")

    def test_retry_and_max_retries_failure(self):
        grading = {"status": "error", "score": 0}
        self.repo.enqueue("att-fail", "S001", "sql_join_01", "SELECT 1;", grading, max_retries=2)

        # First failure -> returns to pending for retry
        claimed1 = self.repo.claim("worker-1")
        failed1 = self.repo.fail(
            claimed1.job_id, "Temporary timeout", lease_token=claimed1.lease_token
        )
        self.assertEqual(failed1.status, "pending")
        self.assertEqual(failed1.retries, 1)

        # Second claim and failure -> reaches max_retries=2 -> marked failed
        claimed2 = self.repo.claim("worker-1")
        failed2 = self.repo.fail(
            claimed2.job_id, "Fatal model failure", lease_token=claimed2.lease_token
        )
        self.assertEqual(failed2.status, "failed")
        self.assertEqual(failed2.retries, 2)
        self.assertIn("Fatal model failure", failed2.error)

    def test_student_authorization_boundary(self):
        grading = {"status": "ok", "score": 1}
        job = self.repo.enqueue("att-auth", "S001", "sql_join_01", "SELECT 1;", grading)

        # Authorized student can retrieve
        self.assertIsNotNone(self.repo.get_for_student(job.job_id, "S001"))

        # Different student raises UnauthorizedJobAccessError (zero cross-student leakage)
        with self.assertRaises(UnauthorizedJobAccessError):
            self.repo.get_for_student(job.job_id, "S002")

    def test_data_minimization_excludes_hidden_expected_rows(self):
        # Pass a comprehensive grading dict containing hidden test outputs
        full_grading = {
            "status": "semantic_error",
            "score": 0,
            "observation": "missing_unmatched_rows",
            "datasets": [{"dataset": "A", "expected": {"rows": [[1, "Secret Employee", 10]]}}],
            "reference_sql": "SELECT * FROM HiddenTable;",
        }
        job = self.repo.enqueue("att-leak-test", "S001", "sql_join_02", "SELECT 1;", full_grading)

        # Inspect raw SQLite database row
        with closing(self.repo.connect()) as db:
            raw_grading_json = db.execute(
                "SELECT grading FROM feedback_jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()[0]

        # Invariant: hidden expected rows, dataset lists, and reference SQL must NOT be in the DB
        self.assertNotIn("Secret Employee", raw_grading_json)
        self.assertNotIn("HiddenTable", raw_grading_json)
        self.assertNotIn("datasets", raw_grading_json)
        self.assertIn("missing_unmatched_rows", raw_grading_json)

    def test_cleanup_retention(self):
        grading = {"status": "ok", "score": 1}
        job = self.repo.enqueue("att-clean", "S001", "sql_join_01", "SELECT 1;", grading)
        claimed = self.repo.claim("worker-1")
        self.repo.complete(
            claimed.job_id, {"feedback_text": "done"}, 10.0, "m1", "p1", "g1", claimed.lease_token
        )

        # Manually backdate completed_at to 2 days ago
        with closing(self.repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET completed_at = '2026-01-01T00:00:00Z' WHERE job_id = ?",
                (claimed.job_id,),
            )
            db.commit()

        # Clean up jobs older than 1 day
        deleted = self.repo.cleanup(retention_seconds=86400)
        self.assertEqual(deleted, 1)
        self.assertIsNone(self.repo.get(job.job_id))


class TestFeedbackWorker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "worker_jobs.sqlite3"
        self.repo = FeedbackJobRepository(self.db_path)
        self.worker = FeedbackWorker(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_worker_process_one_and_drain(self):
        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        self.repo.enqueue(
            "job-1",
            "S001",
            "sql_join_02",
            "SELECT e.name FROM Employees e;",
            grading,
            mode="baseline",
        )
        self.repo.enqueue(
            "job-2",
            "S002",
            "sql_join_01",
            "SELECT e.name FROM Employees e;",
            grading,
            mode="baseline",
        )

        # Process one
        job = self.worker.process_one()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.attempt_id, "job-1")

        # Drain remaining
        drained = self.worker.drain()
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0].attempt_id, "job-2")
        self.assertEqual(self.repo.stats().get("pending", 0), 0)


class TestPrairieLearnBridgeDecoupling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "pl_jobs.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_pl_bridge_async_decoupling_with_trusted_identity(self):
        data = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "partial_scores": {},
            "feedback": {},
        }
        env = {
            "SIIP_ASYNC_FEEDBACK": "1",
            "SIIP_FEEDBACK_JOBS_DB": str(self.db_path),
            "SIIP_FEEDBACK_PROVIDER": "local",
        }
        with patch.dict(os.environ, env):
            grade_question(data, "sql_join_02")

        # 1. Deterministic grading completed immediately
        self.assertIn("score", data)
        self.assertEqual(data["score"], 0.0)

        # 2. Immediate feedback is provided to student without waiting
        self.assertIn("feedback", data)
        self.assertEqual(data["feedback"]["siip"]["feedback_origin"], "prairielearn_hook_immediate")

        # 3. Job was enqueued in the feedback job queue for S001
        job_id = data["feedback"]["siip"]["job_id"]
        self.assertIsNotNone(job_id)
        self.assertEqual(data["feedback"]["siip"]["student_id"], "S001")

        repo = FeedbackJobRepository(self.db_path)
        job = repo.get(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.student_id, "S001")
        self.assertEqual(job.question_id, "sql_join_02")

    def test_pl_bridge_fails_closed_when_identity_missing(self):
        # No user identity passed in data
        data = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {},
            "partial_scores": {},
            "feedback": {},
        }
        env = {
            "SIIP_ASYNC_FEEDBACK": "1",
            "SIIP_FEEDBACK_JOBS_DB": str(self.db_path),
            "SIIP_FEEDBACK_PROVIDER": "local",
        }
        with patch.dict(os.environ, env):
            grade_question(data, "sql_join_02")

        # Grading succeeds deterministically
        self.assertEqual(data["score"], 0.0)
        # Fails closed for personalization: non-personalized baseline returned, NO personalized job queued
        self.assertIsNone(data["feedback"]["siip"]["job_id"])
        self.assertIsNone(data["feedback"]["siip"]["student_id"])
        self.assertIn(
            "non_personalized",
            data["feedback"]["siip"]["personalization_status"],
        )


if __name__ == "__main__":
    unittest.main()
