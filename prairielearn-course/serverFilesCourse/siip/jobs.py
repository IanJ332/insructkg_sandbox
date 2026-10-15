"""Durable, bounded feedback job queue for PrairieLearn and SIIP.
Decouples deterministic SQL grading from synchronous generative LLM inference.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feedback import PROMPT_VERSION, generate_feedback, load_graphs
from .observability import event


class JobQueueFullError(RuntimeError):
    """Raised when feedback job queue exceeds bounded capacity."""

    pass


@dataclass
class FeedbackJob:
    job_id: str
    attempt_id: str
    student_id: str
    question_id: str
    submitted_sql: str
    grading: Dict[str, Any]
    feedback_mode: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    latency_ms: Optional[float] = None
    model_identifier: Optional[str] = None
    prompt_version: Optional[str] = None
    graph_version: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackJobRepository:
    """SQLite-backed durable job queue with atomic claim, bounded capacity, and lease recovery."""

    def __init__(self, db_path: str | Path, max_queue_size: int = 1000):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_queue_size = max_queue_size
        with closing(self.connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS feedback_jobs(
                    job_id TEXT PRIMARY KEY,
                    attempt_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    submitted_sql TEXT NOT NULL,
                    grading TEXT NOT NULL,
                    feedback_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    latency_ms REAL,
                    model_identifier TEXT,
                    prompt_version TEXT,
                    graph_version TEXT,
                    result TEXT,
                    error TEXT,
                    retries INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON feedback_jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_attempt ON feedback_jobs(attempt_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_student ON feedback_jobs(student_id, created_at);
                """
            )
            db.commit()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def enqueue(
        self,
        attempt_id: str,
        student_id: str,
        question_id: str,
        submitted_sql: str,
        grading: Dict[str, Any],
        mode: str = "kg",
        max_retries: int = 2,
    ) -> FeedbackJob:
        """Idempotently enqueue a feedback job. Returns existing job if attempt_id is known."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Check for existing job for this attempt_id
                cursor = db.execute(
                    "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
                    "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
                    "model_identifier, prompt_version, graph_version, result, error, retries, max_retries "
                    "FROM feedback_jobs WHERE attempt_id=?",
                    (attempt_id,),
                )
                row = cursor.fetchone()
                if row:
                    db.commit()
                    return self._row_to_job(row)

                # Check queue bounds
                count_row = db.execute(
                    "SELECT COUNT(*) FROM feedback_jobs WHERE status IN ('pending', 'processing')"
                ).fetchone()
                if count_row and count_row[0] >= self.max_queue_size:
                    raise JobQueueFullError(
                        f"Feedback job queue exceeded bound of {self.max_queue_size} items"
                    )

                job_id = f"job-{uuid.uuid4().hex[:16]}"
                db.execute(
                    "INSERT INTO feedback_jobs "
                    "(job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
                    "feedback_mode, status, created_at, retries, max_retries) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, 0, ?)",
                    (
                        job_id,
                        attempt_id,
                        student_id,
                        question_id,
                        submitted_sql,
                        json.dumps(grading),
                        mode,
                        now,
                        max_retries,
                    ),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        event(
            "feedback_job_enqueued", job_id=job_id, attempt_id=attempt_id, question_id=question_id
        )
        return FeedbackJob(
            job_id=job_id,
            attempt_id=attempt_id,
            student_id=student_id,
            question_id=question_id,
            submitted_sql=submitted_sql,
            grading=grading,
            feedback_mode=mode,
            status="pending",
            created_at=now,
            max_retries=max_retries,
        )

    def claim(
        self, worker_id: str = "worker-1", lease_seconds: float = 60.0
    ) -> Optional[FeedbackJob]:
        """Atomically claim the oldest pending job or recover a timed-out lease."""
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Find oldest pending job or timed-out processing job
                cursor = db.execute(
                    "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
                    "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
                    "model_identifier, prompt_version, graph_version, result, error, retries, max_retries "
                    "FROM feedback_jobs "
                    "WHERE status = 'pending' "
                    "ORDER BY created_at ASC LIMIT 1"
                )
                row = cursor.fetchone()

                # If no pending, look for expired lease in 'processing'
                if not row:
                    cursor = db.execute(
                        "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
                        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
                        "model_identifier, prompt_version, graph_version, result, error, retries, max_retries "
                        "FROM feedback_jobs "
                        "WHERE status = 'processing' "
                        "ORDER BY started_at ASC LIMIT 1"
                    )
                    candidate = cursor.fetchone()
                    if candidate:
                        started_at_str = candidate[9]
                        if started_at_str:
                            started_dt = datetime.fromisoformat(started_at_str)
                            if (now_dt - started_dt).total_seconds() > lease_seconds:
                                row = candidate

                if not row:
                    db.commit()
                    return None

                job_id = row[0]
                db.execute(
                    "UPDATE feedback_jobs SET status = 'processing', started_at = ? WHERE job_id = ?",
                    (now_str, job_id),
                )
                db.commit()

                job = self._row_to_job(row)
                job.status = "processing"
                job.started_at = now_str
                event("feedback_job_claimed", job_id=job.job_id, worker_id=worker_id)
                return job
            except Exception:
                db.rollback()
                raise

    def complete(
        self,
        job_id: str,
        result: Dict[str, Any],
        latency_ms: float,
        model_identifier: str,
        prompt_version: str,
        graph_version: str,
    ) -> FeedbackJob:
        """Mark a job as successfully completed with full provenance."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "UPDATE feedback_jobs SET "
                    "status = 'completed', completed_at = ?, latency_ms = ?, "
                    "model_identifier = ?, prompt_version = ?, graph_version = ?, "
                    "result = ?, error = NULL "
                    "WHERE job_id = ?",
                    (
                        now,
                        latency_ms,
                        model_identifier,
                        prompt_version,
                        graph_version,
                        json.dumps(result),
                        job_id,
                    ),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        event(
            "feedback_job_completed", job_id=job_id, latency_ms=latency_ms, model=model_identifier
        )
        job = self.get(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} not found after completion")
        return job

    def fail(self, job_id: str, error: str) -> FeedbackJob:
        """Record job failure; retries if within bounds, otherwise marks failed."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT retries, max_retries FROM feedback_jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if not row:
                    raise KeyError(f"Job {job_id} not found")
                retries, max_retries = row[0], row[1]
                new_retries = retries + 1
                if new_retries < max_retries:
                    # Retry: return to pending
                    new_status = "pending"
                    completed_at = None
                else:
                    new_status = "failed"
                    completed_at = now

                db.execute(
                    "UPDATE feedback_jobs SET "
                    "status = ?, error = ?, retries = ?, completed_at = ? "
                    "WHERE job_id = ?",
                    (new_status, error, new_retries, completed_at, job_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        event(
            "feedback_job_failed",
            job_id=job_id,
            error=error,
            new_status=new_status,
            retries=new_retries,
        )
        job = self.get(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} not found after failure")
        return job

    def get(self, job_id: str) -> Optional[FeedbackJob]:
        """Fetch a job by ID without authorization check."""
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
                "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
                "model_identifier, prompt_version, graph_version, result, error, retries, max_retries "
                "FROM feedback_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def get_for_student(self, job_id: str, student_id: str) -> Optional[FeedbackJob]:
        """Fetch job enforcing student identity authorization boundary."""
        job = self.get(job_id)
        if not job or job.student_id != student_id:
            return None
        return job

    def stats(self) -> Dict[str, int]:
        """Return counts of jobs by status."""
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT status, COUNT(*) FROM feedback_jobs GROUP BY status"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    @staticmethod
    def _row_to_job(row: Any) -> FeedbackJob:
        return FeedbackJob(
            job_id=row[0],
            attempt_id=row[1],
            student_id=row[2],
            question_id=row[3],
            submitted_sql=row[4],
            grading=json.loads(row[5]),
            feedback_mode=row[6],
            status=row[7],
            created_at=row[8],
            started_at=row[9],
            completed_at=row[10],
            latency_ms=row[11],
            model_identifier=row[12],
            prompt_version=row[13],
            graph_version=row[14],
            result=json.loads(row[15]) if row[15] else None,
            error=row[16],
            retries=row[17],
            max_retries=row[18],
        )


class FeedbackWorker:
    """Bounded worker that pulls jobs from FeedbackJobRepository, invokes provider, and records provenance."""

    def __init__(self, repo: FeedbackJobRepository, worker_id: str = "worker-1"):
        self.repo = repo
        self.worker_id = worker_id

    def process_one(
        self, provider: Any = None, mastery: Optional[Dict[str, Any]] = None
    ) -> Optional[FeedbackJob]:
        """Claim and execute one pending job. Returns completed job or None if queue is empty."""
        job = self.repo.claim(self.worker_id)
        if not job:
            return None

        t0 = time.monotonic()
        try:
            # Capture current graph SHA version for provenance
            graph_sha = "unknown"
            try:
                existing_graph, _ = load_graphs()
                graph_sha = existing_graph.sha256[:16]
            except (OSError, ValueError, KeyError):
                graph_sha = "unversioned"

            # Generate feedback using configured mode and provider
            feedback_result = generate_feedback(
                qid=job.question_id,
                sql=job.submitted_sql,
                result=job.grading,
                mode=job.feedback_mode,
                mastery=mastery,
                provider=provider,
            )
            latency_ms = round((time.monotonic() - t0) * 1000, 3)
            model_id = feedback_result.get("model_identifier", "deterministic-rules-v1")

            return self.repo.complete(
                job_id=job.job_id,
                result=feedback_result,
                latency_ms=latency_ms,
                model_identifier=model_id,
                prompt_version=PROMPT_VERSION,
                graph_version=graph_sha,
            )
        except Exception as exc:
            return self.repo.fail(job.job_id, f"{type(exc).__name__}: {str(exc)[:250]}")

    def drain(
        self,
        provider: Any = None,
        mastery: Optional[Dict[str, Any]] = None,
        max_jobs: Optional[int] = None,
    ) -> List[FeedbackJob]:
        """Process jobs until queue is empty or max_jobs is reached."""
        processed = []
        count = 0
        while max_jobs is None or count < max_jobs:
            job = self.process_one(provider=provider, mastery=mastery)
            if not job:
                break
            processed.append(job)
            count += 1
        return processed
