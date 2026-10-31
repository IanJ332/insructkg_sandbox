"""Historical personalization test suite for SIIP async worker.
Verifies that student historical mastery profile dynamically alters feedback advice,
cleanly labels non-personalized attempts when history is absent, and preserves KG grounding.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.feedback import factual_history, model_context_projection
from siip.grader import QUESTIONS
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.store import SubmissionRepository


class TestHistoricalPersonalization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sub_db = Path(self.tmp.name) / "submissions.sqlite3"
        self.jobs_db = Path(self.tmp.name) / "jobs.sqlite3"

        self.sub_repo = SubmissionRepository(self.sub_db)
        self.jobs_repo = FeedbackJobRepository(self.jobs_db)
        self.worker = FeedbackWorker(
            self.jobs_repo, worker_id="worker-test", submission_repo=self.sub_repo
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_low_vs_high_mastery_pedagogical_differentiation(self):
        # 1. Establish prior history for S001 on sql_join_02: Failed attempt (low mastery on LEFT_OUTER_JOIN)
        self.sub_repo.process(
            {
                "attempt_id": "hist-s001-1",
                "student_id": "S001",
                "question_id": "sql_join_02",
                "submitted_sql": "SELECT name FROM Employees;",  # incorrect
                "timestamp": "2026-10-14T08:00:00Z",
                "source": "synthetic_fixture",
            }
        )
        s001_profile = self.sub_repo.profile("S001")
        s001_loj = s001_profile["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]
        self.assertLess(s001_loj, 0.5)

        # 2. Establish prior history for S002 on sql_join_02: Successful attempt (high mastery on LEFT_OUTER_JOIN)
        self.sub_repo.process(
            {
                "attempt_id": "hist-s002-1",
                "student_id": "S002",
                "question_id": "sql_join_02",
                "submitted_sql": QUESTIONS["sql_join_02"]["reference_sql"],  # correct
                "timestamp": "2026-10-14T08:00:00Z",
                "source": "synthetic_fixture",
            }
        )
        s002_profile = self.sub_repo.profile("S002")
        s002_loj = s002_profile["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]
        self.assertGreaterEqual(s002_loj, 0.5)

        # 3. Both students now make the EXACT same mistake on sql_join_02
        err_sql = "SELECT e.name, d.department_name FROM Employees e JOIN Departments d ON e.department_id = d.department_id;"
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }

        job_s001 = self.jobs_repo.enqueue(
            "curr-s001-sql02",
            "S001",
            "sql_join_02",
            err_sql,
            grading,
            mode="kg",
        )
        job_s002 = self.jobs_repo.enqueue(
            "curr-s002-sql02",
            "S002",
            "sql_join_02",
            err_sql,
            grading,
            mode="kg",
        )

        # 4. Drain queue with worker (auto-resolving prior profile)
        drained = self.worker.drain()
        self.assertEqual(len(drained), 2)

        res1 = self.jobs_repo.get(job_s001.job_id).result
        res2 = self.jobs_repo.get(job_s002.job_id).result

        self.assertIsNotNone(res1)
        self.assertIsNotNone(res2)

        # 5. Verify historical personalization metadata
        self.assertTrue(res1["personalized"])
        self.assertEqual(res1["history_provenance"], "prior_submissions")
        self.assertTrue(res2["personalized"])
        self.assertEqual(res2["history_provenance"], "prior_submissions")

        # 6. Verify distinct feedback text reflecting low vs high prior mastery
        text1 = res1["feedback_text"]
        text2 = res2["feedback_text"]

        self.assertNotEqual(text1, text2)
        # S001 (< 0.5 mastery) receives foundational suggestion to revisit
        self.assertIn("Earlier attempts suggest revisiting", text1)
        # S002 (>= 0.5 mastery) receives positive evidence reinforcement
        self.assertIn("Earlier attempts provide positive evidence for", text2)

        # 7. Knowledge Graph grounding is preserved for both
        self.assertIn("candidate_concepts", res1)
        self.assertIn("candidate_concepts", res2)
        self.assertIn("LEFT_OUTER_JOIN", res1["candidate_concepts"])
        self.assertIn("LEFT_OUTER_JOIN", res2["candidate_concepts"])
        self.assertTrue(len(res1["evidence_references"]) > 0)
        self.assertTrue(len(res2["evidence_references"]) > 0)

    def test_first_time_student_cleanly_unpersonalized(self):
        # S003 has zero prior submissions on sql_join_02
        err_sql = "SELECT e.name FROM Employees e;"
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }

        self.jobs_repo.enqueue("att-s003-first", "S003", "sql_join_02", err_sql, grading, mode="kg")
        processed = self.worker.process_one()
        self.assertIsNotNone(processed)

        res = processed.result
        self.assertFalse(res["personalized"])
        self.assertEqual(res["history_provenance"], "none")
        self.assertEqual(res["historical_personalization"]["status"], "none")
        # Text does not fabricate earlier attempt advice
        self.assertNotIn("Earlier attempts", res["feedback_text"])
        # But KG grounding is intact
        self.assertIn("LEFT_OUTER_JOIN", res["candidate_concepts"])
        self.assertTrue(len(res["evidence_references"]) > 0)

    def test_factual_history_scoping_and_wire_from_persisted_attempts(self):
        rows = [
            ("error", "S001", "course-a", "2026-10-14T07:00:00Z", "SELECT 1"),
            (
                "correct",
                "S001",
                "course-a",
                "2026-10-14T08:00:00Z",
                QUESTIONS["sql_join_02"]["reference_sql"],
            ),
            ("same-time", "S001", "course-a", "2026-10-14T09:00:00Z", "SELECT 1"),
            ("future", "S001", "course-a", "2026-10-14T10:00:00Z", "SELECT 1"),
            ("other-course", "S001", "course-b", "2026-10-14T06:00:00Z", "SELECT 1"),
            ("other-student", "S002", "course-a", "2026-10-14T06:00:00Z", "SELECT 1"),
        ]
        self.sub_repo.process_many(
            [
                {
                    "attempt_id": aid,
                    "student_id": sid,
                    "question_id": "sql_join_02",
                    "timestamp": ts,
                    "course_id": course,
                    "submitted_sql": sql,
                }
                for aid, sid, course, ts, sql in rows
            ]
        )
        facts, refs = factual_history(
            self.sub_repo.records(),
            {"student_id": "S001", "course_id": "course-a", "cutoff": "2026-10-14T09:00:00Z"},
            QUESTIONS["sql_join_02"]["concepts"],
        )
        self.assertEqual(refs, ["error", "correct"])
        self.assertEqual(
            (facts["attempt_count"], facts["question_count"], facts["correct_count"]), (2, 1, 1)
        )
        self.assertEqual(
            [item["status"] for item in facts["observations"]], ["semantic_error", "correct"]
        )
        self.assertEqual(facts["last_seen"], "2026-10-14T08:00:00+00:00")
        self.assertEqual(facts["observations"][0]["source_kind"], "synthetic_fixture")
        wire = model_context_projection(
            {
                "prior_observations": facts,
                "student_mastery": {"X": {"mastery_estimate": 0.4}},
                "approved_prerequisite_history": [{"evidence_level": "weaker"}],
            }
        )
        serialized = __import__("json").dumps(wire)
        for forbidden in (
            "mastery",
            "estimate",
            "evidence_level",
            "attempt_id",
            "submitted_sql",
            "reference_sql",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("SELECT 1", serialized)
        self.assertEqual(
            factual_history(self.sub_repo.records(), None, ["LEFT_OUTER_JOIN"]), ({}, [])
        )

    def test_worker_and_batch_pass_verified_history_to_provider(self):
        class Provider:
            model = "test"

            def __init__(self):
                self.contexts = []

            def generate(self, context):
                self.contexts.append(model_context_projection(context))
                return {
                    "feedback_text": "Check which rows should remain in the result.",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }, None

        provider = Provider()
        prior = {
            "attempt_id": "prior",
            "student_id": "S001",
            "question_id": "sql_join_02",
            "timestamp": "2026-10-14T07:00:00Z",
            "course_id": "course-a",
            "submitted_sql": QUESTIONS["sql_join_02"]["reference_sql"],
        }
        current = {
            **prior,
            "attempt_id": "current",
            "timestamp": "2026-10-14T08:00:00Z",
            "submitted_sql": "SELECT 1",
        }
        saved = self.sub_repo.process_many([prior, current], provider=provider)
        self.assertEqual(provider.contexts[-1]["prior_observations"]["correct_count"], 1)
        self.assertEqual(
            saved[-1]["feedback"]["prior_observation_provenance"]["attempt_ids"], ["prior"]
        )
        provider.contexts.clear()
        self.jobs_repo.enqueue(
            "current", "S001", "sql_join_02", "SELECT 1", saved[-1]["grading"], mode="kg"
        )
        result = self.worker.process_one(provider=provider).result
        self.assertEqual(provider.contexts[-1]["prior_observations"]["correct_count"], 1)
        self.assertEqual(result["prior_observation_provenance"]["attempt_ids"], ["prior"])
        self.assertNotIn("student_mastery", provider.contexts[-1])
        self.assertTrue(result["personalized"])
        self.assertEqual(
            result["historical_personalization"],
            {
                "status": "provided_concept_evidence",
                "concept_count": len(set(QUESTIONS["sql_join_02"]["concepts"])),
                "evidence_kind": "observed_prior_grades",
            },
        )

    def test_manual_heuristic_is_not_provider_history(self):
        class Provider:
            model = "test"

            def generate(self, context):
                self.context = model_context_projection(context)
                return {
                    "feedback_text": "Check which rows should remain in the result.",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }, None

        provider = Provider()
        self.jobs_repo.enqueue(
            "manual",
            "S001",
            "sql_join_02",
            "SELECT 1",
            {"status": "semantic_error", "score": 0, "observation": "result_mismatch"},
            mode="kg",
        )
        mastery = {
            "LEFT_OUTER_JOIN": {"mastery_estimate": 0.25, "denominator": 1, "attempt_count": 2}
        }
        result = self.worker.process_one(provider=provider, mastery=mastery).result
        self.assertEqual(
            result["historical_personalization"],
            {"status": "none", "concept_count": 0, "evidence_kind": None},
        )
        self.assertFalse(result["personalized"])
        self.assertEqual(result["history_provenance"], "none")
        self.assertNotIn("prior_observations", provider.context)
        self.assertNotIn("student_mastery", provider.context)

    def test_time_bounding_excludes_future_submissions(self):
        # Prior submission created at 09:00:00Z
        self.sub_repo.process(
            {
                "attempt_id": "hist-prior",
                "student_id": "S001",
                "question_id": "sql_join_02",
                "submitted_sql": "SELECT 1;",
                "timestamp": "2026-10-14T09:00:00Z",
                "source": "synthetic_fixture",
            }
        )
        # Job created with created_at backdated to 08:00:00Z (before the submission above)
        grading = {
            "status": "semantic_error",
            "score": 0.0,
            "observation": "missing_unmatched_rows",
        }
        job = self.jobs_repo.enqueue(
            "job-backdated", "S001", "sql_join_02", "SELECT 1;", grading, mode="kg"
        )
        # Manually backdate job.created_at to 07:00:00Z in database using closing()
        with closing(self.jobs_repo.connect()) as db:
            db.execute(
                "UPDATE feedback_jobs SET created_at = '2026-10-14T07:00:00Z' WHERE job_id = ?",
                (job.job_id,),
            )
            db.commit()

        processed = self.worker.process_one()
        self.assertIsNotNone(processed)
        # Because job.created_at was 07:00:00Z, the 09:00:00Z submission is in the future relative to the job!
        # Therefore, student had NO prior submissions as of that timestamp.
        self.assertFalse(processed.result["personalized"])
        self.assertEqual(processed.result["history_provenance"], "none")


if __name__ == "__main__":
    unittest.main()
