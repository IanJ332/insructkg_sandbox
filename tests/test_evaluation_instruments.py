"""Unit and Integration Tests for Phase 5.3: Multi-Stakeholder Evaluation & Research Instruments.

Verifies:
1. Student perception survey constructs and Likert scale completeness.
2. Instructor review rubric weights (summing to 1.0) and qualitative scoring levels.
3. Triple-blinded comparative review protocol specifications.
4. Cohort analytics aggregation, concept bottleneck tracking, and API exports.
5. Strict metadata tagging preserving Track A synthetic boundaries.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from dashboard import DashboardServer
from siip.em_repository import EMRepository
from siip.identity import create_signed_session_token
from siip.jobs import FeedbackJobRepository
from siip.project_generator import ProjectRepository, generate_personalized_project
from siip.store import SubmissionRepository
from siip.survey_instruments import (
    INSTRUCTOR_REVIEW_RUBRIC,
    STUDENT_PERCEPTION_SURVEY,
    get_evaluation_instruments,
)


class TestSurveyAndRubricStructures(unittest.TestCase):
    def test_student_perception_survey_coverage(self):
        from dataclasses import asdict

        inst = get_evaluation_instruments()
        survey = inst["student_perception_survey"]
        self.assertEqual(survey, [asdict(q) for q in STUDENT_PERCEPTION_SURVEY])
        self.assertEqual(len(survey), 5)

        categories = {q["category"] for q in survey}
        self.assertIn("Cognitive Load", categories)
        self.assertIn("Pedagogical Actionability", categories)
        self.assertIn("Curriculum Grounding", categories)
        self.assertIn("Entrepreneurial Mindset (EM)", categories)
        self.assertIn("Open-Ended Synthesis", categories)

        for q in survey:
            self.assertEqual(q["scale_type"], "likert_5")
            self.assertEqual(q["min_label"], "Strongly Disagree")
            self.assertEqual(q["max_label"], "Strongly Agree")

    def test_instructor_rubric_weights_sum_to_one(self):
        rubric = INSTRUCTOR_REVIEW_RUBRIC
        total_weight = sum(r.weight for r in rubric)
        self.assertAlmostEqual(total_weight, 1.0, places=4)

        for r in rubric:
            self.assertEqual(set(r.scoring_levels.keys()), {1, 2, 3})
            self.assertTrue(len(r.description) > 20)

    def test_blind_review_protocol_specifies_anonymization(self):
        inst = get_evaluation_instruments()
        protocol = inst["blind_review_protocol"]
        self.assertIn("Option Alpha", protocol["blinding_procedure"])
        self.assertIn("redacted", protocol["blinding_procedure"])
        self.assertTrue(len(protocol["evaluation_tasks"]) >= 3)


class TestCohortAnalyticsDashboardIntegration(unittest.TestCase):
    """Integration test verifying dashboard UI and JSON APIs for cohort analytics and instruments."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sub_db = Path(self.tmp.name) / "sub.sqlite3"
        self.jobs_db = Path(self.tmp.name) / "jobs.sqlite3"
        os.environ["SIIP_FEEDBACK_JOBS_DB"] = str(self.jobs_db)
        os.environ["SIIP_DB_PATH"] = str(self.sub_db)
        os.environ["SIIP_ALLOW_SYNTHETIC_AUTH"] = "1"
        os.environ["SIIP_ENV"] = "development"

        self.sub_repo = SubmissionRepository(self.sub_db)
        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.em_repo = EMRepository(self.sub_db)
        self.proj_repo = ProjectRepository(self.sub_db)

        # Pre-seed one project and one EM reflection
        proj = generate_personalized_project("S001", interest="healthcare")
        self.proj_repo.save_project(proj)
        self.em_repo.record_response(
            student_id="S001",
            question_id="sql_join_02",
            prompt_id="em-prompt-x1",
            attempt_id="att-init-1",
            response_text="Test reflection for cohort analytics.",
        )
        self.instructor_token = create_signed_session_token("instructor_alawini", role="instructor")

        self.server = DashboardServer(self.sub_repo, 0, host="127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def _request(
        self, method: str, path: str, body: str | None = None, headers: dict | None = None
    ):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        hdrs = headers or {}
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        status = resp.status
        resp_headers = dict(resp.getheaders())
        conn.close()
        return status, data, resp_headers

    def test_overview_renders_cohort_metrics_and_bottlenecks(self):
        status, data, _ = self._request("GET", "/")
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Curricular Concept Bottlenecks", html_str)
        self.assertIn("Multi-Stakeholder Research Framework", html_str)
        self.assertIn("EM reflections", html_str)
        self.assertIn("Dynamic projects", html_str)

    def test_instruments_html_page(self):
        status, data, _ = self._request("GET", "/instruments")
        self.assertEqual(status, 200)
        html_str = data.decode("utf-8")
        self.assertIn("Multi-Stakeholder Research Evaluation Instruments", html_str)
        self.assertIn("Cognitive Load", html_str)
        self.assertIn("Technical &amp; Relational Correctness", html_str)
        self.assertIn("Triple-Blinded Evaluation Protocol", html_str)

    def test_instruments_json_api(self):
        status, data, _ = self._request("GET", "/api/instruments")
        self.assertEqual(status, 200)
        inst = json.loads(data.decode("utf-8"))
        self.assertIn("student_perception_survey", inst)
        self.assertIn("instructor_review_rubric", inst)
        self.assertIn("blind_review_protocol", inst)

    def test_cohort_analytics_json_api(self):
        status, data, _ = self._request(
            "GET",
            "/api/cohort-analytics",
            headers={"Authorization": f"Bearer {self.instructor_token}"},
        )
        self.assertEqual(status, 200)
        analytics = json.loads(data.decode("utf-8"))
        self.assertEqual(analytics["cohort_size"], 5)
        self.assertEqual(analytics["provenance"], "TRACK_A_SYNTHETIC_COHORT")
        self.assertIn("em_reflection_summary", analytics)
        self.assertIn("project_summary", analytics)
        self.assertEqual(analytics["project_summary"]["total_generated"], 1)


if __name__ == "__main__":
    unittest.main()
