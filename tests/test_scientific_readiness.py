"""Deterministic Unit Tests for Phase 4.4 Scientific Evaluation Readiness.

Tests EvidenceRegistry, Authentic Prior History Extraction, Blinded Review Generation,
Output Validation, and Statistical Analysis without requiring live inference or external APIs.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT))

import sqlite3
import tempfile

from siip.authentic_history import build_authentic_student_history
from siip.evidence_registry import EvidenceRegistry

from scripts.analyze_results import (
    compute_descriptive_stats,
    compute_paired_comparison,
)
from scripts.experiment_runner import (
    build_condition_prompts,
    prepare_blind_review_packet,
    validate_model_output,
)


class TestAuthenticStudentHistory(unittest.TestCase):
    """Verifies that student histories are strictly temporal using a purpose-built SQLite fixture."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="siip-history-test-")
        cls.fixture_db_path = Path(cls.temp_dir.name) / "Submission_fixture.sqlite"
        conn = sqlite3.connect(cls.fixture_db_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE exercises_result (
                submission_id INTEGER PRIMARY KEY,
                student_id INTEGER,
                exercise_id INTEGER,
                is_correct INTEGER,
                category TEXT,
                submission_time TEXT
            );
            """
        )
        sample_rows = [
            (162, 69, 1, 0, "partially correct", "2018-08-12 20:14:57.946042+10"),
            (163, 69, 1, 1, "correct", "2018-08-12 20:28:16.418559+10"),
            (164, 69, 2, 0, "partially correct", "2018-08-12 20:31:05.505491+10"),
            (165, 69, 2, 0, "partially correct", "2018-08-12 20:31:48.024731+10"),
            (166, 69, 2, 1, "correct", "2018-08-12 20:39:31.176388+10"),
            (167, 69, 12, 1, "correct", "2018-08-12 20:45:57.846334+10"),
            (168, 69, 4, 0, "partially correct", "2018-08-12 21:00:21.819207+10"),
            (172, 69, 4, 1, "correct", "2018-08-12 22:18:13.078619+10"),
            (173, 69, 5, 0, "partially correct", "2018-08-12 22:23:01.309167+10"),
            (180, 69, 5, 1, "correct", "2018-08-12 22:48:30.014202+10"),
        ]
        cur.executemany(
            "INSERT INTO exercises_result VALUES (?, ?, ?, ?, ?, ?);",
            sample_rows,
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_strict_temporal_cutoff(self):
        # Student 69 at 2018-08-12 21:00:21.819207+10 has exactly 6 prior submissions
        hist = build_authentic_student_history(
            69, "2018-08-12 21:00:21.819207+10", db_path=self.fixture_db_path
        )
        self.assertTrue(hist["has_valid_history"])
        self.assertEqual(hist["prior_attempts"], 6)
        self.assertEqual(hist["prior_submission_ids"], [162, 163, 164, 165, 166, 167])
        # Future submissions must be strictly excluded
        self.assertEqual(hist["excluded_future_records_count"], 4)
        self.assertIn("SELECT_PROJECTION", hist["concept_mastery"])

    def test_student_with_zero_prior_attempts(self):
        # A timestamp before the student's first attempt yields zero prior attempts
        hist = build_authentic_student_history(
            69, "2018-08-01 00:00:00+10", db_path=self.fixture_db_path
        )
        self.assertFalse(hist["has_valid_history"])
        self.assertEqual(hist["prior_attempts"], 0)
        self.assertEqual(hist["concept_mastery"], {})
        self.assertEqual(hist["excluded_future_records_count"], 10)


class TestEvidenceRegistry(unittest.TestCase):
    """Verifies Evidence Registry categorization, source hashing, and eligibility checking."""

    def setUp(self):
        self.registry = EvidenceRegistry()

    def test_registered_evidence_items(self):
        self.assertGreaterEqual(len(self.registry.items), 9)
        # Check that provisional relations are strictly labeled unreviewed
        for it in self.registry.items.values():
            if it.evidence_kind == "developer_provisional":
                self.assertEqual(it.instructor_approval_status, "unreviewed")
            elif it.evidence_kind == "synthetic_fixture":
                self.assertEqual(it.instructor_approval_status, "synthetic_fixture")

    def test_instructor_aligned_eligibility_fails_closed(self):
        # Any ANU case without instructor-approved edges must fail closed
        case = {
            "exercise_id": 4,
            "pedagogical_concepts": ["NATURAL_JOIN", "GROUP_BY"],
        }
        eligible, reason, details = self.registry.check_instructor_aligned_eligibility(case)
        self.assertFalse(eligible)
        self.assertIn("0 instructor-approved", reason)
        self.assertEqual(details["instructor_approved_kg_edges"], 0)


class TestExperimentRunnerBlindingAndValidation(unittest.TestCase):
    """Verifies prompt construction, output validation, and single-blind review packets."""

    def setUp(self):
        self.registry = EvidenceRegistry()
        self.sample_case = {
            "eval_id": "eval-anu-001",
            "student_id": "anu-student-69",
            "exercise_id": 4,
            "exercise_title": "SQL Exercise 4",
            "question_prompt": "Find directors who directed movies written by themselves.",
            "authentic_student_sql": "SELECT id FROM person WHERE id IN (SELECT id FROM director);",
            "reference_sql": "SELECT d.id FROM director d NATURAL JOIN writer w GROUP BY d.id HAVING count(*) > 1;",
            "pedagogical_concepts": ["NATURAL_JOIN", "GROUP_BY", "HAVING"],
            "authentic_prior_history": {
                "has_valid_history": True,
                "prior_attempts": 6,
                "concept_mastery": {"NATURAL_JOIN": {"mastery_estimate": 0.5}},
            },
        }

    def test_controlled_prompts_hold_task_and_sql_constant(self):
        prompts = build_condition_prompts(self.sample_case, self.registry)
        self.assertEqual(set(prompts.keys()), {"A", "B", "C", "D", "E"})

        # Task, Schema, and Student SQL must be identical across A, B, C
        for cond in ["A", "B", "C"]:
            self.assertEqual(
                prompts[cond]["context"]["task_description"], self.sample_case["question_prompt"]
            )
            self.assertEqual(
                prompts[cond]["context"]["student_submission"],
                self.sample_case["authentic_student_sql"],
            )
            self.assertEqual(prompts[cond]["context"]["student_history"], "None")

        # Condition E must receive genuine history, while D receives no history
        self.assertEqual(prompts["D"]["context"]["student_history"]["status"], "no_prior_history")
        self.assertEqual(
            prompts["E"]["context"]["student_history"]["status"], "authentic_prior_history"
        )
        self.assertEqual(prompts["E"]["context"]["student_history"]["prior_attempts"], 6)

    def test_output_validation_detects_leakage_and_malformed(self):
        # Valid output
        valid_json = json.dumps(
            {
                "observed_error": "Missing join condition",
                "candidate_concepts": ["NATURAL_JOIN"],
                "guidance_hint": "Consider how person, director, and writer tables relate.",
                "evidence_citations": ["db_schema.pdf"],
            }
        )
        ok, parsed, flags = validate_model_output(
            valid_json, self.sample_case["authentic_student_sql"], self.sample_case["reference_sql"]
        )
        self.assertTrue(ok)
        self.assertEqual(flags, [])

        # Leakage with SELECT keyword
        leaking_json = json.dumps(
            {
                "observed_error": "Wrong projection",
                "candidate_concepts": ["NATURAL_JOIN"],
                "guidance_hint": "You should use SELECT d.id FROM director to get the right id.",
                "evidence_citations": [],
            }
        )
        ok, _, flags = validate_model_output(
            leaking_json,
            self.sample_case["authentic_student_sql"],
            self.sample_case["reference_sql"],
        )
        self.assertFalse(ok)
        self.assertIn("answer_leakage:prohibited_select_keyword", flags)

    def test_blind_review_packet_isolates_conditions_and_prompts(self):
        packet = prepare_blind_review_packet([self.sample_case], seed=123)
        self.assertEqual(len(packet["review_cases"]), 1)
        case_entry = packet["review_cases"][0]

        # Reviewer facing entry must NOT contain condition names or prompt structures
        variants = case_entry["variants"]
        self.assertEqual(len(variants), 5)
        for v in variants:
            self.assertIn("blind_id", v)
            self.assertTrue(v["blind_id"].startswith("resp-"))
            # Must not expose Condition A/B/C/D/E labels in variant keys
            self.assertNotIn("condition", v)
            self.assertNotIn("actual_condition", v)
            self.assertNotIn("system_prompt", v)


class TestStatisticalAnalysis(unittest.TestCase):
    """Verifies descriptive stats, paired tests, effect sizes, and pairwise deletion."""

    def test_descriptive_stats(self):
        data = [3.0, 4.0, 5.0, 4.0, 4.0]
        stats = compute_descriptive_stats(data)
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["mean"], 4.0)
        self.assertEqual(stats["median"], 4.0)
        self.assertEqual(stats["min"], 3.0)
        self.assertEqual(stats["max"], 5.0)
        self.assertEqual(len(stats["ci_95"]), 2)

    def test_paired_comparison_computes_cohens_d(self):
        pairs = [(4.0, 3.0), (5.0, 3.0), (4.0, 2.0), (3.0, 3.0), (4.0, 2.0)]
        comp = compute_paired_comparison(pairs, "Cond_X", "Cond_Y")
        self.assertEqual(comp["n_pairs"], 5)
        self.assertGreater(comp["mean_difference"], 0)
        self.assertGreater(comp["cohens_d"], 0)
        self.assertIsNotNone(comp["wilcoxon_p_value"])

    def test_pairwise_deletion_handles_missing_ratings(self):
        pairs = [(4.0, 3.0), (None, 2.0), (5.0, None), (3.0, 3.0)]
        comp = compute_paired_comparison(pairs, "Cond_X", "Cond_Y")
        # Only the 2 complete pairs should be analyzed
        self.assertEqual(comp["n_pairs"], 2)


if __name__ == "__main__":
    unittest.main()
