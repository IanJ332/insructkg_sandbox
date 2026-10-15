"""Run 1 bounded local Qwen3 8B canary inference test on Windows host."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.feedback import CompatibleProvider
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.store import SubmissionRepository


def main():
    tmp = tempfile.TemporaryDirectory()
    jobs_db = Path(tmp.name) / "canary_jobs.sqlite3"
    sub_db = Path(tmp.name) / "canary_sub.sqlite3"

    repo = FeedbackJobRepository(jobs_db)
    sub_repo = SubmissionRepository(sub_db)
    worker = FeedbackWorker(repo, worker_id="canary-worker", submission_repo=sub_repo)

    provider = CompatibleProvider(
        base_url="http://127.0.0.1:11434/v1",
        model="qwen3:8b",
        key="",
        allow_paid=False,
        timeout=60,
        max_tokens=1200,
    )

    grading = {"status": "semantic_error", "score": 0.0, "observation": "missing_unmatched_rows"}
    job = repo.enqueue(
        "canary-att-01",
        "S001",
        "sql_join_02",
        "SELECT e.name FROM Employees e;",
        grading,
        mode="kg",
    )
    print(f"Enqueued canary job: {job.job_id}")

    t0 = time.time()
    completed = worker.process_one(provider=provider)
    duration = time.time() - t0

    if not completed:
        print("ERROR: Worker returned None")
        sys.exit(1)

    res = completed.result or {}
    print(f"Canary job status: {completed.status}")
    print(f"Total time: {duration:.2f}s (latency recorded: {completed.latency_ms}ms)")
    print(f"Inference status: {res.get('inference_status')}")
    print(f"Model identifier: {completed.model_identifier}")
    print(f"Feedback text: {res.get('feedback_text')}")
    print(f"Candidate concepts: {res.get('candidate_concepts')}")
    print(f"Evidence references: {res.get('evidence_references')}")
    print(f"Token usage: {res.get('token_usage')}")
    print(f"Personalized: {res.get('personalized')}")
    print(f"History provenance: {res.get('history_provenance')}")

    out_file = ROOT / "artifacts/phase4_canary_result.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(
            {
                "job_id": completed.job_id,
                "status": completed.status,
                "duration_seconds": round(duration, 3),
                "model_identifier": completed.model_identifier,
                "inference_status": res.get("inference_status"),
                "token_usage": res.get("token_usage"),
                "learner_view": completed.to_learner_dict(),
            },
            indent=2,
        )
    )
    print(f"Saved canary report to {out_file}")


if __name__ == "__main__":
    main()
