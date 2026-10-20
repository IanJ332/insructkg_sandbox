"""Focused multi-user concurrency, failure injection, and end-to-end lifecycle tests.

Verifies:
1. Two distinct students submitting concurrently with strict authorization isolation.
2. Five simultaneous submissions.
3. Ten simultaneous submissions.
4. Same-student rapid retries (idempotency).
5. Duplicate event delivery.
6. Worker crash, lease recovery, and worker restart.
7. Local Ollama unavailable (graceful failure, score invariance).
8. Feedback timeout handling.
9. Queue saturation (JobQueueFullError).
10. Database restart (state persistence).
11. Cross-student retrieval forbidden (403 Forbidden).
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.jobs import (
    FeedbackJobRepository,
    FeedbackWorker,
    JobQueueFullError,
    StaleLeaseError,
    UnauthorizedJobAccessError,
)
from siip.pl_bridge import grade_question


class TestAsyncMultiUserAndFailureLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "lifecycle_jobs.sqlite3"
        self.repo = FeedbackJobRepository(self.db_path, max_queue_size=20)
        self.worker = FeedbackWorker(self.repo, worker_id="worker-test-1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_distinct_students_concurrently(self):
        """Two distinct students submit concurrently; both are isolated and authorized correctly."""
        results = {}

        def submit(student_id, attempt_id, sql):
            grading = {
                "status": "semantic_error",
                "score": 0,
                "observation": "missing_unmatched_rows",
            }
            job = self.repo.enqueue(
                attempt_id, student_id, "sql_join_02", sql, grading, mode="baseline"
            )
            results[student_id] = job

        t1 = threading.Thread(target=submit, args=("S001", "att-s1-1", "SELECT 1;"))
        t2 = threading.Thread(target=submit, args=("S002", "att-s2-1", "SELECT 2;"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertIn("S001", results)
        self.assertIn("S002", results)
        job1 = results["S001"]
        job2 = results["S002"]

        # Different job IDs and student IDs
        self.assertNotEqual(job1.job_id, job2.job_id)
        self.assertEqual(job1.student_id, "S001")
        self.assertEqual(job2.student_id, "S002")

        # Worker processes both
        drained = self.worker.drain()
        self.assertEqual(len(drained), 2)

        # Cross-student authorization check
        # S001 can retrieve job1, but NOT job2
        self.assertIsNotNone(self.repo.get_for_student(job1.job_id, "S001"))
        with self.assertRaises(UnauthorizedJobAccessError):
            self.repo.get_for_student(job2.job_id, "S001")

        # S002 can retrieve job2, but NOT job1
        self.assertIsNotNone(self.repo.get_for_student(job2.job_id, "S002"))
        with self.assertRaises(UnauthorizedJobAccessError):
            self.repo.get_for_student(job1.job_id, "S002")

    def test_five_simultaneous_submissions(self):
        """Five simultaneous submissions across threads execute without lock contention or collision."""
        students = [f"S00{i}" for i in range(1, 6)]
        grading = {"status": "ok", "score": 1, "observation": "correct"}

        def submit(sid):
            return self.repo.enqueue(f"att-5sim-{sid}", sid, "sql_join_01", "SELECT 1;", grading)

        with ThreadPoolExecutor(max_workers=5) as pool:
            jobs = list(pool.map(submit, students))

        self.assertEqual(len(jobs), 5)
        job_ids = {j.job_id for j in jobs}
        self.assertEqual(len(job_ids), 5)  # All distinct

        # Worker drains all 5
        drained = self.worker.drain()
        self.assertEqual(len(drained), 5)
        for j in drained:
            self.assertEqual(j.status, "completed")

    def test_ten_simultaneous_submissions(self):
        """Ten simultaneous submissions execute within bounded queue capacity."""
        grading = {"status": "ok", "score": 1, "observation": "correct"}

        def submit(idx):
            sid = f"S{idx % 5 + 1:03d}"
            return self.repo.enqueue(
                f"att-10sim-{idx}", sid, "sql_join_01", f"SELECT {idx};", grading
            )

        with ThreadPoolExecutor(max_workers=10) as pool:
            jobs = list(pool.map(submit, range(10)))

        self.assertEqual(len(jobs), 10)
        self.assertEqual(len({j.job_id for j in jobs}), 10)

        drained = self.worker.drain()
        self.assertEqual(len(drained), 10)
        self.assertEqual(self.repo.stats().get("completed", 0), 10)

    def test_same_student_rapid_retries_idempotent(self):
        """Rapid identical retries from the same student produce an idempotent single job."""
        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        sql = "SELECT * FROM Employees e;"

        job1 = self.repo.enqueue("att-rapid-1", "S001", "sql_join_02", sql, grading)
        job2 = self.repo.enqueue("att-rapid-1", "S001", "sql_join_02", sql, grading)
        job3 = self.repo.enqueue("att-rapid-1", "S001", "sql_join_02", sql, grading)

        self.assertEqual(job1.job_id, job2.job_id)
        self.assertEqual(job2.job_id, job3.job_id)
        self.assertEqual(self.repo.stats()["pending"], 1)

    def test_duplicate_event_delivery(self):
        """Duplicate event delivery returns identical job without creating duplicate records."""
        grading = {"status": "ok", "score": 1, "observation": "correct"}
        job1 = self.repo.enqueue("att-dup-event", "S003", "sql_join_01", "SELECT 1;", grading)

        # Worker processes the job to completion
        self.worker.process_one()
        completed = self.repo.get(job1.job_id)
        self.assertEqual(completed.status, "completed")

        # Duplicate event arrives with same attempt_id
        job2 = self.repo.enqueue("att-dup-event", "S003", "sql_join_01", "SELECT 1;", grading)
        self.assertEqual(job2.job_id, job1.job_id)
        self.assertEqual(job2.status, "completed")  # Still completed, not reset to pending

    def test_worker_crash_and_restart_recovery(self):
        """Worker 1 crashes holding a lease; Worker 2 recovers the job after lease expiry."""
        grading = {"status": "ok", "score": 1}
        job = self.repo.enqueue("att-crash-test", "S001", "sql_join_01", "SELECT 1;", grading)

        # Worker 1 claims with lease
        worker1 = FeedbackWorker(self.repo, worker_id="worker-crash-1")
        claimed1 = self.repo.claim(worker1.worker_id, lease_seconds=10.0)
        self.assertIsNotNone(claimed1)
        self.assertEqual(claimed1.status, "processing")

        # Worker 1 "crashes" (stops executing). Simulate lease expiry:
        with closing(self.repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET lease_expires_at = '2026-01-01T00:00:00Z' WHERE job_id = ?",
                (job.job_id,),
            )
            db.commit()

        # Worker 2 starts up after restart
        worker2 = FeedbackWorker(self.repo, worker_id="worker-restart-2")
        recovered_job = worker2.process_one()
        self.assertIsNotNone(recovered_job)
        self.assertEqual(recovered_job.job_id, job.job_id)
        self.assertEqual(recovered_job.status, "completed")

        # If Worker 1 wakes up and tries to complete, it must be rejected (StaleLeaseError)
        with self.assertRaises(StaleLeaseError):
            self.repo.complete(
                job.job_id,
                {"feedback_text": "Zombie worker result"},
                100.0,
                "m1",
                "p1",
                "g1",
                lease_token=claimed1.lease_token,
            )

    def test_local_ollama_unavailable_score_invariant(self):
        """When Ollama is unavailable, deterministic score is completely unaffected."""
        data = {
            "submitted_answers": {"sql": "SELECT name FROM Employees;"},
            "options": {"user": {"user_id": 101, "uid": "student@example.com"}},
            "partial_scores": {},
            "feedback": {},
        }
        # Simulate connection failure to LLM
        env = {
            "SIIP_ASYNC_FEEDBACK": "1",
            "SIIP_FEEDBACK_JOBS_DB": str(self.db_path),
            "SIIP_FEEDBACK_PROVIDER": "local",
            "SIIP_LLM_BASE_URL": "http://127.0.0.1:99999/v1",  # Invalid unreachable port
        }
        with patch.dict(os.environ, env):
            grade_question(data, "sql_join_02")

        # Deterministic grading succeeded completely
        self.assertEqual(data["score"], 0.0)
        self.assertIn("score", data)
        self.assertEqual(data["feedback"]["status"], "semantic_error")

        # Worker attempts to process job with failing provider
        mock_failing_provider = MagicMock()
        mock_failing_provider.generate.side_effect = ConnectionRefusedError("Ollama offline")

        job = self.worker.process_one(provider=mock_failing_provider)
        self.assertIsNotNone(job)
        # First attempt: job returns to pending for retry
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.retries, 1)

    def test_feedback_timeout_handling(self):
        """TimeoutError during inference increments retries and records error cleanly."""
        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        self.repo.enqueue("att-timeout", "S001", "sql_join_02", "SELECT 1;", grading, max_retries=1)

        mock_timeout_provider = MagicMock()
        mock_timeout_provider.generate.side_effect = TimeoutError("Request timed out after 60s")

        job = self.worker.process_one(provider=mock_timeout_provider)
        self.assertIsNotNone(job)
        # Reached max_retries=1 -> marked failed
        self.assertEqual(job.status, "failed")
        self.assertIn("TimeoutError", job.error)

    def test_queue_saturation_raises_bounded_error(self):
        """Enqueuing beyond max_queue_size raises JobQueueFullError and does not corrupt the DB."""
        small_repo = FeedbackJobRepository(Path(self.tmp.name) / "small.sqlite3", max_queue_size=3)
        grading = {"status": "ok", "score": 1}

        for i in range(3):
            small_repo.enqueue(f"att-{i}", "S001", "sql_join_01", "SELECT 1;", grading)

        with self.assertRaises(JobQueueFullError):
            small_repo.enqueue("att-exceed", "S001", "sql_join_01", "SELECT 1;", grading)

        # Database remains healthy
        self.assertEqual(small_repo.stats()["pending"], 3)

    def test_database_restart_preserves_state(self):
        """Closing and reopening repository (simulating service restart) preserves all state."""
        grading = {"status": "ok", "score": 1}
        job = self.repo.enqueue("att-persist", "S001", "sql_join_01", "SELECT 1;", grading)

        # Process to completion
        self.worker.process_one()

        # Simulate service restart: create fresh repository instance on same database file
        restarted_repo = FeedbackJobRepository(self.db_path)
        persisted_job = restarted_repo.get(job.job_id)
        self.assertIsNotNone(persisted_job)
        self.assertEqual(persisted_job.status, "completed")
        self.assertEqual(persisted_job.attempt_id, "att-persist")
        self.assertEqual(persisted_job.student_id, "S001")


if __name__ == "__main__":
    unittest.main()
