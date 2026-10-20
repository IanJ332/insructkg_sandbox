import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.feedback import generate_feedback
from siip.grader import grade

INCORRECT_HEADCOUNT_SQL = (
    "SELECT d.department_name, COUNT(e.employee_id) AS employee_count "
    "FROM Departments d INNER JOIN Employees e ON d.department_id=e.department_id "
    "GROUP BY d.department_id,d.department_name ORDER BY d.department_name"
)


class DemoFeedbackIntegrationTests(unittest.TestCase):
    def test_q04_kg_fallback_preserves_leakage_guard_with_safe_graph_labels(self):
        grading = grade("sql_join_04", INCORRECT_HEADCOUNT_SQL)
        self.assertEqual(grading["score"], 0)

        feedback = generate_feedback("sql_join_04", INCORRECT_HEADCOUNT_SQL, grading, "kg")

        self.assertEqual(feedback["inference_status"], "deterministic_fallback")
        self.assertIn("query projection structure", feedback["feedback_text"])
        self.assertNotRegex(feedback["feedback_text"].lower(), r"\bselect\b")
        self.assertIn("LEFT_OUTER_JOIN", feedback["candidate_concepts"])
        self.assertNotIn("COUNT_AGGREGATION", feedback["candidate_concepts"])
        self.assertNotIn("GROUP_BY", feedback["candidate_concepts"])
        self.assertNotIn("count aggregation", feedback["feedback_text"].lower())


if __name__ == "__main__":
    unittest.main()
