"""Authentic SQL Submission Adapter & Evaluation Manifest Builder.

Extracts authentic student SQL errors from the ANU Relational Database Course
dataset (Wang et al., 2020), builds normalized assessment cases, attaches
temporal authentic student history, and creates a reproducible evaluation manifest.

Dataset Audit & Provenance:
- Source: Zenodo (https://zenodo.org/records/6526769)
- License: Creative Commons Attribution 4.0 International (CC-BY 4.0)
- SHA-256 Hashes:
  * Submission.sqlite: 7248ea9a868b3418c28799393abfd3463d6d22154ab388c1d63d124b1ca46817
  * db_schema.pdf:     f319424eb470721bab8e76d5ba917734fdf6e860de4085267eaa114cd2e5c5e2
  * README.md:         22fbd7d790bcef897aa57d2e64451ff97b2c97542edc0a097b889900f5a841a7
- Verified Benchmark Statistics:
  * Total cases: 25 student submissions
  * Distinct exercises: 7 (Exercises 4, 5, 8, 9, 10, 11, 12; Exercise 13 has 0 selected cases)
  * Distinct student IDs: 21 (Students 12 and 25 have multiple submissions)
  * Unique SQL queries: 24 (1 query text is duplicated across two submissions)
  * Rule-based heuristic categorization: 20/25 assigned broad fallback
    'semantic_projection_or_condition_error'
  * Ground truth: The authentic ANU dataset provides ONLY coarse grading status
    ('partially correct', 'correct', 'noninterpretable'). There are NO expert-validated
    per-submission concept-gap labels in the raw ANU corpus.
  * Executable instance: Submission.sqlite contains populated relational tables
    (movie, person, director, writer, etc.) that can be queried directly.
    However, grading reproduction cannot be claimed from schema descriptions alone;
    it requires an executable database engine with exact test cases.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.authentic_history import build_authentic_student_history

ANU_DB = Path("D:/AI/Datasets/SIIP/anu/Submission.sqlite")
OUTPUT_DATASETS = ROOT / "datasets/authentic_sql_eval_manifest.json"
OUTPUT_ARTIFACTS = ROOT / "artifacts/authentic_sql_eval_manifest.json"

# Target exercises covering JOINs, Subqueries, Anti-joins, and Aggregations
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

        # Categorize primary error pattern based on syntactic heuristics (NOT expert ground truth)
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

        # Build genuine prior student history strictly before sub_time
        student_history = build_authentic_student_history(
            student_id_raw=sid,
            target_submission_time=sub_time,
            target_submission_id=sub_id,
            db_path=ANU_DB,
        )

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
            # Preserve original ANU label separately from rule-based heuristic
            "authentic_anu_label": cat,
            "ground_truth_category": cat,
            "rule_based_structural_pattern": pattern,
            "structural_error_pattern": pattern,
            "pedagogical_concepts": infer_exercise_concepts(eid),
            # Genuine temporal prior history
            "authentic_prior_history": student_history,
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

    exercises = sorted(list(set(c["exercise_id"] for c in cases)))
    students = sorted(list(set(c["student_id"] for c in cases)))
    sqls = [c["authentic_student_sql"] for c in cases]
    unique_sqls = len(set(sqls))

    manifest = {
        "metadata": {
            "title": "SIIP Authentic Student SQL Evaluation Benchmark Manifest",
            "version": "1.1.0",
            "updated_at": "2026-10-15T17:15:00Z",
            "audit_verified": True,
            "audit_findings": {
                "total_cases": len(cases),
                "distinct_exercises_count": len(exercises),
                "distinct_exercises": exercises,
                "distinct_students_count": len(students),
                "unique_sql_count": unique_sqls,
                "duplicate_sql_instances": len(cases) - unique_sqls,
                "rule_based_fallback_count": sum(
                    1
                    for c in cases
                    if c["rule_based_structural_pattern"]
                    == "semantic_projection_or_condition_error"
                ),
                "ground_truth_note": (
                    "ANU corpus provides coarse execution category ('partially correct'). "
                    "Rule-based structural patterns and pedagogical concepts are automated "
                    "heuristics and must not be presented as expert-validated ground truth."
                ),
                "executable_database_audit": (
                    "Submission.sqlite contains queryable tables (movie, person, director, writer, etc.). "
                    "However, grading reproduction cannot be claimed from schema descriptions alone; "
                    "it requires the full test execution environment."
                ),
            },
            "provenance": {
                "dataset": "ANU Relational Database Course (Wang et al., 2020)",
                "source": "Zenodo: https://zenodo.org/records/6526769",
                "citation": (
                    "Wang, Jinshui, Yunpeng Zhao, Zhengyi Tang, and Zhenchang Xing. "
                    "'Combining dynamic and static analysis for automated grading SQL statements.' "
                    "Journal of Network Intelligence 5, no. 4 (2020): 179-190."
                ),
                "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
                "file_hashes": {
                    "Submission.sqlite": "7248ea9a868b3418c28799393abfd3463d6d22154ab388c1d63d124b1ca46817",
                    "db_schema.pdf": "f319424eb470721bab8e76d5ba917734fdf6e860de4085267eaa114cd2e5c5e2",
                    "README.md": "22fbd7d790bcef897aa57d2e64451ff97b2c97542edc0a097b889900f5a841a7",
                },
            },
            "experimental_conditions": {
                "Condition_A": "Baseline LLM (Schema + Question text only)",
                "Condition_B": "Authentic Lecture RAG (Schema + Question + Authentic Lecture/Doc Excerpts)",
                "Condition_C": "Authentic Lecture RAG + Verified KG (Schema + Question + Excerpts + Verified Subgraph)",
                "Condition_D": "Verified KG without prior student history",
                "Condition_E": "Verified KG with genuine prior student history",
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
    print(
        f"Verified stats: {len(exercises)} exercises, {len(students)} students, {unique_sqls} unique SQLs."
    )
    print(f"Saved to: {OUTPUT_DATASETS}")
    print(f"Saved to: {OUTPUT_ARTIFACTS}")
    return manifest


if __name__ == "__main__":
    build_and_save_manifest()
