import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.grader import QUESTIONS
from siip.sources import SyntheticFixtureSource
from siip.store import STUDENTS, SubmissionRepository

correct = {qid: q["reference_sql"] for qid, q in QUESTIONS.items()}
inner = correct["sql_join_01"]
null_only = "SELECT name FROM Employees WHERE department_id IS NULL;"
cartesian = "SELECT e.name, d.department_name FROM Employees e, Departments d;"
activities = {
    "S001": [
        ("sql_join_01", inner),
        ("sql_join_02", correct["sql_join_02"]),
        ("sql_join_03", correct["sql_join_03"]),
    ],
    "S002": [
        ("sql_join_01", inner),
        ("sql_join_02", inner),
        ("sql_join_03", null_only),
        ("sql_join_02", inner),
    ],
    "S003": [
        ("sql_join_01", cartesian),
        ("sql_join_01", inner),
        ("sql_join_02", inner),
        ("sql_join_02", correct["sql_join_02"]),
        ("sql_join_03", correct["sql_join_03"]),
    ],
    "S004": [
        ("sql_join_01", inner),
        ("sql_join_02", correct["sql_join_02"]),
        ("sql_join_03", null_only),
        ("sql_join_03", null_only),
    ],
    "S005": [
        ("sql_join_01", cartesian),
        ("sql_join_01", "SELEC name FROM Employees"),
        ("sql_join_02", inner),
        ("sql_join_03", null_only),
        ("sql_join_03", "SELECT name FROM MissingTable;"),
    ],
}
records = []
for sid, sequence in activities.items():
    for i, (qid, sql) in enumerate(sequence, 1):
        records.append(
            {
                "student_id": sid,
                "assessment_id": "sql-sandbox",
                "question_id": qid,
                "attempt_id": f"fixture-{sid}-{i:02}",
                "timestamp": f"2026-10-13T{8 + int(sid[-1]):02}:{i * 5:02}:00-05:00",
                "submitted_sql": sql,
                "source": "synthetic_fixture",
            }
        )
path = ROOT / "datasets/synthetic-submissions/attempts.json"
path.write_text(json.dumps(records, indent=2) + "\n")
(ROOT / "datasets/synthetic-students/students.json").write_text(
    json.dumps([{"student_id": s, "synthetic": True} for s in STUDENTS], indent=2) + "\n"
)
repo = SubmissionRepository(ROOT / "artifacts/synthetic.sqlite3")
for record in SyntheticFixtureSource(path).records():
    repo.process(record)
(ROOT / "artifacts/synthetic_results.json").write_text(json.dumps(repo.records(), indent=2) + "\n")
(ROOT / "artifacts/analytics.json").write_text(json.dumps(repo.analytics(), indent=2) + "\n")
print(json.dumps(repo.analytics(), indent=2))
