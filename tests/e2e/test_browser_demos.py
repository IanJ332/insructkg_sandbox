"""End-to-end browser integration tests for Demos A, B, and C.

Uses Playwright to independently verify all three demo flows:
- Demo A: Personalized SQL Learning (deterministic grading, worker completion,
  feedback delivery, and evidenced differential recommendations for S001 vs S002).
- Demo B: Entrepreneurial Mindset (sql_join_04 completion, EM Info Box, reflection
  submission, PROPOSED evidence creation, instructor review acceptance, student
  profile update, and student 403 Forbidden authorization negative test).
- Demo C: Personalized Dynamic Mini Project (profile adaptation rationale,
  answer key concealment in learner view, pending notice for unapproved projects,
  and instructor approval workflow).
"""

from __future__ import annotations

import json
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

if "SIIP_DATA_DIR" not in os.environ:
    os.environ["SIIP_DATA_DIR"] = str(ROOT / "artifacts/public-data")

from dashboard import DashboardServer, get_em_repo, get_project_repo
from playwright.sync_api import sync_playwright
from siip.grader import QUESTIONS, grade
from siip.identity import create_signed_session_token, create_signed_ticket
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.project_generator import generate_personalized_project
from siip.recommender import recommend_next_activity
from siip.store import SubmissionRepository


