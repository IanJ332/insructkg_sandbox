"""Synthetic Portal Full Browser Workflow Verification (Phase 5.6 Category B).

Exercises the complete browser workflow hosted on the Synthetic Dashboard Portal
(/practice), executing the PrairieLearn Python grading hook (pl_bridge.grade_question)
and testing the full browser integration path without direct Python backend calls in
the test body:

1. Student login and session authorization via browser form.
2. Synthetic portal practice query submission and deterministic PL grading receipt.
3. Asynchronous grounded feedback delivery and display via signed ticket.
4. Entrepreneurial Mindset (EM) reflection submission via browser form.
5. Student review rejection (403 Forbidden when student accesses /em-review).
6. Instructor login and EM review acceptance via browser form.
7. Dynamic project generation and instructor approval with notes via browser form.
8. Learner-safe project retrieval: answer key concealment, review controls omitted.

Note: This verifies the Synthetic Dashboard Portal interactive interface. It does
not execute the containerized native Node.js/Postgres PrairieLearn application UI.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

# Ensure Playwright browser cache on D: drive is used
d_cache = Path("D:/AI/Cache/Playwright")
if d_cache.is_dir() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(d_cache)

if "SIIP_DATA_DIR" not in os.environ:
    os.environ["SIIP_DATA_DIR"] = str(ROOT / "artifacts/public-data")

from dashboard import DashboardServer, get_em_repo, get_project_repo
from playwright.sync_api import expect, sync_playwright
from siip.grader import QUESTIONS
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.store import SubmissionRepository


class AsyncWorkerThread(threading.Thread):
    """Background daemon thread executing feedback queue jobs as in production."""

    def __init__(self, worker: FeedbackWorker, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.worker = worker
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            job = self.worker.process_one()
            if not job:
                time.sleep(0.05)


class TestRealBrowserE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.tmp.name)
        self.jobs_db = self.dir_path / "real_e2e_jobs.sqlite3"
        self.sub_db = self.dir_path / "real_e2e_sub.sqlite3"

        os.environ.pop("SIIP_QUEUE_URL", None)
        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_EM_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_PROJECT_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ASYNC_FEEDBACK"] = "1"
        os.environ["SIIP_FEEDBACK_PROVIDER"] = "local"
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.sub_repo = SubmissionRepository(self.sub_db)
        self.em_repo = get_em_repo()
        self.proj_repo = get_project_repo()

        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.server_port = self.server.server_port
        self.base_url = f"http://127.0.0.1:{self.server_port}"
        os.environ["SIIP_FEEDBACK_SERVICE_URL"] = self.base_url

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        # Start continuous background queue worker
        self.worker = FeedbackWorker(
            self.jobs_repo, worker_id="real-browser-worker", submission_repo=self.sub_repo
        )
        self.stop_worker = threading.Event()
        self.worker_thread = AsyncWorkerThread(self.worker, self.stop_worker)
        self.worker_thread.start()

    def tearDown(self):
        self.stop_worker.set()
        self.worker_thread.join(timeout=2.0)
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        self.tmp.cleanup()
        os.environ.pop("SIIP_QUEUE_URL", None)
        os.environ.pop("SIIP_FEEDBACK_SERVICE_URL", None)

    def test_complete_real_browser_prairielearn_e2e_lifecycle(self):
        """Full end-to-end integration path conducted entirely through browser interactions."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 960})
            page = context.new_page()

            # -------------------------------------------------------------------
            # Step 1: Student login and session authorization via browser form
            # -------------------------------------------------------------------
            page.goto(f"{self.base_url}/login")
            expect(page.locator("h2")).to_contain_text("Research Demo Login")
            page.select_option("select[name='principal']", "S001")
            page.click("button:has-text('Sign In to Demo Session')")
            page.wait_for_load_state("networkidle")

            # Verify authenticated status
            page.goto(f"{self.base_url}/login")
            expect(page.locator("text=Logged in as S001")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 2: SQL grading via authentic PrairieLearn browser submission
            # -------------------------------------------------------------------
            page.goto(f"{self.base_url}/practice?id=sql_join_04")
            expect(page.locator("h2")).to_contain_text("PrairieLearn Interactive SQL Practice")
            expect(page.locator("code:has-text('sql_join_04')")).to_be_visible()

            # Enter correct reference SQL in browser textarea
            target_sql = QUESTIONS["sql_join_04"]["reference_sql"]
            page.fill("textarea#sql", target_sql)
            page.click("button#submit-query")
            page.wait_for_load_state("networkidle")

            # Verify PrairieLearn grading receipt rendered in browser
            expect(page.locator("h3:has-text('PrairieLearn Grading Receipt')")).to_be_visible()
            expect(page.locator("span.badge:has-text('CORRECT')")).to_be_visible()
            expect(page.locator("text=Score: 100%")).to_be_visible()
            expect(page.locator("#ai-feedback-link")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 3: Grounded AI Feedback availability via browser navigation
            # -------------------------------------------------------------------
            # Click the grounded AI explanation link
            page.click("#ai-feedback-link")
            page.wait_for_load_state("networkidle")

            # Verify grounded feedback and EM reflection prompt
            expect(page.locator("h2").first).to_contain_text("Personalized AI feedback")
            expect(page.locator("text=Learner: S001")).to_be_visible()
            expect(page.locator("text=COMPLETED").first).to_be_visible()
            expect(
                page.locator("text=Entrepreneurial Mindset (EM) Reflection (Optional)")
            ).to_be_visible()
            expect(page.locator("text=Creating Value (V)")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 4: EM Reflection submission via browser form
            # -------------------------------------------------------------------
            reflection_text = (
                "Accurate outer join aggregation across all operating units ensures equitable "
                "resource allocation and protects underrepresented clinical departments from "
                "silent administrative omission."
            )
            page.fill("textarea#reflection_text", reflection_text)
            page.click("button:has-text('Submit Reflection')")
            page.wait_for_load_state("networkidle")

            # Verify reflection recorded in PROPOSED status in browser view
            expect(page.locator("text=Status: PROPOSED")).to_be_visible()
            expect(page.locator("text=Your submitted reflection")).to_be_visible()
            expect(page.locator(f"text={reflection_text}")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 5: Student review rejection (Negative Authorization Check)
            # -------------------------------------------------------------------
            page.goto(f"{self.base_url}/em-review")
            expect(page.locator("body")).to_contain_text(
                "Forbidden: Synthetic students cannot perform instructor actions."
            )

            # -------------------------------------------------------------------
            # Step 6: Instructor login and EM review acceptance
            # -------------------------------------------------------------------
            page.goto(f"{self.base_url}/login")
            page.select_option("select[name='principal']", "instructor_alawini")
            page.click("button:has-text('Sign In to Demo Session')")
            page.wait_for_load_state("networkidle")

            # Instructor accesses /em-review
            page.goto(f"{self.base_url}/em-review")
            expect(page.locator("h2")).to_contain_text(
                "Instructor Entrepreneurial Mindset (EM) Evidence Review"
            )
            expect(page.locator("text=S001").first).to_be_visible()
            expect(page.locator(f"text={reflection_text[:60]}")).to_be_visible()
            expect(page.locator("span.badge:has-text('PROPOSED')").first).to_be_visible()

            # Accept evidence with instructor notes
            page.fill(
                "input[name='instructor_notes']",
                "Approved: Explicitly connects query edge-case aggregation to organizational equity.",
            )
            page.click("button:has-text('Accept')")
            page.wait_for_load_state("networkidle")

            # Verify evidence status is now ACCEPTED
            expect(page.locator("span.badge:has-text('ACCEPTED')").first).to_be_visible()

            # Instructor confirms student profile reflects accepted EM evidence
            page.goto(f"{self.base_url}/students?id=S001")
            expect(page.locator("text=OBSERVED_EVIDENCE_RECORDED")).to_be_visible()
            expect(page.locator("text=Creating Value (V) accepted")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 7: Dynamic project generation and instructor approval
            # -------------------------------------------------------------------
            page.goto(f"{self.base_url}/projects")
            expect(page.locator("h2")).to_contain_text("Personalized Dynamic SQL Projects")

            # Generate project for S001 via instructor form
            page.click(".card:has-text('S001') button:has-text('Generate Project')")
            page.wait_for_load_state("networkidle")

            # Verify on project page with instructor review controls
            expect(page.locator("h3:has-text('Instructor Review & Approval')")).to_be_visible()
            expect(page.locator("summary:has-text('Reference SQL Solution')").first).to_be_visible()
            current_project_url = page.url
            self.assertIn("/projects?id=", current_project_url)

            # Instructor approves the project
            page.fill(
                "input[name='notes']",
                "Approved for healthcare analytics query design exercise.",
            )
            page.click("button:has-text('Approve Project')")
            page.wait_for_load_state("networkidle")

            # Verify status is now APPROVED in instructor view
            expect(page.locator("text=Status: APPROVED")).to_be_visible()

            # -------------------------------------------------------------------
            # Step 8: Learner-safe project retrieval
            # -------------------------------------------------------------------
            # Switch back to synthetic student S001
            page.goto(f"{self.base_url}/login")
            page.select_option("select[name='principal']", "S001")
            page.click("button:has-text('Sign In to Demo Session')")
            page.wait_for_load_state("networkidle")

            # S001 accesses the project
            page.goto(current_project_url)
            learner_page_content = page.content()

            # Verify project is retrieved as learner
            expect(page.locator("text=Status: APPROVED")).to_be_visible()

            # Pending notice is cleared
            expect(page.locator("text=Pending Instructor Approval")).not_to_be_visible()

            # CRITICAL SECURITY INVARIANT: Reference solutions MUST NOT be in learner DOM
            self.assertNotIn("Reference SQL Solution", learner_page_content)
            self.assertNotIn("Grading Ground Truth", learner_page_content)

            # Review controls MUST NOT be present in learner DOM
            self.assertNotIn('action="/api/projects/review"', learner_page_content)
            self.assertNotIn("Approve Project", learner_page_content)

            browser.close()


if __name__ == "__main__":
    unittest.main()
