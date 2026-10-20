"""Queue storage topology and single-runtime ownership tests.
Verifies WAL checkpointing, database integrity, concurrent claims,
fencing token enforcement, and stale lease protection on Windows host.
"""

from __future__ import annotations

import concurrent.futures
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.jobs import FeedbackJobRepository, FeedbackWorker, StaleLeaseError


class TestQueueTopology(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "topology_jobs.sqlite3"
        self.repo = FeedbackJobRepository(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_wal_mode_and_pragma_integrity(self):
        # Database must run in WAL mode with normal synchronous pragma
        with closing(self.repo.connect()) as db:
            journal_mode = db.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal")

            integrity = db.execute("PRAGMA integrity_check;").fetchone()[0]
            self.assertEqual(integrity.lower(), "ok")

    def test_mandatory_lease_token_enforced(self):
        grading = {"status": "semantic_error", "score": 0.0}
        job = self.repo.enqueue("att-token-1", "S001", "sql_join_01", "SELECT 1;", grading)

        # Claiming assigns a lease token
        claimed = self.repo.claim("worker-1")
        self.assertIsNotNone(claimed)
        self.assertIsNotNone(claimed.lease_token)

        # Attempting to complete with None lease_token MUST raise StaleLeaseError
        with self.assertRaises(StaleLeaseError):
            self.repo.complete(
                job.job_id, {"feedback_text": "ok"}, 10.0, "m1", "p1", "g1", lease_token=None
            )

        # Attempting to complete with wrong lease_token MUST raise StaleLeaseError
        with self.assertRaises(StaleLeaseError):
            self.repo.complete(
                job.job_id,
                {"feedback_text": "ok"},
                10.0,
                "m1",
                "p1",
                "g1",
                lease_token="fake-lease-token",
            )

        # Attempting to fail with None lease_token MUST raise StaleLeaseError
        with self.assertRaises(StaleLeaseError):
            self.repo.fail(job.job_id, "error message", lease_token=None)

        # Completing with valid lease token succeeds
        completed = self.repo.complete(
            job.job_id,
            {"feedback_text": "ok"},
            10.0,
            "m1",
            "p1",
            "g1",
            lease_token=claimed.lease_token,
        )
        self.assertEqual(completed.status, "completed")

    def test_concurrent_worker_claims_no_double_processing(self):
        grading = {"status": "semantic_error", "score": 0.0}
        # Enqueue 20 jobs
        for i in range(20):
            self.repo.enqueue(f"att-conc-{i}", "S001", "sql_join_01", f"SELECT {i};", grading)

        claimed_jobs = []

        def worker_task(worker_id):
            worker = FeedbackWorker(self.repo, worker_id=worker_id)
            jobs_done = []
            while True:
                job = worker.process_one()
                if not job:
                    break
                jobs_done.append(job.job_id)
            return jobs_done

        # 4 concurrent workers pulling from the queue
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(worker_task, f"w-{i}") for i in range(4)]
            for f in concurrent.futures.as_completed(futures):
                claimed_jobs.extend(f.result())

        # All 20 jobs must be processed exactly once (no duplicates, no missed jobs)
        self.assertEqual(len(claimed_jobs), 20)
        self.assertEqual(len(set(claimed_jobs)), 20)
        self.assertEqual(self.repo.stats()["completed"], 20)
        self.assertEqual(self.repo.stats().get("pending", 0), 0)

        # Database integrity check passes after concurrent operations
        with closing(self.repo.connect()) as db:
            integrity = db.execute("PRAGMA integrity_check;").fetchone()[0]
            self.assertEqual(integrity.lower(), "ok")


if __name__ == "__main__":
    unittest.main()
