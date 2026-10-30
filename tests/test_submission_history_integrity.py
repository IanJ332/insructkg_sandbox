import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.store import SubmissionRepository


def attempt(aid, day, **extra):
    return {
        "attempt_id": aid,
        "student_id": "S001",
        "question_id": "sql_join_02",
        "submitted_sql": "SELECT name FROM Employees;",
        "timestamp": f"2026-01-{day:02}T00:00:00Z",
        **extra,
    }


class SubmissionHistoryIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = SubmissionRepository(Path(self.tmp.name) / "batch.sqlite")

    def test_batch_matches_sequential_and_keeps_input_order(self):
        early, later = attempt("early", 1), attempt("later", 2)
        batch = self.repo.process_many([later, early])
        sequential = SubmissionRepository(Path(self.tmp.name) / "sequential.sqlite")
        sequential.process(early)
        expected = sequential.process(later)
        self.assertEqual([r["attempt_id"] for r in batch], ["later", "early"])
        self.assertEqual(
            batch[0]["feedback"]["historical_personalization"],
            expected["feedback"]["historical_personalization"],
        )
        self.assertEqual(batch[1]["feedback"]["historical_personalization"]["status"], "none")

    def test_equal_time_and_duplicates_do_not_add_prior_evidence(self):
        early, same, later = attempt("early", 1), attempt("same", 1), attempt("later", 2)
        rows = self.repo.process_many([early, early, same, later])
        self.assertEqual(rows[2]["feedback"]["historical_personalization"]["status"], "none")
        self.assertEqual(self.repo.profile("S001")["attempt_count"], 3)
        self.assertEqual(
            self.repo.profile("S001", as_of=later["timestamp"], before=True)["attempt_count"], 2
        )
        with self.assertRaises(ValueError):
            self.repo.process_many([attempt("new", 3), attempt("new", 4)])
        self.assertEqual(self.repo.profile("S001")["attempt_count"], 3)

    def test_course_and_student_isolation_and_aggregate_compatibility(self):
        rows = self.repo.process_many(
            [
                attempt("a", 1, course_id="course-a"),
                attempt("b", 2, course_id="course-b"),
                attempt("legacy", 3),
                attempt("other", 4, student_id="S002", course_id="course-a"),
            ]
        )
        self.assertEqual(rows[1]["feedback"]["historical_personalization"]["status"], "none")
        self.assertEqual(rows[2]["feedback"]["historical_personalization"]["status"], "none")
        self.assertEqual(self.repo.profile("S001")["attempt_count"], 3)
        for course in ("course-a", "course-b", None):
            self.assertEqual(self.repo.profile("S001", course_id=course)["attempt_count"], 1)
        with self.assertRaises(ValueError):
            self.repo.process(attempt("a", 1, course_id="course-b"))
        with self.assertRaises(ValueError):
            self.repo.process(attempt("invalid", 5, course_id="bad course"))


if __name__ == "__main__":
    unittest.main()
