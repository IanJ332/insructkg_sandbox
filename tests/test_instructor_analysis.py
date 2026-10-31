import sys
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "prairielearn-course/serverFilesCourse")
)
from siip.instructor_analysis import analyze_attempt


class InstructorAnalysisTests(unittest.TestCase):
    def test_prior_scope_and_reviewed_prerequisites(self):
        current = {
            "attempt_id": "now",
            "student_id": "s1",
            "course_id": "c1",
            "timestamp": "2026-01-03",
            "concepts": ["JOIN"],
            "diagnosis": {"observed_error": "missing"},
        }

        def row(aid, student="s1", course="c1", when="2026-01-01"):
            return {
                "attempt_id": aid,
                "student_id": student,
                "course_id": course,
                "timestamp": when,
                "concepts": ["JOIN"],
                "grading": {"score": 0},
                "diagnosis": {"observed_error": "missing"},
            }

        graph = {
            "graph_id": "g",
            "version": 2,
            "source_document_id": "d",
            "source_version": 1,
            "edges": [
                {
                    "edge_id": "approved",
                    "source": "raw",
                    "target": "BASE",
                    "relation": "depends_on",
                    "review_state": "APPROVED",
                    "evidence_excerpt": "source",
                },
                {
                    "edge_id": "rejected",
                    "source": "raw",
                    "target": "OTHER",
                    "relation": "depends_on",
                    "review_state": "REJECTED",
                },
            ],
        }
        result = analyze_attempt(
            current,
            [
                row("a"),
                row("b"),
                row("other", student="s2"),
                row("course", course="c2"),
                row("same", when="2026-01-03"),
                row("later", when="2026-01-04"),
            ],
            graph,
            {"raw": "JOIN"},
        )
        self.assertEqual(result["prior_history"]["attempt_count"], 2)
        self.assertEqual(result["concept_history"][0]["attempt_ids"], ["a", "b"])
        self.assertEqual(result["repeated_prior_errors"][0]["prior_count"], 2)
        self.assertEqual([e["edge_id"] for e in result["reviewed_prerequisites"]], ["approved"])
        self.assertEqual(result["graph_provenance"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
