"""Playwright Browser End-to-End Test for Entrepreneurial Mindset (EM) Vertical Slice (Phase 5.1).

Validates the full interactive loop in a real browser:
1. Learner visits feedback URL with HMAC ticket and observes the EM reflection prompt.
2. Learner types a reflection response and submits the form.
3. Learner is redirected and sees the submitted reflection in PROPOSED status.
4. Instructor visits /em-review, reviews the proposed evidence, adds notes, and accepts it.
5. Instructor views student profile at /students?id=... and confirms accepted EM evidence is recorded.
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
from siip.em_repository import EMRepository
from siip.identity import create_signed_ticket
from siip.jobs import FeedbackJobRepository
from siip.store import SubmissionRepository


class TestEMLifecycleBrowser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sub_db = Path(self.tmp.name) / "sub.sqlite3"
        self.jobs_db = Path(self.tmp.name) / "e2e_jobs.sqlite3"

        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.sub_repo = SubmissionRepository(self.sub_db)
        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.em_repo = EMRepository(self.sub_db)

        # Enqueue a completed job for synthetic learner S001 on sql_join_02 (Connections prompt)
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }
        self.job = self.jobs_repo.enqueue(
            attempt_id="att-em-browser-01",
            student_id="S001",
            question_id="sql_join_02",
            submitted_sql="SELECT Employees.name, Departments.name FROM Employees INNER JOIN Departments ON Employees.department_id = Departments.id;",
            grading=grading,
            mode="kg",
        )
        self.jobs_repo.complete(
            job_id=self.job.job_id,
            result={
                "feedback_text": "Remember that LEFT OUTER JOIN preserves rows from the left table even when no match exists.",
                "candidate_concepts": ["LEFT_OUTER_JOIN"],
                "evidence_references": ["Lecture 4: Join semantics"],
                "personalized": False,
                "history_provenance": "none",
            },
            latency_ms=18.0,
            model_identifier="test-model",
            prompt_version="v1",
            graph_version="g1",
            lease_token=self.jobs_repo.claim("worker-browser").lease_token,
        )

        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_browser_em_vertical_slice(self):
        ticket = create_signed_ticket("S001", self.job.job_id)
        feedback_url = f"{self.base_url}/feedback?job_id={self.job.job_id}&ticket={ticket}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Learner opens feedback page
            page.goto(feedback_url)
            expect(page.locator("h2").first).to_contain_text("Personalized AI feedback")
            expect(
                page.locator("text=Entrepreneurial Mindset (EM) Reflection (Optional)")
            ).to_be_visible()
            expect(page.locator("text=Connections (X)")).to_be_visible()

            # 2. Learner enters and submits reflection
            reflection_content = (
                "Choosing a LEFT OUTER JOIN safeguards downstream HR provisioning and building security access "
                "when personnel are temporarily unassigned to a department."
            )
            page.fill("textarea#reflection_text", reflection_content)
            page.click("button:has-text('Submit Reflection')")

            # 3. Learner sees submitted reflection with PROPOSED status
            page.wait_for_load_state("networkidle")
            expect(page.locator("text=Status: PROPOSED")).to_be_visible()
            expect(page.locator("text=Your submitted reflection")).to_be_visible()
            expect(page.locator(f"text={reflection_content}")).to_be_visible()

            # 4. Instructor visits /em-review
            page.goto(f"{self.base_url}/em-review")
            expect(page.locator("h2")).to_contain_text(
                "Instructor Entrepreneurial Mindset (EM) Evidence Review"
            )
            expect(page.locator("text=S001").first).to_be_visible()
            expect(page.locator("span.badge:has-text('PROPOSED')").first).to_be_visible()

            # 5. Instructor fills notes and clicks Accept
            page.fill(
                "input[name='instructor_notes']",
                "Accurately connects query semantics to HR and building security.",
            )
            page.click("button:has-text('Accept')")

            # 6. Verify row now reflects ACCEPTED status
            page.wait_for_load_state("networkidle")
            expect(page.locator("span.badge:has-text('ACCEPTED')").first).to_be_visible()

            # 7. Instructor verifies student profile
            page.goto(f"{self.base_url}/students?id=S001")
            expect(page.locator("h2:has-text('Entrepreneurial Mindset')")).to_be_visible()
            expect(page.locator("text=OBSERVED_EVIDENCE_RECORDED")).to_be_visible()
            expect(page.locator("text=Connections (X) accepted")).to_be_visible()
            expect(page.locator("text=Methodological Boundary:")).to_be_visible()

            browser.close()
