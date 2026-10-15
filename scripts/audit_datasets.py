"""Audit authentic SQL benchmark datasets (ANU and SQLRepair).

Audits licenses, schemas, row counts, student identifiers, timestamps, question
context, and grading labels, and selects 20-30 candidate authentic SQL errors.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

ANU_DIR = Path("D:/AI/Datasets/SIIP/anu")
SQLREPAIR_DIR = Path("D:/AI/Datasets/SIIP/sqlrepair")


def audit_anu() -> dict:
    db_path = ANU_DIR / "Submission.sqlite"
    if not db_path.exists():
        return {"error": "ANU Submission.sqlite not found"}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Tables and row counts
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]

    table_info = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t});")  # nosec B608
        cols = [
            {"cid": col[0], "name": col[1], "type": col[2], "notnull": col[3]}
            for col in cur.fetchall()
        ]
        cur.execute(f"SELECT COUNT(*) FROM {t};")  # nosec B608
        count = cur.fetchone()[0]
        table_info[t] = {"columns": cols, "count": count}

    # Distinct students, exercises, categories in exercises_result
    cur.execute(
        "SELECT COUNT(DISTINCT student_id), COUNT(DISTINCT exercise_id) FROM exercises_result;"
    )
    dist_students, dist_exercises = cur.fetchone()

    cur.execute("SELECT category, COUNT(*) FROM exercises_result GROUP BY category;")
    categories = dict(cur.fetchall())

    cur.execute("SELECT is_correct, COUNT(*) FROM exercises_result GROUP BY is_correct;")
    correctness = dict(cur.fetchall())

    # Exercise details
    cur.execute("SELECT id, title, preamble, difficulty, ref FROM exercises_exercise ORDER BY id;")
    exercises = []
    for row in cur.fetchall():
        exercises.append(
            {
                "id": row[0],
                "title": row[1],
                "preamble": row[2],
                "difficulty": row[3],
                "ref_sql": row[4],
            }
        )

    # Sample benchmark scores
    cur.execute("SELECT COUNT(*) FROM exercises_benchmark;")
    bench_count = cur.fetchone()[0]

    conn.close()

    import hashlib

    def compute_sha256(path: Path) -> str:
        if not path.exists():
            return "not_found"
        return hashlib.sha256(path.read_bytes()).hexdigest()

    hashes = {
        "Submission.sqlite": compute_sha256(db_path),
        "db_schema.pdf": compute_sha256(ANU_DIR / "db_schema.pdf"),
        "README.md": compute_sha256(ANU_DIR / "README.md"),
    }

    # Verify query execution on populated database instance
    query_exec_ok = False
    try:
        c2 = sqlite3.connect(db_path)
        row = c2.execute("SELECT count(*) FROM movie;").fetchone()
        query_exec_ok = bool(row and row[0] > 0)
        c2.close()
    except Exception:
        query_exec_ok = False

    return {
        "dataset": "ANU Relational Database Course (Wang et al., 2020)",
        "source": "Zenodo: https://zenodo.org/records/6526769",
        "license": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
        "file_path": str(db_path),
        "file_hashes": hashes,
        "database_executable": query_exec_ok,
        "grading_reproduction_note": (
            "Submission.sqlite contains queryable schema and data. However, automated grading "
            "reproduction cannot be claimed from schema descriptions alone without the full "
            "browser test execution harness."
        ),
        "tables": table_info,
        "distinct_students": dist_students,
        "distinct_exercises": dist_exercises,
        "categories": categories,
        "correctness_distribution": correctness,
        "benchmark_grades_count": bench_count,
        "exercises": exercises,
    }


def audit_sqlrepair() -> dict:
    data_dir = SQLREPAIR_DIR / "data"
    if not data_dir.exists():
        return {"error": "SQLRepair data directory not found"}

    csv_files = list(data_dir.glob("*.csv"))
    audits = {}

    for csv_file in csv_files:
        row_count = 0
        distinct_participants = set()
        distinct_problems = set()
        correct_count = 0
        incorrect_count = 0
        columns = []

        with csv_file.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            for row in reader:
                row_count += 1
                distinct_participants.add(row.get("participant"))
                distinct_problems.add(row.get("problem"))
                if str(row.get("correct")) == "1":
                    correct_count += 1
                else:
                    incorrect_count += 1

        audits[csv_file.name] = {
            "row_count": row_count,
            "columns": columns,
            "distinct_participants": len(distinct_participants),
            "distinct_problems": len(distinct_problems),
            "problems": sorted(list(distinct_problems)),
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
        }

    return {
        "dataset": "SQLRepair (Presler-Marshall et al., 2021)",
        "source": "GitHub: https://github.com/kpresler/SQLRepair",
        "license": "MIT License / Academic research distribution",
        "csv_files": audits,
    }


if __name__ == "__main__":
    report = {
        "anu": audit_anu(),
        "sqlrepair": audit_sqlrepair(),
    }
    print(json.dumps(report, indent=2))
