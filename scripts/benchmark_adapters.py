"""Authentic SQL Submission Adapter & Evaluation Manifest Builder.

Extracts authentic student SQL errors from the ANU Relational Database Course
dataset (Wang et al., 2020), builds normalized assessment cases, and creates
a reproducible evaluation manifest for controlled LLM feedback experiments.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

ANU_DB = Path("D:/AI/Datasets/SIIP/anu/Submission.sqlite")
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DATASETS = ROOT / "datasets/authentic_sql_eval_manifest.json"
OUTPUT_ARTIFACTS = ROOT / "artifacts/authentic_sql_eval_manifest.json"

# Exercises covering JOINs, Subqueries, Anti-joins, and Aggregations
TARGET_EXERCISES = [4, 5, 8, 9, 10, 11, 12, 13]


def extract_evaluation_manifest(target_count: int = 25) -> List[Dict[str, Any]]:
    if not ANU_DB.exists():
        raise FileNotFoundError(f"ANU database not found at {ANU_DB}")

    conn = sqlite3.connect(ANU_DB)
    cur = conn.cursor()

    # Load exercise metadata
    placeholders = ",".join("?" for _ in TARGET_EXERCISES)
    cur.execute(
        f"SELECT id, title, preamble, difficulty, ref FROM exercises_exercise WHERE id IN ({placeholders})",  # nosec B608
        TARGET_EXERCISES,
    )
    exercises = {
        row[0]: {
            "id": row[0],
            "title": row[1],
            "preamble": row[2].strip(),
            "difficulty": row[3],
            "ref_sql": row[4].strip(),
        }
        for row in cur.fetchall()
    }

    # Query partially correct authentic submissions with diverse students
    cur.execute(
        f"""
        SELECT submission_id, student_id, exercise_id, submitted_answer, submission_time, category
        FROM exercises_result
        WHERE category = 'partially correct'
          AND exercise_id IN ({placeholders})
          AND LENGTH(submitted_answer) > 25
          AND LENGTH(submitted_answer) < 800
        ORDER BY exercise_id, submission_id;
    """,  # nosec B608
        TARGET_EXERCISES,
    )
    all_errors = cur.fetchall()

    selected = []
    seen_students = set()
    per_exercise_count: Dict[int, int] = {e: 0 for e in TARGET_EXERCISES}
    max_per_exercise = 4

    for row in all_errors:
        sub_id, sid, eid, sql, sub_time, cat = row
        sql_clean = sql.strip()

        # Balance selection across exercises and distinct students
        if per_exercise_count[eid] >= max_per_exercise:
            continue
        if sid in seen_students and len(selected) < target_count - 5:
            continue

        ex_meta = exercises[eid]

        # Categorize primary error pattern based on syntactic and structural features
        sql_lower = sql_clean.lower()
        ref_lower = ex_meta["ref_sql"].lower()

        if "join" in ref_lower and "join" not in sql_lower and "," not in sql_lower:
            pattern = "missing_join"
        elif (
            "not exists" in ref_lower
            and "not exists" not in sql_lower
            and "not in" not in sql_lower
        ):
            pattern = "missing_anti_join_negation"
        elif "group by" in ref_lower and "group by" not in sql_lower:
            pattern = "missing_group_by_aggregation"
        elif "having" in ref_lower and "having" not in sql_lower:
            pattern = "missing_having_filter"
        elif "where" in ref_lower and "where" not in sql_lower:
            pattern = "missing_predicate_filter"
        elif "null" in sql_lower and "= null" in sql_lower:
            pattern = "null_equality_semantic_error"
        else:
            pattern = "semantic_projection_or_condition_error"

        eval_case = {
            "eval_id": f"eval-anu-{len(selected) + 1:03d}",
            "benchmark_source": "ANU Relational Database Course (Wang et al., 2020)",
            "license": "CC-BY 4.0",
            "exercise_id": eid,
            "exercise_title": ex_meta["title"],
            "difficulty": ex_meta["difficulty"],
            "question_prompt": ex_meta["preamble"],
            "reference_sql": ex_meta["ref_sql"],
            "submission_id": sub_id,
            "student_id": f"anu-student-{sid}",
            "submission_timestamp": sub_time,
            "authentic_student_sql": sql_clean,
            "ground_truth_category": cat,
            "structural_error_pattern": pattern,
            "pedagogical_concepts": infer_exercise_concepts(eid),
        }

        selected.append(eval_case)
        seen_students.add(sid)
        per_exercise_count[eid] += 1

        if len(selected) >= target_count:
            break

    conn.close()
    return selected


def infer_exercise_concepts(exercise_id: int) -> List[str]:
    mapping = {
        4: ["NATURAL_JOIN", "MULTI_TABLE_JOIN", "GROUP_BY", "HAVING"],
        5: ["INNER_JOIN", "PREDICATE_FILTERING", "STRING_NORMALIZATION"],
        8: ["SUBQUERY_IN_FROM", "MULTI_TABLE_JOIN", "EQUALITY_JOIN"],
        9: ["MULTI_TABLE_JOIN", "RANGE_PREDICATE", "COUNT_AGGREGATION"],
        10: ["COMPOUND_KEY_JOIN", "MULTI_TABLE_JOIN", "GROUP_BY", "HAVING"],
        11: ["ANTI_JOIN", "NOT_EXISTS", "UNION", "CORRELATED_SUBQUERY"],
        12: ["ANTI_JOIN", "NOT_EXISTS", "NULL_SEMANTICS"],
        13: ["NOT_IN", "SET_DIFFERENCE", "SUBQUERY_NEGATION", "NULL_HAZARD"],
    }
    return mapping.get(exercise_id, ["SQL_QUERY"])


def build_and_save_manifest() -> Dict[str, Any]:
    cases = extract_evaluation_manifest(target_count=25)
    manifest = {
        "metadata": {
            "title": "SIIP Authentic Student SQL Evaluation Benchmark Manifest",
            "version": "1.0.0",
            "created_at": "2026-10-15T01:00:00Z",
            "total_cases": len(cases),
            "primary_model": "qwen3:8b",
            "dataset": "ANU Relational Database Course (Wang et al., 2020)",
            "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
            "provenance": "D:/AI/Datasets/SIIP/anu/Submission.sqlite",
            "experimental_conditions": {
                "Condition_A": "Baseline LLM (Schema + Question text only)",
                "Condition_B": "Lecture RAG (Schema + Question + Lecture Excerpts)",
                "Condition_C": "Lecture RAG + KG (Schema + Question + Lecture + Concept Subgraph)",
                "Condition_D": "KG without prior student history",
                "Condition_E": "KG with authorized prior student history",
            },
        },
        "cases": cases,
    }

    OUTPUT_DATASETS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_ARTIFACTS.parent.mkdir(parents=True, exist_ok=True)

    formatted = json.dumps(manifest, indent=2) + "\n"
    OUTPUT_DATASETS.write_text(formatted, encoding="utf-8")
    OUTPUT_ARTIFACTS.write_text(formatted, encoding="utf-8")

    print(f"Generated manifest with {len(cases)} authentic SQL error cases.")
    print(f"Saved to: {OUTPUT_DATASETS}")
    print(f"Saved to: {OUTPUT_ARTIFACTS}")
    return manifest


if __name__ == "__main__":
    build_and_save_manifest()
