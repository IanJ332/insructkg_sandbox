"""End-to-end browser integration test for SIIP asynchronous feedback lifecycle.
Exercises:
1. PL submission hook execution with deterministic grading (<10ms).
2. Durable HTTP queue enqueue (/api/queue/enqueue).
3. Independent feedback worker execution and provenance generation.
4. Authorized learner browser delivery via HMAC signed ticket in Playwright.
5. 403 Forbidden rejection and zero identity disclosure when student S002 accesses S001's feedback.
6. 401 Unauthorized rejection when accessing without signed ticket.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

# Ensure Playwright browser cache on D: drive is used
d_cache = Path("D:/AI/Cache/Playwright")
if d_cache.is_dir() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(d_cache)

from dashboard import DashboardServer
from playwright.sync_api import expect, sync_playwright
from siip.identity import create_signed_ticket
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.pl_bridge import grade_question
from siip.store import SubmissionRepository


class TestAsyncBrowserFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs_db = Path(self.tmp.name) / "e2e_jobs.sqlite3"
        self.sub_db = Path(self.tmp.name) / "e2e_sub.sqlite3"

        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ASYNC_FEEDBACK"] = "1"
        os.environ["SIIP_FEEDBACK_PROVIDER"] = "local"

        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.sub_repo = SubmissionRepository(self.sub_db)

        # Start host dashboard server
        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.server_port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        # Configure queue URL to point to host dashboard HTTP endpoint
        os.environ["SIIP_QUEUE_URL"] = f"http://127.0.0.1:{self.server_port}/api/queue/enqueue"
        os.environ["SIIP_FEEDBACK_SERVICE_URL"] = f"http://127.0.0.1:{self.server_port}"

        # Initialize worker pointing to queue repository and submission repository
        self.worker = FeedbackWorker(
            self.jobs_repo, worker_id="e2e-worker", submission_repo=self.sub_repo
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_complete_async_browser_lifecycle(self):
        # Step 1: Student S001 submits SQL with semantic error via PrairieLearn hook
        submission_data = {
            "submitted_answers": {
                "sql": "SELECT e.name, d.department_name FROM Employees e JOIN Departments d ON e.department_id = d.department_id;"
            },
            "options": {"user": {"user_id": 101, "uid": "student1@example.com"}},
            "submission_id": 98765,
            "partial_scores": {},
            "feedback": {},
        }

        grade_question(submission_data, "sql_join_02")

        # 1a. Deterministic grade was computed immediately
        self.assertEqual(submission_data["score"], 0.0)
        self.assertEqual(submission_data["feedback"]["status"], "semantic_error")

        # 1b. Asynchronous job was dispatched via HTTP queue
        job_id = submission_data["feedback"]["job_id"]
        ticket = submission_data["feedback"]["ticket"]
        feedback_url = submission_data["feedback"]["feedback_url"]

        self.assertIsNotNone(job_id)
        self.assertIsNotNone(ticket)
        self.assertIsNotNone(feedback_url)
        self.assertIn(f"job_id={job_id}", feedback_url)
        self.assertIn(f"ticket={ticket}", feedback_url)

        # 1c. Job is pending in queue
        job_before = self.jobs_repo.get(job_id)
        self.assertIsNotNone(job_before)
        self.assertEqual(job_before.status, "pending")
        self.assertEqual(job_before.student_id, "S001")

        # Step 2: Background worker claims and executes inference
        processed_job = self.worker.process_one()
        self.assertIsNotNone(processed_job)
        self.assertEqual(processed_job.job_id, job_id)
        self.assertEqual(processed_job.status, "completed")
        self.assertIsNotNone(processed_job.result)

        # Step 3: Browser retrieval by authorized student S001 using Playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 960})
            page = context.new_page()

            # 3a. Navigate to authorized feedback URL
            resp = page.goto(feedback_url)
            self.assertEqual(resp.status, 200)

            # 3b. Verify authorized learner view content
            expect(page.get_by_role("heading", name="Personalized AI feedback")).to_be_visible()
            expect(page.get_by_text("Learner: S001")).to_be_visible()
            expect(page.get_by_text("COMPLETED", exact=True)).to_be_visible()
            expect(page.locator("pre")).to_contain_text("SELECT e.name, d.department_name")
            expect(page.get_by_role("heading", name="Pedagogical guidance")).to_be_visible()

            # Verify grounding candidate concepts and references rendered
            guidance_text = page.locator("section:has-text('Pedagogical guidance')").inner_text()
            self.assertIn("LEFT_OUTER_JOIN", guidance_text)

            # Step 4: Verification of 403 Forbidden when Student S002 attempts to access S001's job
            ticket_s002 = create_signed_ticket("S002", job_id)
            forbidden_url = (
                f"http://127.0.0.1:{self.server_port}/feedback?job_id={job_id}&ticket={ticket_s002}"
            )

            resp_cross = page.goto(forbidden_url)
            self.assertEqual(resp_cross.status, 403)
            expect(page.get_by_role("heading", name="403 Forbidden: Access Denied")).to_be_visible()

            body_cross = page.locator("body").inner_text()
            # Zero identity disclosure: MUST NOT reveal S001 or job ownership details
            self.assertNotIn("S001", body_cross)
            self.assertNotIn("belongs to", body_cross.lower())

            # Step 5: Verification of 401 Unauthorized when accessing without ticket
            unauth_url = f"http://127.0.0.1:{self.server_port}/feedback?job_id={job_id}"
            resp_unauth = page.goto(unauth_url)
            self.assertEqual(resp_unauth.status, 401)
            expect(page.get_by_role("heading", name="401 Unauthorized")).to_be_visible()

            browser.close()


if __name__ == "__main__":
    unittest.main()
