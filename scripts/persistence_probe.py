"""Compare actual PL IDs and normalized records across a deliberate local restart."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

DOCKER = shutil.which("docker")
GIT = shutil.which("git")
if DOCKER is None or GIT is None:
    raise SystemExit("Docker and Git are required")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.store import SubmissionRepository

parser = argparse.ArgumentParser()
parser.add_argument("stage", choices=["before", "after"])
args = parser.parse_args()
repo = SubmissionRepository(ROOT / "artifacts/synthetic.sqlite3")
records = repo.records()
pl_ids = subprocess.check_output(
    [
        DOCKER,
        "compose",
        "-f",
        str(ROOT / "infrastructure/compose.yaml"),
        "exec",
        "-T",
        "prairielearn",
        "psql",
        "-d",
        "postgres",
        "-Atc",
        "SELECT id FROM submissions ORDER BY id",
    ],
    text=True,
).splitlines()
state = {
    "record_ids": [r["attempt_id"] for r in records],
    "record_sha256": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
    "pl_submission_ids": pl_ids,
}
path = ROOT / "artifacts/phase2" / ("persistence-" + args.stage + ".json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(state, indent=2) + "\n")
if args.stage == "after":
    before = json.loads((path.parent / "persistence-before.json").read_text())
    if before != state:
        raise SystemExit("Persistence mismatch after restart")
    print("PASS: exact PL submission IDs and normalized record hashes survived restart.")
else:
    print("Saved pre-restart state:", len(records), "records;", len(pl_ids), "PL submissions.")
