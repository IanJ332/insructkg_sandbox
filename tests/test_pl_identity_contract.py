"""Synthetic contract tests for PrairieLearn identity access, safety boundaries, and grading invariance."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.grader import QUESTIONS
from siip.pl_bridge import grade_question
from siip.sources import normalize_pl

QID = "sql_join_02"
GOOD_SQL = QUESTIONS[QID]["reference_sql"]
BAD_SQL = QUESTIONS["sql_join_01"]["reference_sql"]


class TestPrairieLearnIdentityContract(unittest.TestCase):
    """Verifies rules governing data['options']['user'] and grading invariance."""

    def test_grading_invariance_with_or_without_user_identity(self):
        """Grading score must be strictly identical regardless of whether student identity is provided."""
        # 1. Payload with NO user identity (standard default in PrairieLearn)
        data_anonymous = {
            "submitted_answers": {"sql": BAD_SQL},
            "options": {},
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data_anonymous, QID)

        # 2. Payload WITH user identity (course opt-in with questionsReceiveUserData)
        data_with_identity = {
            "submitted_answers": {"sql": BAD_SQL},
            "options": {
                "user": {
                    "user_id": 101,
                    "uid": "synthetic_student@illinois.edu",
                    "uin": "123456789",
                    "name": "Synthetic Student",
                }
            },
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data_with_identity, QID)

        # Invariance check: scores and deterministic status must match exactly
        self.assertEqual(data_anonymous["score"], data_with_identity["score"])
        self.assertEqual(data_anonymous["score"], 0.0)
        self.assertEqual(
            data_anonymous["feedback"]["status"],
            data_with_identity["feedback"]["status"],
        )
        self.assertEqual(
            data_anonymous["feedback"]["siip"]["observation"],
            data_with_identity["feedback"]["siip"]["observation"],
        )

    def test_raw_pii_never_persisted_in_feedback_payload(self):
        """Raw identity fields (uid, uin, name, email) must never leak into feedback, receipts, or context."""
        sensitive_email = "sensitive_netid@illinois.edu"
        sensitive_uin = "987654321"
        sensitive_name = "Real Student Name"

        data = {
            "submitted_answers": {"sql": BAD_SQL},
            "options": {
                "user": {
                    "user_id": 101,
                    "uid": sensitive_email,
                    "uin": sensitive_uin,
                    "name": sensitive_name,
                }
            },
            "partial_scores": {},
            "feedback": {},
        }
        grade_question(data, QID)

        feedback_json = json.dumps(data["feedback"])
        self.assertNotIn(sensitive_email, feedback_json)
        self.assertNotIn(sensitive_uin, feedback_json)
        self.assertNotIn(sensitive_name, feedback_json)

    def test_course_options_questions_receive_user_data_flag(self):
        """Verify parsing of course-level opt-in options schema."""
        course_config_default = {
            "name": "SIIP SQL",
            "timezone": "America/Chicago",
        }
        # By default, questionsReceiveUserData is False
        self.assertFalse(
            course_config_default.get("options", {}).get("questionsReceiveUserData", False)
        )

        course_config_optin = {
            "name": "SIIP SQL",
            "options": {"questionsReceiveUserData": True},
        }
        self.assertTrue(
            course_config_optin.get("options", {}).get("questionsReceiveUserData", False)
        )

    def test_group_assessment_isolation(self):
        """Group submissions have group_id, not individual user identity; must fail closed for individual profiles."""
        group_record = {
            "submission_id": "501",
            "user_id": None,
            "group_id": "G42",
            "question_name": QID,
            "assessment_id": "7000",
            "assessment_instance_id": "9000",
            "variant_id": "8000",
            "date": "2026-10-14T11:00:00Z",
            "submitted_answer": {"sql": GOOD_SQL},
            "score": 1,
        }
        identity_map = {"101": "S001"}
        # Must raise ValueError: individual personalization cannot silently consume group records
        with self.assertRaises(ValueError) as ctx:
            normalize_pl(group_record, identity_map)
        self.assertIn("Individual submissions only", str(ctx.exception))

    def test_pseudonymized_identity_mapping_closed_on_unknown_id(self):
        """Submission normalization fails closed if numeric user_id is unmapped."""
        record = {
            "submission_id": "502",
            "user_id": "999",  # Unmapped user
            "group_id": None,
            "question_name": QID,
            "assessment_id": "7000",
            "assessment_instance_id": "9000",
            "variant_id": "8000",
            "date": "2026-10-14T11:00:00Z",
            "submitted_answer": {"sql": GOOD_SQL},
            "score": 1,
        }
        identity_map = {"101": "S001"}
        with self.assertRaises(ValueError) as ctx:
            normalize_pl(record, identity_map)
        self.assertIn("Missing authorized pseudonymous identity mapping", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
