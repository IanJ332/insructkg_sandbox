from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_student import (  # noqa: E402
    DemoStudentJourney,
    FIXTURE_HISTORY_LABEL,
    INNER_JOIN_HEADCOUNT_SQL,
)
from siip.jobs import FeedbackJobRepository  # noqa: E402
from siip.recommender import recommend_next_activity  # noqa: E402
from siip.store import SubmissionRepository  # noqa: E402


def published_assignment() -> dict:
    return {
        "assignment_id": "assignment-left-headcount-demo",
        "course_id": "intro-relational-databases-demo",
        "question_id": "sql_join_04",
        "relevant_kg_node_ids": ["LEFT_OUTER_JOIN", "COUNT_AGGREGATION"],
        "publication_timestamp": "2026-10-19T18:00:00Z",
        "grading_configuration": {"engine": "siip_deterministic_sql"},
        "publication_status": "PUBLISHED_LOCAL_DEMO",
        "native_prairielearn_publication": False,
    }


class TestDemoStudentJourney(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="siip-student-demo-test-")
        self.directory = Path(self.temp.name)
        self.journey = DemoStudentJourney(self.directory)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_inner_join_is_really_graded_persisted_diagnosed_and_queued(self) -> None:
        result = self.journey.submit(
            published_assignment(),
            "S001",
            INNER_JOIN_HEADCOUNT_SQL,
            submission_key="browser-submit-001",
            timestamp="2026-10-19T19:00:00Z",
        )

        # This score is produced by the existing two-dataset deterministic grader.
        self.assertEqual(result["grading"]["score"], 0)
        self.assertEqual(result["grading"]["status"], "semantic_error")
        self.assertEqual(result["grading"]["observation"], "result_mismatch")
        self.assertEqual(result["diagnosis"]["diagnosis_source"], "deterministic_rule")
        self.assertEqual(
            result["diagnosis"]["candidate_concepts"],
            ["LEFT_OUTER_JOIN", "COUNT_AGGREGATION", "GROUP_BY", "NULL_SEMANTICS"],
        )

        persisted = self.journey.submissions.attempt_for_student(result["attempt_id"], "S001")
        self.assertEqual(persisted["submitted_sql"], INNER_JOIN_HEADCOUNT_SQL)
        self.assertEqual(persisted["grading"]["score"], 0)
        self.assertEqual(persisted["diagnosis"], result["diagnosis"])

        job = self.journey.feedback_jobs.get(result["feedback_job"]["job_id"])
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempt_id, result["attempt_id"])
        self.assertEqual(job.submitted_sql, INNER_JOIN_HEADCOUNT_SQL)
        self.assertEqual(job.grading["score"], 0)
        self.assertNotIn("datasets", job.grading)

        # A browser retry of the same submission event is an idempotent replay.
        replay = self.journey.submit(
            published_assignment(),
            "S001",
            INNER_JOIN_HEADCOUNT_SQL,
            submission_key="browser-submit-001",
            timestamp="2026-10-19T20:00:00Z",
        )
        self.assertEqual(replay["attempt_id"], result["attempt_id"])
        self.assertEqual(replay["timestamp"], "2026-10-19T19:00:00+00:00")
        self.assertEqual(replay["feedback_job"]["job_id"], job.job_id)
        self.assertEqual(len(self.journey.submissions.records("S001")), 1)
        with self.assertRaisesRegex(ValueError, "conflicting SQL payload"):
            self.journey.submit(
                published_assignment(),
                "S001",
                "SELECT 1;",
                submission_key="browser-submit-001",
            )

    def test_different_recommendations_are_derived_from_stored_fixture_histories(self) -> None:
        fixture = self.journey.seed_fixture_histories()
        comparison = self.journey.profiles_and_recommendations()

        self.assertEqual(fixture["classification"], FIXTURE_HISTORY_LABEL)
        self.assertEqual(len(fixture["attempt_ids"]), 3)
        s001 = comparison["students"]["S001"]
        s002 = comparison["students"]["S002"]
        self.assertEqual(s001["profile"]["attempt_count"], 1)
        self.assertEqual(s002["profile"]["attempt_count"], 2)
        self.assertTrue(
            all(row["classification"] == FIXTURE_HISTORY_LABEL for row in s001["history_sources"])
        )
        self.assertTrue(
            all(row["classification"] == FIXTURE_HISTORY_LABEL for row in s002["history_sources"])
        )

        # Verify the cards are exactly the real recommender's result for profiles
        # reconstructed from persisted attempts, not student-ID-specific constants.
        self.assertEqual(
            s001["recommendation"], recommend_next_activity("S001", s001["profile"])
        )
        self.assertEqual(
            s002["recommendation"], recommend_next_activity("S002", s002["profile"])
        )
        self.assertEqual(s001["recommendation"]["recommended_question_id"], "sql_join_01")
        self.assertEqual(s002["recommendation"]["recommended_question_id"], "sql_join_04")
        self.assertNotEqual(
            s001["recommendation"]["recommended_question_id"],
            s002["recommendation"]["recommended_question_id"],
        )

        reopened = DemoStudentJourney(self.directory)
        self.assertEqual(reopened.submissions.profile("S002")["attempt_count"], 2)

    def test_assignment_path_is_accepted_and_unpublished_assignment_is_rejected(self) -> None:
        assignment_path = self.directory / "03_published_assignment.json"
        assignment_path.write_text(json.dumps(published_assignment()), encoding="utf-8")
        result = self.journey.submit(
            assignment_path,
            "S001",
            INNER_JOIN_HEADCOUNT_SQL,
            submission_key="path-submit",
            timestamp="2026-10-19T19:15:00Z",
        )
        self.assertEqual(result["assignment_id"], "assignment-left-headcount-demo")
        self.assertEqual(result["publication_status"], "PUBLISHED_LOCAL_DEMO")
        self.assertFalse(result["native_prairielearn_publication"])

        draft = published_assignment()
        draft["publication_status"] = "DRAFT"
        with self.assertRaisesRegex(ValueError, "published"):
            self.journey.submit(draft, "S001", INNER_JOIN_HEADCOUNT_SQL)

        misleading = published_assignment()
        misleading["native_prairielearn_publication"] = True
        with self.assertRaisesRegex(ValueError, "native_prairielearn_publication=False"):
            self.journey.submit(misleading, "S001", INNER_JOIN_HEADCOUNT_SQL)

    def test_explicit_repository_injection_uses_caller_stores(self) -> None:
        submissions = SubmissionRepository(self.directory / "custom-submissions.sqlite3")
        jobs = FeedbackJobRepository(self.directory / "custom-jobs.sqlite3")
        journey = DemoStudentJourney(submission_store=submissions, feedback_jobs=jobs)
        result = journey.submit(
            published_assignment(),
            "S001",
            INNER_JOIN_HEADCOUNT_SQL,
            submission_key="injected-store-submit",
            timestamp="2026-10-19T19:30:00Z",
        )
        self.assertEqual(submissions.records("S001")[0]["attempt_id"], result["attempt_id"])
        self.assertIsNotNone(jobs.get_by_attempt(result["attempt_id"]))

    def test_optional_em_reflection_creates_proposed_evidence_without_mastery_change(self) -> None:
        submission = self.journey.submit(
            published_assignment(),
            "S001",
            INNER_JOIN_HEADCOUNT_SQL,
            submission_key="em-reflection-submit",
            timestamp="2026-10-19T19:45:00Z",
        )
        profile_before = self.journey.submissions.profile("S001")
        reflection = self.journey.submit_em_reflection(
            "S001",
            submission["attempt_id"],
            "Omitting unstaffed departments can hide new initiatives and distort budget decisions.",
        )
        profile_after = self.journey.submissions.profile("S001")

        self.assertTrue(reflection["optional"])
        self.assertTrue(reflection["technical_mastery_separate"])
        self.assertEqual(reflection["prompt"]["question_id"], "sql_join_04")
        self.assertEqual(reflection["evidence"]["review_status"], "PROPOSED")
        self.assertEqual(reflection["evidence"]["attempt_id"], submission["attempt_id"])
        self.assertEqual(profile_after, profile_before)


if __name__ == "__main__":
    unittest.main()
