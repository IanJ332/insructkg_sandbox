"""Explicit local synthetic PL API poll; CSV remains a supported fallback."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import LOCAL_HOSTS, read_env_file
from siip.sources import AuthorizedPrairieLearnAPISource
from siip.store import SubmissionRepository
from siip.synchronization import SubmissionSynchronizer

parser = argparse.ArgumentParser()
parser.add_argument(
    "--scope-file", type=Path, required=True, help="Ignored local JSON scope/map; no token"
)
parser.add_argument("--db", type=Path, default=ROOT / "artifacts/synthetic.sqlite3")
parser.add_argument("--ack-local-synthetic-api", action="store_true", required=True)
parser.add_argument("--polls", type=int, default=1)
parser.add_argument("--interval", type=float, default=10)
args = parser.parse_args()
if not 1 <= args.polls <= 100 or not 1 <= args.interval <= 3600:
    raise SystemExit("Use a finite 1–100 poll count and 1–3600 second interval")
scope = json.loads(args.scope_file.read_text())
if urlparse(scope["base_url"]).hostname not in LOCAL_HOSTS:
    raise SystemExit("This phase's CLI is restricted to a local synthetic course")
env = read_env_file(str(ROOT / ".env"), os.environ)
source = AuthorizedPrairieLearnAPISource(
    scope["base_url"],
    env.get("SIIP_PL_API_TOKEN", ""),
    scope["course_instance_id"],
    scope["assessment_instance_id"],
    scope["identity_map"],
    authorized=args.ack_local_synthetic_api,
    assessment_id=scope["assessment_id"],
)
sync = SubmissionSynchronizer(
    SubmissionRepository(args.db), source, legacy_attempt_ids=scope.get("legacy_attempt_ids")
)
for poll in range(args.polls):
    print(json.dumps(sync.sync_once()), flush=True)
    if poll + 1 < args.polls:
        time.sleep(args.interval)
