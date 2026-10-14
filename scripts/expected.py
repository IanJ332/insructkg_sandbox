import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.grader import QUESTIONS, run_query

out = {
    qid: {d: run_query(q["reference_sql"], d)["rows"] for d in ["A", "B"]}
    for qid, q in QUESTIONS.items()
}
(ROOT / "datasets/questions/expected_outputs.json").write_text(json.dumps(out, indent=2) + "\n")
print("Reference outputs saved for both datasets.")
