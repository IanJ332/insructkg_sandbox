"""Inspect post-submission synthetic feedback; never calls a model provider."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.personalization import feedback_for_attempt, synthetic_principal
from siip.store import SubmissionRepository

parser = argparse.ArgumentParser()
parser.add_argument("--student", required=True)
parser.add_argument("--attempt", required=True)
parser.add_argument("--db", type=Path, default=ROOT / "artifacts/synthetic.sqlite3")
parser.add_argument("--ack-local-synthetic", action="store_true", required=True)
args = parser.parse_args()
principal = synthetic_principal(args.student, authorized=args.ack_local_synthetic)
print(
    json.dumps(
        feedback_for_attempt(SubmissionRepository(args.db), args.attempt, principal), indent=2
    )
)
