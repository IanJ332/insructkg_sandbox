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

from siip.demo_observability import DemoObservabilityRepository
from siip.feedback import configured_provider
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.observability import event
from siip.store import SubmissionRepository


def record_demo_feedback_events(job):
    """Mirror verified worker timestamps into the optional professor-demo timeline."""

    artifact_dir = os.environ.get("SIIP_DEMO_ARTIFACT_DIR")
    if not artifact_dir or not job.started_at:
        return
    repository = DemoObservabilityRepository(Path(artifact_dir))
    existing = repository.list_events()
    correlation_id = os.environ.get("SIIP_DEMO_CORRELATION_ID", "siip-professor-demo")
    if not any(
        item.event_type == "feedback_generation_started" and item.entity_id == job.job_id
        for item in existing
    ):
        repository.record_event(
            actor_type="system",
            actor_id="siip-feedback-worker",
            phase="feedback",
            event_type="feedback_generation_started",
            entity_id=job.job_id,
            correlation_id=correlation_id,
            status="started",
            artifact_path="outputs/feedback/05_feedback_job.json",
            source_type="actual_execution",
            timestamp_utc=job.started_at,
        )
    if job.completed_at and not any(
        item.event_type == "feedback_generation_completed" and item.entity_id == job.job_id
        for item in existing
    ):
        repository.record_event(
            actor_type="system",
            actor_id="siip-feedback-worker",
            phase="feedback",
            event_type="feedback_generation_completed",
            entity_id=job.job_id,
            correlation_id=correlation_id,
            status="completed" if job.status == "completed" else "failed",
            artifact_path="outputs/feedback/05_feedback_result.json",
            source_type="actual_execution",
            timestamp_utc=job.completed_at,
        )


def main():
    parser = argparse.ArgumentParser(description="SIIP Asynchronous Feedback Worker")
    parser.add_argument(
        "--db",
        default=os.environ.get("SIIP_FEEDBACK_JOBS_DB")
        or str(ROOT / "artifacts/jobs/feedback_jobs.sqlite3"),
        help="Path to feedback jobs SQLite database",
    )
    parser.add_argument(
        "--sub-db",
        default=os.environ.get("SIIP_DB_PATH") or str(ROOT / "artifacts/synthetic.sqlite3"),
        help="Path to submissions SQLite database for historical profile lookup",
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

    sub_repo = None
    if args.sub_db:
        sub_path = Path(args.sub_db)
        sub_repo = SubmissionRepository(sub_path)

    worker = FeedbackWorker(repo, worker_id=args.worker_id, submission_repo=sub_repo)
    provider = configured_provider()

    print(
        f"SIIP Feedback Worker starting: id={args.worker_id}, db={args.db}, sub_db={args.sub_db if sub_repo else 'None'}, provider={type(provider).__name__ if provider else 'None'}",
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
            record_demo_feedback_events(job)
            print(f"Processed job {job.job_id} ({job.status}) in {job.latency_ms}ms", flush=True)
            sys.exit(0)
        else:
            print("No pending jobs available", flush=True)
            sys.exit(0)

    if args.drain:
        jobs = worker.drain(provider=provider, max_jobs=args.max_jobs)
        for job in jobs:
            record_demo_feedback_events(job)
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
                record_demo_feedback_events(job)
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
