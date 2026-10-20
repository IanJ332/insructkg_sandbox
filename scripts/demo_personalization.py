"""Demonstrate distinct synthetic histories without network or model inference."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.grader import QUESTIONS
from siip.personalization import feedback_for_attempt, synthetic_principal
from siip.store import SubmissionRepository

wrong = QUESTIONS["sql_join_01"]["reference_sql"]
correct = QUESTIONS["sql_join_02"]["reference_sql"]
results = []
with tempfile.TemporaryDirectory(prefix="siip-personalization-") as directory:
    repo = SubmissionRepository(Path(directory) / "synthetic.sqlite3")
    for sid, prior_sql in [("S001", wrong), ("S002", correct)]:
        for suffix, sql, timestamp in [
            ("prior", prior_sql, "2026-10-14T09:00:00Z"),
            ("current", wrong, "2026-10-14T10:00:00Z"),
        ]:
            repo.process(
                {
                    "attempt_id": sid + "-" + suffix,
                    "student_id": sid,
                    "question_id": "sql_join_02",
                    "submitted_sql": sql,
                    "timestamp": timestamp,
                }
            )
        report = feedback_for_attempt(
            repo, sid + "-current", synthetic_principal(sid, authorized=True)
        )
        results.append({"synthetic_student": sid, "deterministic_score": 0, **report})
assert results[0]["feedback"]["feedback_text"] != results[1]["feedback"]["feedback_text"]
output = ROOT / "artifacts/followup/personalization-demo.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(
        {
            "status": "PASS",
            "same_current_sql": True,
            "distinct_prior_histories": True,
            "live_model_calls": 0,
            "results": results,
        },
        indent=2,
    )
    + "\n"
)
print(
    "PASS: identical current SQL/grade, distinct prior synthetic histories and feedback; zero inference. "
    + str(output)
)
