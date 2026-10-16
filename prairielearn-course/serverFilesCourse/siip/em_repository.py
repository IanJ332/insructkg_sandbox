"""SQLite Repository for Entrepreneurial Mindset (EM) Prompts, Responses, and Evidence.

Provides durable local persistence for Track A synthetic learner reflections and
instructor review workflows.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .em_models import (
    EMDimension,
    EMEvidenceRecord,
    EMReflectionPrompt,
    EMReflectionResponse,
    EMResponseStatus,
    EMReviewStatus,
)

DEFAULT_PROMPTS = [
    EMReflectionPrompt(
        prompt_id="em-prompt-c1",
        question_id="sql_join_03",
        dimension=EMDimension.CURIOSITY,
        info_box_focus="Curiosity (C) · Investigating Missing Data Anomalies",
        why_it_matters="In enterprise applications, unexpected NULL foreign keys often signal broken pipeline synchronizations, unonboarded personnel, or silent transaction failures rather than mere cosmetic gaps.",
        intended_learning_objective="Explore why database entities lack expected relationships and formulate investigative hypotheses before modifying records.",
        prompt_text="When examining employees with a NULL department_id, what organizational or technical root causes might explain why this reference is missing? What diagnostic query or investigation would you run next before altering these records?",
        rubric_version="rubric-keen-c1-v1",
    ),
    EMReflectionPrompt(
        prompt_id="em-prompt-x1",
        question_id="sql_join_02",
        dimension=EMDimension.CONNECTIONS,
        info_box_focus="Connections (X) · Linking Query Semantics to Cross-Department Workflows",
        why_it_matters="A database join is not only a relational algebra operation; it represents how disparate business domains (e.g. HR, Payroll, Project Planning) share authoritative state.",
        intended_learning_objective="Connect SQL join semantics to downstream cross-functional dependencies across organizational systems.",
        prompt_text="How does choosing a LEFT OUTER JOIN instead of an INNER JOIN protect downstream organizational processes (such as automated benefits enrollment or building access) when employees are between department assignments?",
        rubric_version="rubric-keen-x1-v1",
    ),
    EMReflectionPrompt(
        prompt_id="em-prompt-v1",
        question_id="sql_join_04",
        dimension=EMDimension.CREATING_VALUE,
        info_box_focus="Creating Value (V) · Protecting Decision-Making and Resource Allocation",
        why_it_matters="Omitting zero-headcount departments from an executive summary can cause leadership to assume those units have been terminated, potentially leading to incorrect budget reallocation or canceled strategic initiatives.",
        intended_learning_objective="Evaluate how subtle relational query choices directly safeguard executive decision-making and operational value.",
        prompt_text="If executive leadership uses your department headcount report to allocate quarterly operational budgets, what real-world business risks occur if zero-employee departments are silently omitted by an INNER JOIN? How does your query protect stakeholder value?",
        rubric_version="rubric-keen-v1-v1",
    ),
]


class EMRepository:
    """Manages persistence and review for EM reflections and evidence records."""

    def __init__(self, db_path: Path | str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._seed_default_prompts()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = sqlite3.Row
        return db

    def _init_tables(self) -> None:
        with closing(self.connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS em_prompts (
                    prompt_id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    info_box_focus TEXT NOT NULL,
                    why_it_matters TEXT NOT NULL,
                    intended_learning_objective TEXT NOT NULL,
                    rubric_version TEXT NOT NULL,
                    graph_version TEXT NOT NULL,
                    provenance TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_em_prompts_qid ON em_prompts(question_id);

                CREATE TABLE IF NOT EXISTS em_responses (
                    response_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    prompt_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    provenance TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_em_resp_student ON em_responses(student_id);

                CREATE TABLE IF NOT EXISTS em_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    response_id TEXT,
                    attempt_id TEXT,
                    student_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    relevant_concepts TEXT NOT NULL,
                    evidence_excerpt TEXT NOT NULL,
                    classification_method TEXT NOT NULL,
                    model_or_rubric_version TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    review_status TEXT NOT NULL,
                    instructor_notes TEXT,
                    reviewed_at TEXT,
                    reviewer_id TEXT,
                    created_at TEXT NOT NULL,
                    graph_version TEXT NOT NULL,
                    provenance TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_em_ev_student ON em_evidence(student_id);
                CREATE INDEX IF NOT EXISTS idx_em_ev_status ON em_evidence(review_status);
                """
            )
            db.commit()

    def _seed_default_prompts(self) -> None:
        with closing(self.connect()) as db:
            for p in DEFAULT_PROMPTS:
                db.execute(
                    """
                    INSERT OR REPLACE INTO em_prompts (
                        prompt_id, question_id, dimension, prompt_text,
                        info_box_focus, why_it_matters, intended_learning_objective,
                        rubric_version, graph_version, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        p.prompt_id,
                        p.question_id,
                        p.dimension.value if isinstance(p.dimension, EMDimension) else p.dimension,
                        p.prompt_text,
                        p.info_box_focus,
                        p.why_it_matters,
                        p.intended_learning_objective,
                        p.rubric_version,
                        p.graph_version,
                        p.provenance,
                    ),
                )
            db.commit()

    def get_prompt_for_question(self, question_id: str) -> Optional[EMReflectionPrompt]:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM em_prompts WHERE question_id = ? LIMIT 1;", (question_id,)
            ).fetchone()
            if not row:
                return None
            return EMReflectionPrompt(
                prompt_id=row["prompt_id"],
                question_id=row["question_id"],
                dimension=EMDimension(row["dimension"]),
                prompt_text=row["prompt_text"],
                info_box_focus=row["info_box_focus"],
                why_it_matters=row["why_it_matters"],
                intended_learning_objective=row["intended_learning_objective"],
                rubric_version=row["rubric_version"],
                graph_version=row["graph_version"],
                provenance=row["provenance"],
            )

    def record_response(
        self,
        student_id: str,
        question_id: str,
        prompt_id: str,
        attempt_id: str,
        response_text: str,
        status: EMResponseStatus = EMResponseStatus.SUBMITTED,
    ) -> EMReflectionResponse:
        resp_id = f"em-resp-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        resp = EMReflectionResponse(
            response_id=resp_id,
            student_id=student_id,
            question_id=question_id,
            prompt_id=prompt_id,
            attempt_id=attempt_id,
            response_text=response_text,
            status=status,
            submitted_at=now,
        )
        with closing(self.connect()) as db:
            db.execute(
                """
                INSERT INTO em_responses (
                    response_id, student_id, question_id, prompt_id,
                    attempt_id, response_text, status, submitted_at, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    resp.response_id,
                    resp.student_id,
                    resp.question_id,
                    resp.prompt_id,
                    resp.attempt_id,
                    resp.response_text,
                    resp.status.value if isinstance(resp.status, EMResponseStatus) else resp.status,
                    resp.submitted_at,
                    resp.provenance,
                ),
            )
            db.commit()
        return resp

    def get_response_for_student_question(
        self, student_id: str, question_id: str
    ) -> Optional[EMReflectionResponse]:
        with closing(self.connect()) as db:
            row = db.execute(
                """
                SELECT * FROM em_responses
                WHERE student_id = ? AND question_id = ?
                ORDER BY submitted_at DESC LIMIT 1;
                """,
                (student_id, question_id),
            ).fetchone()
            if not row:
                return None
            return EMReflectionResponse(
                response_id=row["response_id"],
                student_id=row["student_id"],
                question_id=row["question_id"],
                prompt_id=row["prompt_id"],
                attempt_id=row["attempt_id"],
                response_text=row["response_text"],
                status=EMResponseStatus(row["status"]),
                submitted_at=row["submitted_at"],
                provenance=row["provenance"],
            )

    def get_response_for_attempt(
        self, student_id: str, attempt_id: str
    ) -> Optional[EMReflectionResponse]:
        with closing(self.connect()) as db:
            row = db.execute(
                """
                SELECT * FROM em_responses
                WHERE student_id = ? AND attempt_id = ?
                ORDER BY submitted_at DESC LIMIT 1;
                """,
                (student_id, attempt_id),
            ).fetchone()
            if not row:
                return None
            return EMReflectionResponse(
                response_id=row["response_id"],
                student_id=row["student_id"],
                question_id=row["question_id"],
                prompt_id=row["prompt_id"],
                attempt_id=row["attempt_id"],
                response_text=row["response_text"],
                status=EMResponseStatus(row["status"]),
                submitted_at=row["submitted_at"],
                provenance=row["provenance"],
            )

    def get_evidence_for_attempt(self, attempt_id: str) -> Optional[EMEvidenceRecord]:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM em_evidence WHERE attempt_id = ? ORDER BY created_at DESC LIMIT 1;",
                (attempt_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_evidence(row)

    def create_evidence_record(
        self,
        student_id: str,
        question_id: str,
        dimension: EMDimension,
        relevant_concepts: List[str],
        evidence_excerpt: str,
        classification_method: str = "rule_based_deterministic",
        model_or_rubric_version: str = "rubric-keen-v1",
        confidence: float = 0.85,
        response_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
    ) -> EMEvidenceRecord:
        ev_id = f"em-ev-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        rec = EMEvidenceRecord(
            evidence_id=ev_id,
            response_id=response_id,
            attempt_id=attempt_id,
            student_id=student_id,
            question_id=question_id,
            dimension=dimension,
            relevant_concepts=relevant_concepts,
            evidence_excerpt=evidence_excerpt,
            classification_method=classification_method,
            model_or_rubric_version=model_or_rubric_version,
            confidence=confidence,
            review_status=EMReviewStatus.PROPOSED,
            created_at=now,
        )
        with closing(self.connect()) as db:
            db.execute(
                """
                INSERT INTO em_evidence (
                    evidence_id, response_id, attempt_id, student_id,
                    question_id, dimension, relevant_concepts, evidence_excerpt,
                    classification_method, model_or_rubric_version, confidence,
                    review_status, instructor_notes, reviewed_at, reviewer_id,
                    created_at, graph_version, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    rec.evidence_id,
                    rec.response_id,
                    rec.attempt_id,
                    rec.student_id,
                    rec.question_id,
                    rec.dimension.value
                    if isinstance(rec.dimension, EMDimension)
                    else rec.dimension,
                    json.dumps(rec.relevant_concepts),
                    rec.evidence_excerpt,
                    rec.classification_method,
                    rec.model_or_rubric_version,
                    rec.confidence,
                    rec.review_status.value
                    if isinstance(rec.review_status, EMReviewStatus)
                    else rec.review_status,
                    rec.instructor_notes,
                    rec.reviewed_at,
                    rec.reviewer_id,
                    rec.created_at,
                    rec.graph_version,
                    rec.provenance,
                ),
            )
            db.commit()
        return rec

    def get_evidence(self, evidence_id: str) -> Optional[EMEvidenceRecord]:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM em_evidence WHERE evidence_id = ? LIMIT 1;", (evidence_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_evidence(row)

    def list_all_evidence(self, review_status: Optional[str] = None) -> List[EMEvidenceRecord]:
        with closing(self.connect()) as db:
            if review_status:
                rows = db.execute(
                    "SELECT * FROM em_evidence WHERE review_status = ? ORDER BY created_at DESC;",
                    (review_status,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM em_evidence ORDER BY created_at DESC;").fetchall()
            return [self._row_to_evidence(r) for r in rows]

    def get_evidence_for_student(self, student_id: str) -> List[EMEvidenceRecord]:
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT * FROM em_evidence WHERE student_id = ? ORDER BY created_at DESC;",
                (student_id,),
            ).fetchall()
            return [self._row_to_evidence(r) for r in rows]

    def review_evidence(
        self,
        evidence_id: str,
        status: EMReviewStatus,
        notes: Optional[str] = None,
        reviewer_id: str = "instructor-admin",
    ) -> Optional[EMEvidenceRecord]:
        now = datetime.now(timezone.utc).isoformat()
        status_val = status.value if isinstance(status, EMReviewStatus) else status
        with closing(self.connect()) as db:
            db.execute(
                """
                UPDATE em_evidence
                SET review_status = ?, instructor_notes = ?, reviewed_at = ?, reviewer_id = ?
                WHERE evidence_id = ?;
                """,
                (status_val, notes, now, reviewer_id, evidence_id),
            )
            db.commit()
        return self.get_evidence(evidence_id)

    def student_em_summary(self, student_id: str) -> Dict[str, Any]:
        """Provides an EM evidence summary for a student, strictly isolated from technical mastery."""
        records = self.get_evidence_for_student(student_id)
        counts_by_status = {"PROPOSED": 0, "ACCEPTED": 0, "REJECTED": 0, "NEEDS_REVISION": 0}
        counts_by_dimension = {"C": 0, "X": 0, "V": 0}
        accepted_by_dimension = {"C": 0, "X": 0, "V": 0}

        for r in records:
            st = (
                r.review_status.value
                if isinstance(r.review_status, EMReviewStatus)
                else r.review_status
            )
            dim = r.dimension.value if isinstance(r.dimension, EMDimension) else r.dimension
            counts_by_status[st] = counts_by_status.get(st, 0) + 1
            counts_by_dimension[dim] = counts_by_dimension.get(dim, 0) + 1
            if st == "ACCEPTED":
                accepted_by_dimension[dim] = accepted_by_dimension.get(dim, 0) + 1

        return {
            "student_id": student_id,
            "total_observations": len(records),
            "counts_by_status": counts_by_status,
            "counts_by_dimension": counts_by_dimension,
            "accepted_by_dimension": accepted_by_dimension,
            "has_insufficient_evidence": len(records) == 0
            or accepted_by_dimension == {"C": 0, "X": 0, "V": 0},
            "records": [r.to_dict() for r in records],
            "disclaimer": "EM evidence records reflect observed student reflection behaviors in synthetic exercises. They are NOT validated psychological metrics of underlying mindset.",
        }

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row) -> EMEvidenceRecord:
        return EMEvidenceRecord(
            evidence_id=row["evidence_id"],
            response_id=row["response_id"],
            attempt_id=row["attempt_id"],
            student_id=row["student_id"],
            question_id=row["question_id"],
            dimension=EMDimension(row["dimension"]),
            relevant_concepts=json.loads(row["relevant_concepts"]),
            evidence_excerpt=row["evidence_excerpt"],
            classification_method=row["classification_method"],
            model_or_rubric_version=row["model_or_rubric_version"],
            confidence=row["confidence"],
            review_status=EMReviewStatus(row["review_status"]),
            instructor_notes=row["instructor_notes"],
            reviewed_at=row["reviewed_at"],
            reviewer_id=row["reviewer_id"],
            created_at=row["created_at"],
            graph_version=row["graph_version"],
            provenance=row["provenance"],
        )
