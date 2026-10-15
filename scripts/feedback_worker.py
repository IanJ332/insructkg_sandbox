"""Independent feedback worker daemon for asynchronous SIIP / PrairieLearn inference.
Pulls claimed jobs from FeedbackJobRepository, invokes the configured provider,
and stores full provenance and result metadata.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.feedback import configured_provider
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.observability import event


def main():
    parser = argparse.ArgumentParser(description="SIIP Asynchronous Feedback Worker")
    parser.add_argument(
        "--db",
        default=os.environ.get("SIIP_FEEDBACK_JOBS_DB")
        or str(ROOT / "artifacts/jobs/feedback_jobs.sqlite3"),
        help="Path to feedback jobs SQLite database",
    )
    parser.add_argument(
        "--worker-id",
        default=f"worker-{os.getpid()}",
        help="Unique worker identifier",
    )
    parser.add_argument(
        "--lease-seconds",
        type=float,
        default=60.0,
        help="Lease duration in seconds before a processing job may be reclaimed",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds to sleep when no pending jobs are available",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job and exit",
    )
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Process all available jobs until queue is empty, then exit",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Maximum jobs to process before exiting",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    repo = FeedbackJobRepository(db_path)
    worker = FeedbackWorker(repo, worker_id=args.worker_id)
    provider = configured_provider()

    print(
        f"SIIP Feedback Worker starting: id={args.worker_id}, db={args.db}, provider={type(provider).__name__ if provider else 'None'}",
        flush=True,
    )

    running = True

    def _handle_signal(signum, frame):
        nonlocal running
        print(
            f"Worker {args.worker_id} received stop signal ({signum}); shutting down cleanly...",
            flush=True,
        )
        running = False

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    processed_count = 0

    if args.once:
        job = worker.process_one(provider=provider)
        if job:
            print(f"Processed job {job.job_id} ({job.status}) in {job.latency_ms}ms", flush=True)
            sys.exit(0)
        else:
            print("No pending jobs available", flush=True)
            sys.exit(0)

    if args.drain:
        jobs = worker.drain(provider=provider, max_jobs=args.max_jobs)
        print(f"Drained {len(jobs)} jobs from queue", flush=True)
        sys.exit(0)

    # Continuous daemon loop
    while running:
        if args.max_jobs is not None and processed_count >= args.max_jobs:
            print(f"Reached max_jobs limit ({args.max_jobs}); exiting", flush=True)
            break

        try:
            job = worker.process_one(provider=provider)
            if job:
                processed_count += 1
                print(
                    f"[{time.strftime('%X')}] Completed job {job.job_id} for student {job.student_id} "
                    f"question {job.question_id} (status: {job.status}, latency: {job.latency_ms}ms)",
                    flush=True,
                )
            else:
                time.sleep(args.poll_interval)
        except Exception as exc:
            event("worker_loop_error", worker_id=args.worker_id, error=str(exc))
            print(f"Worker error in loop: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.poll_interval)

    print(f"Worker {args.worker_id} stopped. Total jobs processed: {processed_count}", flush=True)


if __name__ == "__main__":
    main()