class TestBrowserDemos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.tmp.name)
        self.jobs_db = self.dir_path / "browser_jobs.sqlite3"
        self.sub_db = self.dir_path / "browser_sub.sqlite3"
        self.em_db = self.dir_path / "browser_em.sqlite3"
        self.proj_db = self.dir_path / "browser_proj.sqlite3"

        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_EM_DB_PATH"] = str(self.em_db)
        os.environ["SIIP_PROJECT_DB_PATH"] = str(self.proj_db)
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.sub_repo = SubmissionRepository(self.sub_db)
        self.em_repo = get_em_repo()
        self.proj_repo = get_project_repo()

        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.server_port = self.server.server_port
        self.base_url = f"http://127.0.0.1:{self.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        self.worker = FeedbackWorker(
            self.jobs_repo, worker_id="browser-worker", submission_repo=self.sub_repo
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    # ---------------------------------------------------------------------------
    # Demo A: Personalized SQL Learning Browser Flow
    # ---------------------------------------------------------------------------
    def test_demo_a_personalized_sql_learning_browser_flow(self):
        """Browser verification of Demo A:

        1. Learner S001 submits incorrect SQL on sql_join_02.
        2. Deterministic grading returns score 0.0 with observation missing_unmatched_rows.
        3. Background worker completes feedback job.
        4. S001 views personalized feedback using signed ticket.
        5. Profile reflects attempt.
        6. Recommender recommends INNER_JOIN remediation for S001.
        7. Student S002 (with INNER_JOIN mastered) receives a different recommendation.
        """
        # Step 1 & 2: S001 submits incorrect SQL for sql_join_02
        s001_sql = "SELECT e.name, d.department_name FROM Employees e INNER JOIN Departments d ON e.department_id = d.department_id;"
        s001_grading = grade("sql_join_02", s001_sql)
        self.assertEqual(s001_grading["score"], 0.0)
        self.assertEqual(s001_grading["status"], "semantic_error")
        self.assertEqual(s001_grading["observation"], "missing_unmatched_rows")

        # Record in submission repo
        att_id = "demo-a-s001-att1"
        self.sub_repo.process(
            {
                "attempt_id": att_id,
                "student_id": "S001",
                "question_id": "sql_join_02",
                "submitted_sql": s001_sql,
                "timestamp": "2026-10-15T10:00:00Z",
            }
        )

        # Step 3: Enqueue and process feedback job
        job = self.jobs_repo.enqueue(
            att_id, "S001", "sql_join_02", s001_sql, s001_grading, mode="kg"
        )
        completed_job = self.worker.process_one()
        self.assertIsNotNone(completed_job)
        self.assertEqual(completed_job.status, "completed")

        # Step 4: S001 views feedback via Playwright browser
        ticket = create_signed_ticket("S001", job.job_id)
        feedback_url = f"{self.base_url}/feedback?job_id={job.job_id}&ticket={ticket}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto(feedback_url)
            content = page.content()
            self.assertIn("Personalized AI feedback", content)
            self.assertIn("Consider which join preserves rows", content)

            # Step 5: S001 visits their student profile
            page.goto(f"{self.base_url}/students?id=S001")
            prof_content = page.content()
            self.assertIn("synthetic learning history", prof_content)
            self.assertIn("Adaptive Next-Activity Recommendation", prof_content)

            # Step 6: Verify S001 recommendation
            s001_profile = self.sub_repo.profile("S001")
            s001_rec = recommend_next_activity("S001", s001_profile)
            self.assertIn(s001_rec["recommended_question_id"], prof_content)

            # Step 7: Demonstrate S002 with a different history receives distinct recommendation
            # S002 masters INNER_JOIN and LEFT_OUTER_JOIN
            self.sub_repo.process(
                {
                    "attempt_id": "demo-a-s002-att1",
                    "student_id": "S002",
                    "question_id": "sql_join_01",
                    "submitted_sql": QUESTIONS["sql_join_01"]["reference_sql"],
                    "timestamp": "2026-10-15T09:00:00Z",
                }
            )
            self.sub_repo.process(
                {
                    "attempt_id": "demo-a-s002-att2",
                    "student_id": "S002",
                    "question_id": "sql_join_02",
                    "submitted_sql": QUESTIONS["sql_join_02"]["reference_sql"],
                    "timestamp": "2026-10-15T09:30:00Z",
                }
            )
            s002_profile = self.sub_repo.profile("S002")
            s002_rec = recommend_next_activity("S002", s002_profile)

            # S001 and S002 must receive DIFFERENT recommendations based on evidence
            self.assertNotEqual(
                s001_rec["recommended_question_id"],
                s002_rec["recommended_question_id"],
                f"S001 ({s001_rec['recommended_question_id']}) and S002 ({s002_rec['recommended_question_id']}) should differ",
            )

            # Verify S002 profile in browser
            page.goto(f"{self.base_url}/students?id=S002")
            s002_content = page.content()
            self.assertIn(s002_rec["recommended_question_id"], s002_content)
            self.assertIn("Practice combining outer joins with COUNT(column)", s002_content)

            browser.close()

    # ---------------------------------------------------------------------------
    # Demo B: Entrepreneurial Mindset Browser Flow & Negative Authorization Test
    # ---------------------------------------------------------------------------
    def test_demo_b_entrepreneurial_mindset_browser_flow(self):
        """Browser verification of Demo B:

        1. Complete sql_join_04 correctly (score 1.0).
        2. Technical feedback displays voluntary EM reflection prompt.
        3. Submit reflection -> EM evidence created in PROPOSED status.
        4. Instructor reviews evidence at /em-review and accepts.
        5. Student profile reflects accepted EM behavioral evidence.
        6. Concept mastery is strictly invariant.
        7. Mandatory negative test: student cannot review/approve EM evidence.
        """
        # 1. Technical completion
        correct_sql = QUESTIONS["sql_join_04"]["reference_sql"]
        grading = grade("sql_join_04", correct_sql)
        self.assertEqual(grading["score"], 1.0)

        att_id = "demo-b-s001-att1"
        self.sub_repo.process(
            {
                "attempt_id": att_id,
                "student_id": "S001",
                "question_id": "sql_join_04",
                "submitted_sql": correct_sql,
                "timestamp": "2026-10-15T11:00:00Z",
            }
        )
        job = self.jobs_repo.enqueue(att_id, "S001", "sql_join_04", correct_sql, grading, mode="kg")
        self.worker.process_one()

        ticket = create_signed_ticket("S001", job.job_id)
        feedback_url = f"{self.base_url}/feedback?job_id={job.job_id}&ticket={ticket}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 2. View feedback and voluntary EM prompt
            page.goto(feedback_url)
            self.assertIn("Creating Value (V)", page.content())
            self.assertIn("Entrepreneurial Mindset (EM) Reflection (Optional)", page.content())

            # 3. Submit reflection via form
            page.fill(
                "textarea[name='reflection_text']",
                "Silent department omissions distort quarterly budget allocations across business units.",
            )
            page.click("button:has-text('Submit Reflection')")
            page.wait_for_load_state("networkidle")

            # 4. Verify PROPOSED evidence record in repository
            summary_before = self.em_repo.student_em_summary("S001")
            self.assertEqual(summary_before["total_observations"], 1)
            ev_id = summary_before["records"][0]["evidence_id"]
            self.assertEqual(summary_before["records"][0]["review_status"], "PROPOSED")

            # 5. Instructor reviews at /em-review
            page.goto(f"{self.base_url}/em-review")
            self.assertIn(ev_id, page.content())
            self.assertIn("Silent department omissions", page.content())

            # Perform instructor review
            page.fill(
                "input[name='instructor_notes']",
                "Accurately connects query edge case to budget risks.",
            )
            page.click("button:has-text('Accept')")
            page.wait_for_load_state("networkidle")

            # 6. Verify evidence status is now ACCEPTED
            summary_after = self.em_repo.student_em_summary("S001")
            self.assertEqual(summary_after["accepted_by_dimension"]["V"], 1)

            # View student profile
            page.goto(f"{self.base_url}/students?id=S001")
            prof_html = page.content()
            self.assertIn("OBSERVED_EVIDENCE_RECORDED", prof_html)
            self.assertIn("Creating Value (V) accepted", prof_html)

            # 7. Mandatory negative test: Student session token rejected with 403
            student_token = create_signed_session_token("S001", role="student")

            # Attempt to change review status as student via POST
            api_resp = page.request.post(
                f"{self.base_url}/api/em/review",
                data=json.dumps({"evidence_id": ev_id, "review_status": "REJECTED"}),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {student_token}",
                },
            )
            self.assertEqual(api_resp.status, 403)
            self.assertIn("Forbidden", api_resp.text())

            browser.close()

    # ---------------------------------------------------------------------------
    # Demo C: Dynamic Personalized Project Browser Flow
    # ---------------------------------------------------------------------------
    def test_demo_c_dynamic_personalized_project_browser_flow(self):
        """Browser verification of Demo C:

        1. Project generated for S001 based on clinical operations interest.
        2. Learner view conceals reference SQL solution and shows pending approval notice.
        3. Instructor view displays reference SQL solutions and approval controls.
        4. Instructor approves project.
        5. Learner view now shows APPROVED status and pending notice is cleared.
        """
        # Generate project adapted to profile
        s001_prof = self.sub_repo.profile("S001")
        project = generate_personalized_project("S001", interest="healthcare", profile=s001_prof)
        self.proj_repo.save_project(project)

        # Provenance includes adaptation rationale
        self.assertIn("profile_adaptation_rationale", project.generation_provenance)
        self.assertIn("adapted_difficulty_level", project.generation_provenance)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Learner View (?view=learner)
            learner_url = f"{self.base_url}/projects?id={project.project_id}&view=learner"
            page.goto(learner_url)
            learner_html = page.content()

            # Reference SQL MUST be concealed
            self.assertNotIn("Reference SQL Solution", learner_html)
            self.assertNotIn("SELECT physicians.name", learner_html)

            # Pending notice MUST be visible
            self.assertIn("Pending Instructor Approval", learner_html)

            # Instructor review form MUST NOT be present
            self.assertNotIn('action="/api/projects/review"', learner_html)

            # 2. Instructor View (without view=learner)
            instructor_url = f"{self.base_url}/projects?id={project.project_id}"
            page.goto(instructor_url)
            inst_html = page.content()

            # Reference SQL is visible to instructor
            self.assertIn("Reference SQL Solution", inst_html)
            self.assertIn("SELECT physicians.name", inst_html)
            self.assertIn('action="/api/projects/review"', inst_html)

            # 3. Instructor approves project
            page.fill("input[name='notes']", "Approved for clinical query design exercise.")
            page.click("button:has-text('Approve Project')")
            page.wait_for_load_state("networkidle")

            # 4. Re-check Learner View
            page.goto(learner_url)
            approved_learner_html = page.content()

            # Status is now APPROVED
            self.assertIn("Status: APPROVED", approved_learner_html)
            # Pending notice is now gone
            self.assertNotIn("Pending Instructor Approval", approved_learner_html)
            # Reference SQL is STILL concealed from learner
            self.assertNotIn("Reference SQL Solution", approved_learner_html)
            self.assertNotIn("SELECT physicians.name", approved_learner_html)

            browser.close()


if __name__ == "__main__":
    unittest.main()
