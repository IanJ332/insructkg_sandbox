"""Durable, bounded feedback job queue for PrairieLearn and SIIP.
Decouples deterministic SQL grading from synchronous generative LLM inference.
Enforces fencing tokens, atomic compare-and-set state transitions, lease expiry,
bounded retries, data minimization (no hidden test rows), and student authorization.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feedback import PROMPT_VERSION, generate_feedback, load_graphs
from .observability import event


class JobQueueFullError(RuntimeError):
    """Raised when feedback job queue exceeds bounded capacity."""

    pass


class AttemptConflictError(ValueError):
    """Raised when duplicate attempt_id is enqueued with conflicting payload."""

    pass


class StaleLeaseError(RuntimeError):
    """Raised when worker attempts to complete or fail a job after lease expiration or theft."""

    pass


class UnauthorizedJobAccessError(PermissionError):
    """Raised when attempting to access a job belonging to another student."""

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
    lease_token: Optional[str] = None
    claimed_by: Optional[str] = None
    lease_expires_at: Optional[str] = None
    version: int = 0
    attempt_kind: str = "authoritative"
    reconciled_from: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_learner_dict(self) -> Dict[str, Any]:
        """Return strictly learner-visible fields. Excludes lease tokens, worker IDs, retry counters, and internal errors."""
        res = self.result or {}
        return {
            "job_id": self.job_id,
            "status": self.status,
            "question_id": self.question_id,
            "submitted_sql": self.submitted_sql,
            "grading": {
                "status": self.grading.get("status"),
                "score": self.grading.get("score"),
                "observation": self.grading.get("observation"),
            },
            "feedback": (
                {
                    "feedback_text": res.get("feedback_text"),
                    "candidate_concepts": res.get("candidate_concepts", []),
                    "evidence_references": res.get("evidence_references", []),
                    "personalized": res.get("personalized", False),
                    "history_provenance": res.get("history_provenance", "none"),
                    "grounding_provenance": res.get("grounding_provenance"),
                    "inference_status": res.get("inference_status"),
                    "feedback_quality": res.get("feedback_quality", "legacy_unreviewed"),
                    "quality_validation_scope": res.get("quality_validation_scope"),
                    "model_digest": res.get("model_digest"),
                }
                if self.status == "completed" and self.result
                else None
            ),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": "Feedback generation unavailable." if self.status == "failed" else None,
            "provenance": (
                {
                    "model_identifier": self.model_identifier,
                    "prompt_version": self.prompt_version,
                    "graph_version": self.graph_version,
                    "latency_ms": self.latency_ms,
                }
                if self.status == "completed"
                else None
            ),
        }


class FeedbackJobRepository:
    """SQLite-backed durable job queue with atomic claim, bounded capacity, lease recovery, and fencing tokens."""

    _COLUMNS = (
        "job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
        "model_identifier, prompt_version, graph_version, result, error, retries, "
        "max_retries, lease_token, claimed_by, lease_expires_at, version, attempt_kind, reconciled_from"
    )
    _SQL_SELECT_BY_ATTEMPT = (
        "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
        "model_identifier, prompt_version, graph_version, result, error, retries, "
        "max_retries, lease_token, claimed_by, lease_expires_at, version, attempt_kind, reconciled_from "
        "FROM feedback_jobs WHERE attempt_id=?"
    )
    _SQL_SELECT_PENDING = (
        "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
        "model_identifier, prompt_version, graph_version, result, error, retries, "
        "max_retries, lease_token, claimed_by, lease_expires_at, version, attempt_kind, reconciled_from "
        "FROM feedback_jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
    )
    _SQL_SELECT_EXPIRED_LEASE = (
        "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
        "model_identifier, prompt_version, graph_version, result, error, retries, "
        "max_retries, lease_token, claimed_by, lease_expires_at, version, attempt_kind, reconciled_from "
        "FROM feedback_jobs WHERE status = 'processing' AND (lease_expires_at IS NULL OR lease_expires_at < ?) "
        "ORDER BY started_at ASC LIMIT 1"
    )
    _SQL_SELECT_BY_JOB_ID = (
        "SELECT job_id, attempt_id, student_id, question_id, submitted_sql, grading, "
        "feedback_mode, status, created_at, started_at, completed_at, latency_ms, "
        "model_identifier, prompt_version, graph_version, result, error, retries, "
        "max_retries, lease_token, claimed_by, lease_expires_at, version, attempt_kind, reconciled_from "
        "FROM feedback_jobs WHERE job_id = ?"
    )

    def __init__(self, db_path: str | Path, max_queue_size: int = 1000):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_queue_size = max_queue_size
        with closing(self.connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS feedback_jobs(
                    job_id TEXT PRIMARY KEY,
                    attempt_id TEXT NOT NULL UNIQUE,
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
                    max_retries INTEGER DEFAULT 2,
                    lease_token TEXT,
                    claimed_by TEXT,
                    lease_expires_at TEXT,
                    version INTEGER DEFAULT 0,
                    attempt_kind TEXT DEFAULT 'authoritative',
                    reconciled_from TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON feedback_jobs(status, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_attempt ON feedback_jobs(attempt_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_student ON feedback_jobs(student_id, created_at);
                """
            )
            # Ensure schema migrations for existing databases that lack lease columns
            self._ensure_schema(db)
            db.commit()

    def _ensure_schema(self, db: sqlite3.Connection) -> None:
        """Ensure lease_token, claimed_by, lease_expires_at, version, and attempt_kind columns exist."""
        cursor = db.execute("PRAGMA table_info(feedback_jobs)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        for col_name, col_type in [
            ("lease_token", "TEXT"),
            ("claimed_by", "TEXT"),
            ("lease_expires_at", "TEXT"),
            ("version", "INTEGER DEFAULT 0"),
            ("attempt_kind", "TEXT DEFAULT 'authoritative'"),
            ("reconciled_from", "TEXT"),
        ]:
            if col_name not in existing_cols:
                db.execute(f"ALTER TABLE feedback_jobs ADD COLUMN {col_name} {col_type}")

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
        attempt_kind: str = "authoritative",
        grounding: Optional[Dict[str, Any]] = None,
    ) -> FeedbackJob:
        """Idempotently enqueue a feedback job. Returns existing job if attempt_id is known."""
        # Never store hidden rows, reference SQL or raw engine datasets in durable job queue
        minimized_grading = {
            k: grading[k] for k in ["status", "score", "observation"] if k in grading
        }
        if grounding is not None:
            from .assignment_grounding import validate_grounding

            minimized_grading["_grounding"] = validate_grounding(grounding)
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Check for existing job for this attempt_id
                cursor = db.execute(
                    self._SQL_SELECT_BY_ATTEMPT,
                    (attempt_id,),
                )
                row = cursor.fetchone()
                if row:
                    existing = self._row_to_job(row)
                    if (
                        existing.student_id != student_id
                        or existing.question_id != question_id
                        or existing.submitted_sql != submitted_sql
                        or existing.grading.get("status") != minimized_grading.get("status")
                        or existing.grading.get("score") != minimized_grading.get("score")
                        or existing.grading.get("observation")
                        != minimized_grading.get("observation")
                        or existing.grading.get("_grounding") != minimized_grading.get("_grounding")
                    ):
                        raise AttemptConflictError(
                            f"Attempt ID '{attempt_id}' already exists with conflicting payload"
                        )
                    db.commit()
                    return existing

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
                    "feedback_mode, status, created_at, retries, max_retries, version, attempt_kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, 0, ?, 0, ?)",
                    (
                        job_id,
                        attempt_id,
                        student_id,
                        question_id,
                        submitted_sql,
                        json.dumps(minimized_grading),
                        mode,
                        now,
                        max_retries,
                        attempt_kind,
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
            grading=minimized_grading,
            feedback_mode=mode,
            status="pending",
            created_at=now,
            max_retries=max_retries,
            version=0,
            attempt_kind=attempt_kind,
        )

    def claim(
        self, worker_id: str = "worker-1", lease_seconds: float = 60.0
    ) -> Optional[FeedbackJob]:
        """Atomically claim the oldest pending job or recover a timed-out lease using compare-and-set."""
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        lease_expires_str = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        lease_token = uuid.uuid4().hex

        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # 1. Find oldest pending job
                cursor = db.execute(self._SQL_SELECT_PENDING)
                row = cursor.fetchone()

                # 2. If no pending, look for expired lease in 'processing'
                if not row:
                    cursor = db.execute(
                        self._SQL_SELECT_EXPIRED_LEASE,
                        (now_str,),
                    )
                    row = cursor.fetchone()

                if not row:
                    db.commit()
                    return None

                job_id = row[0]
                current_retries = row[17]
                max_retries = row[18]

                # Check if recovering this lease exceeds max retries
                if row[7] == "processing" and (current_retries + 1) > max_retries:
                    db.execute(
                        "UPDATE feedback_jobs SET status = 'failed', error = 'Max lease retries exceeded', "
                        "completed_at = ?, lease_token = NULL, claimed_by = NULL, version = version + 1 "
                        "WHERE job_id = ? AND status = 'processing'",
                        (now_str, job_id),
                    )
                    db.commit()
                    event("feedback_job_max_retries_exceeded", job_id=job_id, worker_id=worker_id)
                    return None

                # Atomic compare-and-set update with fencing token
                update_cursor = db.execute(
                    "UPDATE feedback_jobs SET "
                    "status = 'processing', claimed_by = ?, lease_token = ?, started_at = ?, "
                    "lease_expires_at = ?, "
                    "retries = CASE WHEN status = 'processing' THEN retries + 1 ELSE retries END, "
                    "version = version + 1 "
                    "WHERE job_id = ? AND ("
                    "  status = 'pending' OR (status = 'processing' AND (lease_expires_at IS NULL OR lease_expires_at < ?))"
                    ")",
                    (worker_id, lease_token, now_str, lease_expires_str, job_id, now_str),
                )
                if update_cursor.rowcount == 0:
                    db.commit()
                    return None

                # Fetch freshly updated record
                updated_row = db.execute(
                    self._SQL_SELECT_BY_JOB_ID,
                    (job_id,),
                ).fetchone()
                db.commit()

                job = self._row_to_job(updated_row)
                event(
                    "feedback_job_claimed",
                    job_id=job.job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
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
        lease_token: Optional[str] = None,
    ) -> FeedbackJob:
        """Mark a job as successfully completed with full provenance and fencing token validation."""
        if not lease_token:
            raise StaleLeaseError(
                f"Job {job_id} cannot be completed without an active worker claim (missing lease token)"
            )
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                update_cursor = db.execute(
                    "UPDATE feedback_jobs SET "
                    "status = 'completed', completed_at = ?, latency_ms = ?, "
                    "model_identifier = ?, prompt_version = ?, graph_version = ?, "
                    "result = ?, error = NULL, lease_token = NULL, claimed_by = NULL, "
                    "version = version + 1 "
                    "WHERE job_id = ? AND status = 'processing' AND lease_token = ?",
                    (
                        now,
                        latency_ms,
                        model_identifier,
                        prompt_version,
                        graph_version,
                        json.dumps(result),
                        job_id,
                        lease_token,
                    ),
                )
                if update_cursor.rowcount == 0:
                    raise StaleLeaseError(
                        f"Job {job_id} cannot be completed: lease expired or acquired by another worker"
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

    def fail(self, job_id: str, error: str, lease_token: Optional[str] = None) -> FeedbackJob:
        """Record job failure; retries if within bounds, otherwise marks failed."""
        if not lease_token:
            raise StaleLeaseError(
                f"Job {job_id} failure update rejected: missing active worker claim (missing lease token)"
            )
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT retries, max_retries FROM feedback_jobs WHERE job_id = ? AND lease_token = ?",
                    (job_id, lease_token),
                ).fetchone()
                if not row:
                    raise StaleLeaseError(
                        f"Job {job_id} failure update rejected: lease expired or invalid"
                    )
                retries, max_retries = row[0], row[1]
                new_retries = retries + 1
                if new_retries < max_retries:
                    new_status = "pending"
                    completed_at = None
                else:
                    new_status = "failed"
                    completed_at = now

                update_cursor = db.execute(
                    "UPDATE feedback_jobs SET "
                    "status = ?, error = ?, retries = ?, completed_at = ?, "
                    "lease_token = NULL, claimed_by = NULL, lease_expires_at = NULL, "
                    "version = version + 1 "
                    "WHERE job_id = ? AND lease_token = ?",
                    (new_status, error, new_retries, completed_at, job_id, lease_token),
                )
                if update_cursor.rowcount == 0:
                    raise StaleLeaseError(f"Job {job_id} failure update lost race condition")
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

    def cleanup(self, retention_seconds: float = 86400.0) -> int:
        """Purge completed/failed jobs older than retention_seconds."""
        cutoff_dt = datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        cutoff_str = cutoff_dt.isoformat()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                cursor = db.execute(
                    "DELETE FROM feedback_jobs "
                    "WHERE status IN ('completed', 'failed') AND completed_at != '' AND completed_at < ?",
                    (cutoff_str,),
                )
                deleted = cursor.rowcount
                db.commit()
                return deleted
            except Exception:
                db.rollback()
                raise

    def get(self, job_id: str) -> Optional[FeedbackJob]:
        """Fetch a job by ID without authorization check."""
        with closing(self.connect()) as db:
            row = db.execute(
                self._SQL_SELECT_BY_JOB_ID,
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def get_by_attempt(self, attempt_id: str) -> Optional[FeedbackJob]:
        """Fetch a job by its attempt identifier."""
        with closing(self.connect()) as db:
            row = db.execute(self._SQL_SELECT_BY_ATTEMPT, (attempt_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def reconcile(
        self,
        provisional_attempt_id: str,
        authoritative_attempt_id: str,
        student_id: Optional[str] = None,
        question_id: Optional[str] = None,
        submission_time: Optional[str] = None,
    ) -> Optional[FeedbackJob]:
        """
        Reconcile a provisional live event to an authoritative submission identifier.
        Validates corresponding student and question evidence before binding.
        """
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Verify provisional record exists and get its evidence
                prov_row = db.execute(
                    "SELECT job_id, student_id, question_id, created_at, submitted_sql FROM feedback_jobs WHERE attempt_id = ?",
                    (provisional_attempt_id,),
                ).fetchone()
                if not prov_row:
                    db.commit()
                    return None

                prov_job_id, prov_student, prov_question, prov_created, prov_sql = prov_row

                # Evidence verification: student_id must match if supplied
                if student_id and prov_student != student_id:
                    raise AttemptConflictError(
                        f"Reconciliation student mismatch: provisional belongs to '{prov_student}', "
                        f"reconciliation requested for '{student_id}'"
                    )

                # Evidence verification: question_id must match if supplied
                if question_id and prov_question != question_id:
                    raise AttemptConflictError(
                        f"Reconciliation question mismatch: provisional belongs to '{prov_question}', "
                        f"reconciliation requested for '{question_id}'"
                    )

                # Check if authoritative record already exists
                existing_auth = db.execute(
                    "SELECT job_id, student_id, question_id, submitted_sql FROM feedback_jobs WHERE attempt_id = ?",
                    (authoritative_attempt_id,),
                ).fetchone()
                if existing_auth:
                    auth_job_id, auth_student, auth_question, auth_sql = existing_auth
                    if auth_student != prov_student or auth_question != prov_question:
                        raise AttemptConflictError("Reconciliation ownership or question mismatch")
                    if auth_sql != prov_sql:
                        raise AttemptConflictError("Reconciliation SQL evidence mismatch")
                    if student_id and auth_student != student_id:
                        raise AttemptConflictError(
                            f"Authoritative student mismatch: existing belongs to '{auth_student}', "
                            f"reconciliation requested for '{student_id}'"
                        )
                    if question_id and auth_question != question_id:
                        raise AttemptConflictError(
                            f"Authoritative question mismatch: existing belongs to '{auth_question}', "
                            f"reconciliation requested for '{question_id}'"
                        )
                    # Authoritative job exists; mark provisional as reconciled alias
                    db.execute(
                        "UPDATE feedback_jobs SET attempt_kind = 'reconciled_duplicate', reconciled_from = ? WHERE attempt_id = ?",
                        (authoritative_attempt_id, provisional_attempt_id),
                    )
                    db.commit()
                    return self.get(auth_job_id)

                # Update provisional attempt to authoritative attempt_id
                if submission_time:
                    cursor = db.execute(
                        "UPDATE feedback_jobs SET attempt_id = ?, attempt_kind = 'reconciled', reconciled_from = ?, created_at = ? "
                        "WHERE attempt_id = ?",
                        (
                            authoritative_attempt_id,
                            provisional_attempt_id,
                            submission_time,
                            provisional_attempt_id,
                        ),
                    )
                else:
                    cursor = db.execute(
                        "UPDATE feedback_jobs SET attempt_id = ?, attempt_kind = 'reconciled', reconciled_from = ? "
                        "WHERE attempt_id = ?",
                        (authoritative_attempt_id, provisional_attempt_id, provisional_attempt_id),
                    )
                if cursor.rowcount == 0:
                    db.commit()
                    return None
                db.commit()
            except Exception:
                db.rollback()
                raise
        return self.get_by_attempt(authoritative_attempt_id)

    def get_for_student(self, job_id: str, student_id: str) -> Optional[FeedbackJob]:
        """Fetch job enforcing student identity authorization boundary."""
        job = self.get(job_id)
        if not job:
            return None
        if job.student_id != student_id:
            raise UnauthorizedJobAccessError(
                f"Unauthorized access: You do not have permission to view feedback for job '{job_id}'"
            )
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
            lease_token=row[19] if len(row) > 19 else None,
            claimed_by=row[20] if len(row) > 20 else None,
            lease_expires_at=row[21] if len(row) > 21 else None,
            version=row[22] if len(row) > 22 else 0,
            attempt_kind=row[23] if len(row) > 23 else "authoritative",
            reconciled_from=row[24] if len(row) > 24 else None,
        )


class FeedbackWorker:
    """Bounded worker that pulls jobs from FeedbackJobRepository, invokes provider, and records provenance."""

    def __init__(
        self,
        repo: FeedbackJobRepository,
        worker_id: str = "worker-1",
        submission_repo: Optional[Any] = None,
    ):
        self.repo = repo
        self.worker_id = worker_id
        self.submission_repo = submission_repo

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

            # Historical personalization: load prior mastery profile if not explicitly passed
            student_mastery = mastery
            history_provenance = "none"
            if student_mastery is None and self.submission_repo is not None:
                try:
                    cutoff = job.created_at
                    try:
                        current = self.submission_repo.attempt_for_student(
                            job.attempt_id, job.student_id
                        )
                        cutoff = min(cutoff, current["timestamp"])
                    except PermissionError:
                        # Native provisional events can precede submission import.
                        if job.attempt_kind == "provisional":
                            raise ValueError(
                                "Prior history unavailable until attempt reconciliation"
                            )
                        pass
                    prof = self.submission_repo.profile(job.student_id, as_of=cutoff, before=True)
                    if prof and isinstance(prof, dict) and prof.get("concepts"):
                        student_mastery = prof["concepts"]
                        history_provenance = "prior_submissions"
                except Exception:
                    student_mastery = None
            elif student_mastery is not None:
                history_provenance = "provided_context"

            # Generate feedback using configured mode and provider
            feedback_result = generate_feedback(
                qid=job.question_id,
                sql=job.submitted_sql,
                result=job.grading,
                mode=job.feedback_mode,
                mastery=student_mastery,
                provider=provider,
                grounding=job.grading.get("_grounding"),
            )
            if feedback_result.get("grounding_provenance"):
                provenance = feedback_result["grounding_provenance"]
                graph_sha = f"{provenance['graph_id']}:v{provenance['graph_version']}"
            feedback_result["personalized"] = bool(student_mastery)
            feedback_result["history_provenance"] = history_provenance
            if "historical_personalization" not in feedback_result:
                feedback_result["historical_personalization"] = {
                    "status": "provided_concept_evidence" if student_mastery else "none",
                    "concept_count": len(student_mastery) if student_mastery else 0,
                    "evidence_kind": "descriptive_beta_heuristic" if student_mastery else None,
                }
            if (
                provider is not None
                and feedback_result.get("inference_status") == "provider_error_fallback"
                and not job.grading.get("_grounding")
            ):
                raise RuntimeError(
                    f"Provider inference failed: {feedback_result.get('error_details', 'unknown')}"
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
                lease_token=job.lease_token,
            )
        except StaleLeaseError as exc:
            event(
                "feedback_worker_stale_lease",
                job_id=job.job_id,
                worker_id=self.worker_id,
                error=str(exc),
            )
            return None
        except Exception as exc:
            try:
                return self.repo.fail(
                    job.job_id,
                    f"{type(exc).__name__}: {str(exc)[:250]}",
                    lease_token=job.lease_token,
                )
            except StaleLeaseError:
                return None

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
