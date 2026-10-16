"""Authentic ANU Research Dataset Integration Tests.

Verifies integration with the locally installed ANU research database (Submission.sqlite).
These tests run against the authentic local research environment and are preserved
separately from deterministic public CI fixtures.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT))

from siip.authentic_history import ANU_DB_PATH, build_authentic_student_history


class AuthenticANUDatasetTests(unittest.TestCase):
    """Integration tests against the authentic local ANU SQLite dataset."""

    def setUp(self):
        if not ANU_DB_PATH.exists():
            self.fail(f"Authentic ANU database not found at expected path: {ANU_DB_PATH}")

    def test_authentic_student_history_extraction(self):
        # Target submission for Student 69 at 2018-08-12 21:00:21.819207+10
        hist = build_authentic_student_history(
            69, "2018-08-12 21:00:21.819207+10", db_path=ANU_DB_PATH
        )
        self.assertTrue(hist["has_valid_history"])
        self.assertEqual(hist["prior_attempts"], 6)
        self.assertEqual(hist["prior_submission_ids"], [162, 163, 164, 165, 166, 167])
        self.assertGreater(hist["excluded_future_records_count"], 0)
        self.assertIn("SELECT_PROJECTION", hist["concept_mastery"])

    def test_authentic_student_zero_prior_attempts(self):
        # Query before student's first attempt in authentic dataset
        hist = build_authentic_student_history(69, "2018-08-01 00:00:00+10", db_path=ANU_DB_PATH)
        self.assertFalse(hist["has_valid_history"])
        self.assertEqual(hist["prior_attempts"], 0)
        self.assertEqual(hist["concept_mastery"], {})
        self.assertGreater(hist["excluded_future_records_count"], 0)


if __name__ == "__main__":
    unittest.main()
