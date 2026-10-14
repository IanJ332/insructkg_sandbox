"""Import only a reviewed local synthetic PrairieLearn all-submissions CSV."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.ingestion import import_local_csv
from siip.store import SubmissionRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--local-synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    repo = SubmissionRepository(ROOT / "artifacts/synthetic.sqlite3")
    try:
        processed = import_local_csv(repo, args.csv)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    (ROOT / "artifacts/pl_import_results.json").write_text(json.dumps(processed, indent=2) + "\n")
    print(f"Atomically imported/reused {len(processed)} actual local PL submissions into S003.")
    print(json.dumps(repo.analytics(), indent=2))


if __name__ == "__main__":
    main()
