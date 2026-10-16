"""Deterministic Adaptive Next-Activity Recommender for Track A Synthetic Learners.

Selects the next best pedagogical task based on verified concept mastery,
historical error observations, and prerequisite sequencing without calling external LLMs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

RECOMMENDER_VERSION = "siip-adaptive-recommender-v1"

# Pedagogical prerequisite rules:
# 1. INNER_JOIN is prerequisite for LEFT_OUTER_JOIN
# 2. LEFT_OUTER_JOIN is prerequisite for NULL_SEMANTICS
# 3. Join mechanics are prerequisite for aggregation across incomplete records (sql_join_04)
QUESTION_METADATA = {
    "sql_join_01": {
        "title": "Inner join fundamentals",
        "concepts": ["INNER_JOIN", "JOIN_CONDITION"],
        "level": 1,
    },
    "sql_join_02": {
        "title": "Preserving unmatched records with LEFT JOIN",
        "concepts": ["LEFT_OUTER_JOIN"],
        "level": 2,
    },
    "sql_join_03": {
        "title": "Finding records with NULL foreign keys",
        "concepts": ["LEFT_OUTER_JOIN", "NULL_SEMANTICS"],
        "level": 3,
    },
    "sql_join_04": {
        "title": "Department headcount with unstaffed units",
        "concepts": ["LEFT_OUTER_JOIN", "NULL_SEMANTICS", "COUNT_AGGREGATION"],
        "level": 4,
    },
}


def recommend_next_activity(
    student_id: str,
    profile: Dict[str, Any],
    available_questions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Computes deterministic next-question recommendation based on learner profile.

    Heuristic policy:
    1. Mastery < 0.60 in INNER_JOIN -> recommend sql_join_01 (foundational inner join).
    2. Mastery >= 0.60 in INNER_JOIN but < 0.60 in LEFT_OUTER_JOIN -> recommend sql_join_02.
    3. Mastery >= 0.60 in LEFT_OUTER_JOIN but < 0.60 in NULL_SEMANTICS -> recommend sql_join_03.
    4. Mastery >= 0.60 in outer joins and nulls, but < 0.60 in COUNT_AGGREGATION -> recommend sql_join_04.
    5. All >= 0.60 -> recommend review of lowest mastery or advanced synthesis.
    """
    allowed_qids = available_questions or list(QUESTION_METADATA.keys())
    concepts_profile = profile.get("concepts", {})

    def get_mastery(concept_name: str) -> float:
        c_data = concepts_profile.get(concept_name)
        if isinstance(c_data, dict):
            est = c_data.get("mastery_estimate")
            if isinstance(est, (int, float)):
                return float(est)
        return 0.5  # neutral unobserved prior: (1+0)/(2+0) = 0.50

    inner_m = get_mastery("INNER_JOIN")
    left_m = get_mastery("LEFT_OUTER_JOIN")
    null_m = get_mastery("NULL_SEMANTICS")
    count_m = get_mastery("COUNT_AGGREGATION")

    mastery_snapshot = {
        "INNER_JOIN": round(inner_m, 3),
        "LEFT_OUTER_JOIN": round(left_m, 3),
        "NULL_SEMANTICS": round(null_m, 3),
        "COUNT_AGGREGATION": round(count_m, 3),
    }

    # Rule 1: Foundational inner join prerequisite
    if "sql_join_01" in allowed_qids and inner_m < 0.60:
        return {
            "student_id": student_id,
            "recommended_question_id": "sql_join_01",
            "question_title": QUESTION_METADATA["sql_join_01"]["title"],
            "target_concepts": QUESTION_METADATA["sql_join_01"]["concepts"],
            "rule_id": "RULE_PREREQ_INNER_JOIN",
            "rationale": (
                f"INNER_JOIN mastery is {inner_m:.2f} (< 0.60 threshold). "
                "Reinforce foundational join predicates and matching rows before proceeding to outer joins."
            ),
            "mastery_snapshot": mastery_snapshot,
            "provenance": RECOMMENDER_VERSION,
        }

    # Rule 2: Left outer join preservation
    if "sql_join_02" in allowed_qids and left_m < 0.60:
        return {
            "student_id": student_id,
            "recommended_question_id": "sql_join_02",
            "question_title": QUESTION_METADATA["sql_join_02"]["title"],
            "target_concepts": QUESTION_METADATA["sql_join_02"]["concepts"],
            "rule_id": "RULE_PREREQ_LEFT_OUTER_JOIN",
            "rationale": (
                f"INNER_JOIN is mastered ({inner_m:.2f}), but LEFT_OUTER_JOIN mastery is {left_m:.2f} (< 0.60). "
                "Practice preserving non-matching rows from the primary table."
            ),
            "mastery_snapshot": mastery_snapshot,
            "provenance": RECOMMENDER_VERSION,
        }

    # Rule 3: Null semantics in relational queries
    if "sql_join_03" in allowed_qids and null_m < 0.60:
        return {
            "student_id": student_id,
            "recommended_question_id": "sql_join_03",
            "question_title": QUESTION_METADATA["sql_join_03"]["title"],
            "target_concepts": QUESTION_METADATA["sql_join_03"]["concepts"],
            "rule_id": "RULE_PREREQ_NULL_SEMANTICS",
            "rationale": (
                f"Outer joins established ({left_m:.2f}), but NULL_SEMANTICS mastery is {null_m:.2f} (< 0.60). "
                "Practice three-valued logic and IS NULL filtering on unlinked foreign keys."
            ),
            "mastery_snapshot": mastery_snapshot,
            "provenance": RECOMMENDER_VERSION,
        }

    # Rule 4: Aggregation across incomplete records
    if "sql_join_04" in allowed_qids and count_m < 0.60:
        return {
            "student_id": student_id,
            "recommended_question_id": "sql_join_04",
            "question_title": QUESTION_METADATA["sql_join_04"]["title"],
            "target_concepts": QUESTION_METADATA["sql_join_04"]["concepts"],
            "rule_id": "RULE_PREREQ_COUNT_AGGREGATION",
            "rationale": (
                f"Join fundamentals mastered, but COUNT_AGGREGATION mastery is {count_m:.2f} (< 0.60). "
                "Practice combining outer joins with COUNT(column) to retain zero-headcount entities."
            ),
            "mastery_snapshot": mastery_snapshot,
            "provenance": RECOMMENDER_VERSION,
        }

    # Rule 5: Mastery synthesis / review lowest mastered concept
    min_concept, min_val = min(mastery_snapshot.items(), key=lambda kv: kv[1])
    target_qid = "sql_join_04" if "sql_join_04" in allowed_qids else allowed_qids[-1]
    return {
        "student_id": student_id,
        "recommended_question_id": target_qid,
        "question_title": QUESTION_METADATA[target_qid]["title"],
        "target_concepts": QUESTION_METADATA[target_qid]["concepts"],
        "rule_id": "RULE_MASTERY_SYNTHESIS",
        "rationale": (
            "All core relational concepts exceed the 0.60 mastery threshold. "
            f"Recommended advanced synthesis or dynamic personalized project to reinforce {min_concept} ({min_val:.2f})."
        ),
        "mastery_snapshot": mastery_snapshot,
        "provenance": RECOMMENDER_VERSION,
    }
