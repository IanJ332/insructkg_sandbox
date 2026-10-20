"""Entrepreneurial Mindset (EM) Graph Schema and Evidence Models for SIIP Track A.

Defines the KEEN 3C dimensions:
- Curiosity (C)
- Connections (X)
- Creating Value (V)

Strict separation between:
1. Technical concept mastery vs EM behavioral evidence.
2. Intended activity EM learning objectives vs observed student behavioral evidence.
3. Model-proposed observations vs instructor-approved evidence.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class EMDimension(str, enum.Enum):
    CURIOSITY = "C"
    CONNECTIONS = "X"
    CREATING_VALUE = "V"


class EMReviewStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"


class EMResponseStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    SKIPPED = "SKIPPED"


@dataclass
class EMActivityObjective:
    """Intended EM learning objective linked to a learning activity/question."""

    activity_id: str
    dimension: EMDimension
    title: str
    pedagogical_rationale: str
    target_concepts: List[str]
    graph_version: str = "siip-em-graph-v1"
    provenance: str = "synthetic_track_a"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EMReflectionPrompt:
    """Reflection prompt presented to students following selected SQL activities."""

    prompt_id: str
    question_id: str
    dimension: EMDimension
    prompt_text: str
    info_box_focus: str
    why_it_matters: str
    intended_learning_objective: str
    rubric_version: str = "rubric-keen-v1"
    graph_version: str = "siip-em-graph-v1"
    provenance: str = "synthetic_track_a"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EMReflectionResponse:
    """Learner's response or explicit skip of an optional EM reflection."""

    response_id: str
    student_id: str
    question_id: str
    prompt_id: str
    attempt_id: str
    response_text: str
    status: EMResponseStatus
    submitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provenance: str = "synthetic_learner_interaction"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EMEvidenceRecord:
    """Observed behavioral EM evidence record awaiting or post instructor review."""

    evidence_id: str
    student_id: str
    question_id: str
    dimension: EMDimension
    relevant_concepts: List[str]
    evidence_excerpt: str
    classification_method: str  # 'rule_based_deterministic', 'rubric_matching', 'model_assisted'
    model_or_rubric_version: str
    confidence: float
    review_status: EMReviewStatus = EMReviewStatus.PROPOSED
    response_id: Optional[str] = None
    attempt_id: Optional[str] = None
    instructor_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    graph_version: str = "siip-em-graph-v1"
    provenance: str = "synthetic_track_a"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dimension"] = (
            self.dimension.value if isinstance(self.dimension, EMDimension) else self.dimension
        )
        d["review_status"] = (
            self.review_status.value
            if isinstance(self.review_status, EMReviewStatus)
            else self.review_status
        )
        return d
