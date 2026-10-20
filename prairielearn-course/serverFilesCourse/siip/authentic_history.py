"""Authentic Student History Builder for ANU Benchmark Evaluation.

Extracts genuine temporal submission records from the ANU Relational Database
Course dataset (Wang et al., 2020), ensuring strict temporal causality:
only submissions recorded strictly before each target submission timestamp
are included in student learner profiles. Future records are explicitly excluded.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

ANU_DB_PATH = Path("D:/AI/Datasets/SIIP/anu/Submission.sqlite")

# Exercise to concepts mapping for ANU course exercises
EXERCISE_CONCEPT_MAP: Dict[int, List[str]] = {
    1: ["SELECT_PROJECTION", "SUBQUERY_SCALAR", "MAX_AGGREGATION"],
    2: ["SELECT_PROJECTION", "PREDICATE_FILTERING", "SUBQUERY_SCALAR"],
    3: ["MULTI_TABLE_JOIN", "PREDICATE_FILTERING"],
    4: ["NATURAL_JOIN", "MULTI_TABLE_JOIN", "GROUP_BY", "HAVING"],
    5: ["INNER_JOIN", "PREDICATE_FILTERING", "STRING_NORMALIZATION"],
    6: ["MULTI_TABLE_JOIN", "PREDICATE_FILTERING", "COUNT_AGGREGATION"],
    7: ["MULTI_TABLE_JOIN", "GROUP_BY", "COUNT_AGGREGATION"],
    8: ["SUBQUERY_IN_FROM", "MULTI_TABLE_JOIN", "EQUALITY_JOIN"],
    9: ["MULTI_TABLE_JOIN", "RANGE_PREDICATE", "COUNT_AGGREGATION"],
    10: ["COMPOUND_KEY_JOIN", "MULTI_TABLE_JOIN", "GROUP_BY", "HAVING"],
    11: ["ANTI_JOIN", "NOT_EXISTS", "UNION", "CORRELATED_SUBQUERY"],
    12: ["ANTI_JOIN", "NOT_EXISTS", "NULL_SEMANTICS"],
    13: ["NOT_IN", "SET_DIFFERENCE", "SUBQUERY_NEGATION", "NULL_HAZARD"],
    14: ["DERIVED_TABLES", "UNION", "MAX_AGGREGATION", "GROUP_BY"],
    15: ["MULTI_TABLE_JOIN", "GROUP_BY", "COUNT_AGGREGATION", "MAX_AGGREGATION"],
}


def build_authentic_student_history(
    student_id_raw: Any,
    target_submission_time: str,
    target_submission_id: Optional[int] = None,
    db_path: Path = ANU_DB_PATH,
) -> Dict[str, Any]:
    """Builds a genuine student history strictly prior to target_submission_time.

    Args:
        student_id_raw: Student identifier (int or 'anu-student-X')
        target_submission_time: ISO-like timestamp string from ANU dataset
        target_submission_id: Optional submission_id to ensure exact exclusion
        db_path: Path to ANU Submission.sqlite

    Returns:
        Structured profile documenting prior attempts, excluded future records,
        and concept mastery estimates.
    """
    if not db_path.exists():
        return {
            "status": "database_not_found",
            "has_valid_history": False,
            "prior_attempts": 0,
            "concept_mastery": {},
            "historical_observation_count": 0,
            "excluded_future_records_count": 0,
        }

    # Normalize student ID to integer for ANU DB query
    if isinstance(student_id_raw, str):
        sid_str = student_id_raw.replace("anu-student-", "")
        try:
            sid = int(sid_str)
        except ValueError:
            return {
                "status": "invalid_student_id",
                "has_valid_history": False,
                "prior_attempts": 0,
                "concept_mastery": {},
            }
    else:
        sid = int(student_id_raw)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Fetch strictly prior submissions
    cur.execute(
        """
        SELECT submission_id, exercise_id, is_correct, category, submission_time
        FROM exercises_result
        WHERE student_id = ?
          AND submission_time < ?
        ORDER BY submission_time ASC, submission_id ASC;
        """,
        (sid, target_submission_time),
    )
    prior_rows = cur.fetchall()

    # 2. Fetch excluded concurrent / future submissions (to audit leakage prevention)
    cur.execute(
        """
        SELECT submission_id, exercise_id, is_correct, category, submission_time
        FROM exercises_result
        WHERE student_id = ?
          AND submission_time >= ?
        ORDER BY submission_time ASC, submission_id ASC;
        """,
        (sid, target_submission_time),
    )
    future_rows = cur.fetchall()
    conn.close()

    if not prior_rows:
        return {
            "status": "no_prior_history",
            "student_id": f"anu-student-{sid}",
            "has_valid_history": False,
            "prior_attempts": 0,
            "concept_mastery": {},
            "prior_submission_ids": [],
            "historical_observation_count": 0,
            "excluded_future_records_count": len(future_rows),
            "profile_computation_version": "anu-authentic-temporal-v1",
        }

    prior_sub_ids = [r[0] for r in prior_rows]
    distinct_exercises = sorted(list(set(r[1] for r in prior_rows)))
    total_correct = sum(1 for r in prior_rows if r[2] == 1)

    # 3. Compute empirical concept mastery estimates from prior submissions
    concept_stats: Dict[str, Dict[str, int]] = {}
    for sub_id, ex_id, is_corr, cat, sub_time in prior_rows:
        concepts = EXERCISE_CONCEPT_MAP.get(ex_id, [])
        for c in concepts:
            if c not in concept_stats:
                concept_stats[c] = {"attempts": 0, "correct": 0}
            concept_stats[c]["attempts"] += 1
            if is_corr == 1:
                concept_stats[c]["correct"] += 1

    concept_mastery: Dict[str, Dict[str, Any]] = {}
    for c, stats in concept_stats.items():
        att = stats["attempts"]
        cor = stats["correct"]
        # Bayesian Beta estimate with uniform prior Beta(1, 1): (correct + 1) / (attempts + 2)
        estimate = round((cor + 1.0) / (att + 2.0), 3)
        concept_mastery[c] = {
            "mastery_estimate": estimate,
            "attempt_count": att,
            "success_count": cor,
            "empirical_success_rate": round(cor / att, 3) if att > 0 else 0.0,
        }

    return {
        "status": "authentic_prior_history",
        "student_id": f"anu-student-{sid}",
        "has_valid_history": True,
        "prior_attempts": len(prior_rows),
        "prior_submission_ids": prior_sub_ids,
        "historical_observation_count": len(prior_rows),
        "distinct_exercises_attempted": distinct_exercises,
        "prior_overall_accuracy": round(total_correct / len(prior_rows), 3),
        "concept_mastery": concept_mastery,
        "excluded_future_records_count": len(future_rows),
        "target_submission_time": target_submission_time,
        "profile_computation_version": "anu-authentic-temporal-v1",
    }
