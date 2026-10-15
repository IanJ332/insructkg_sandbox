import os
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.jobs import FeedbackJobRepository, FeedbackWorker, JobQueueFullError
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

        # Re-enqueuing the same attempt_id must return the existing job (idempotent)
        job2 = self.repo.enqueue("att-001", "S001", "sql_join_02", "SELECT 1;", grading, mode="kg")
        self.assertEqual(job1.job_id, job2.job_id)
        self.assertEqual(self.repo.stats()["pending"], 1)

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

        claimed2 = self.repo.claim("worker-B")
        self.assertIsNotNone(claimed2)
        self.assertEqual(claimed2.attempt_id, "att-second")

        # No more pending jobs
        self.assertIsNone(self.repo.claim("worker-A"))

    def test_claim_lease_recovery(self):
        grading = {"status": "ok", "score": 1}
        self.repo.enqueue("att-stale", "S001", "sql_join_01", "SELECT 1;", grading)
        job = self.repo.claim("worker-dead", lease_seconds=0.01)
        self.assertIsNotNone(job)

        # Immediately claiming with 60s lease returns None (job still within lease)
        self.assertIsNone(self.repo.claim("worker-alive", lease_seconds=60.0))

        # Manually backdate started_at to simulate expired lease
        with closing(self.repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET started_at = '2026-01-01T00:00:00Z' WHERE job_id = ?",
                (job.job_id,),
            )
            db.commit()

        # Expired lease is recovered by new worker
        recovered = self.repo.claim("worker-alive", lease_seconds=60.0)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.job_id, job.job_id)

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
        failed1 = self.repo.fail(claimed1.job_id, "Temporary timeout")
        self.assertEqual(failed1.status, "pending")
        self.assertEqual(failed1.retries, 1)

        # Second claim and failure -> reaches max_retries=2 -> marked failed
        claimed2 = self.repo.claim("worker-1")
        failed2 = self.repo.fail(claimed2.job_id, "Fatal model failure")
        self.assertEqual(failed2.status, "failed")
        self.assertEqual(failed2.retries, 2)
        self.assertIn("Fatal model failure", failed2.error)

    def test_student_authorization_boundary(self):
        grading = {"status": "ok", "score": 1}
        job = self.repo.enqueue("att-auth", "S001", "sql_join_01", "SELECT 1;", grading)

        # Authorized student can retrieve
        self.assertIsNotNone(self.repo.get_for_student(job.job_id, "S001"))

        # Different student is denied (returns None, zero existence leakage)
        self.assertIsNone(self.repo.get_for_student(job.job_id, "S002"))


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

    def test_pl_bridge_async_decoupling(self):
        data = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
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

        # 3. Job was enqueued in the feedback job queue
        job_id = data["feedback"]["siip"]["job_id"]
        self.assertIsNotNone(job_id)

        repo = FeedbackJobRepository(self.db_path)
        job = repo.get(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.question_id, "sql_join_02")


if __name__ == "__main__":
    unittest.main()
