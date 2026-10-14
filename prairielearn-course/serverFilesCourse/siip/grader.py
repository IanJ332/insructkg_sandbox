import collections
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DATA = Path(os.environ.get("SIIP_DATA_DIR", Path(__file__).with_name("data")))
QUESTIONS = json.loads((DATA / "questions.json").read_text())


def run_query(sql, dataset, timeout=3, deadline_seconds=0.3):
    schema = (DATA / f"dataset_{dataset}.sql").read_text()
    try:
        with tempfile.TemporaryDirectory(prefix="siip-sql-") as directory:
            result = subprocess.run(
                [sys.executable, "-I", str(Path(__file__).with_name("sql_worker.py"))],
                input=json.dumps(
                    {"sql": sql, "schema": schema, "deadline_seconds": deadline_seconds}
                ),
                text=True,
                capture_output=True,
                timeout=timeout,
                cwd=directory,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            )
        if result.returncode:
            return {
                "status": "execution_error",
                "error": "SQL worker resource limit or process failure.",
            }
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"status": "execution_error", "error": "SQL worker timeout."}
    except (ValueError, OSError):
        return {"status": "execution_error", "error": "SQL worker unavailable."}


def bag(rows):
    return collections.Counter(tuple(row) for row in rows)


def grade(question_id, sql):
    question = QUESTIONS[question_id]
    results = []
    for dataset in ["A", "B"]:
        actual = run_query(sql, dataset)
        if actual["status"] != "ok":
            return {
                "status": actual["status"],
                "score": 0,
                "datasets": results,
                "error": actual["error"],
                "observation": actual["status"],
            }
        expected = run_query(question["reference_sql"], dataset)
        if expected["status"] != "ok":
            raise RuntimeError("Invalid reference query")
        got, want = bag(actual["rows"]), bag(expected["rows"])
        missing, unexpected = list((want - got).elements()), list((got - want).elements())
        ok = not missing and not unexpected and len(actual["columns"]) == len(expected["columns"])
        results.append(
            {
                "dataset": dataset,
                "correct": ok,
                "actual": actual,
                "expected": expected,
                "missing_rows": missing,
                "unexpected_rows": unexpected,
            }
        )
    correct = all(r["correct"] for r in results)
    observation = "correct" if correct else "result_mismatch"
    if (
        not correct
        and question_id == "sql_join_02"
        and all(not r["unexpected_rows"] for r in results)
        and any(r["missing_rows"] for r in results)
    ):
        observation = "missing_required_rows"
        if all(all(row[1] is None for row in r["missing_rows"]) for r in results):
            observation = "missing_unmatched_rows"
    elif not correct and question_id == "sql_join_03":
        b = results[1]
        if any(row[0] == "Gina" for row in b["missing_rows"]):
            observation = "missing_nonnull_unmatched_reference"
    return {
        "status": "correct" if correct else "semantic_error",
        "score": int(correct),
        "datasets": results,
        "observation": observation,
    }


def public_grade(result):
    """Never send hidden rows, reference SQL or raw engine error text to a model/student."""
    return {k: result[k] for k in ["status", "score", "observation"]}
