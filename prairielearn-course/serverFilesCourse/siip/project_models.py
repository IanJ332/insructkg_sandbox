"""Data Models for Dynamic Personalized SQL Project Specifications (Phase 5.2).

Represents 3-stage dynamic projects grounded in student domain interests,
concept gap diagnostics, and InstructKG prerequisite rankings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class StudentInterest(str, Enum):
    HEALTHCARE = "healthcare"
    PUBLIC_TRANSIT = "public_transit"
    GAMING = "gaming"
    CLIMATE = "climate"
    FINTECH = "fintech"


STUDENT_INTEREST_PROFILES: Dict[str, Dict[str, str]] = {
    "S001": {
        "interest": StudentInterest.HEALTHCARE.value,
        "label": "Healthcare & Clinical Operations",
        "context": "Hospital patient admissions, outpatient clinics, and physician staffing.",
    },
    "S002": {
        "interest": StudentInterest.PUBLIC_TRANSIT.value,
        "label": "Public Transit & Fleet Operations",
        "context": "Urban transit routes, bus stop coverage, vehicle maintenance, and passenger tap logs.",
    },
    "S003": {
        "interest": StudentInterest.GAMING.value,
        "label": "Online Gaming & Matchmaking Platforms",
        "context": "Multiplayer gamer guilds, matchmaking lobbies, server latency, and unranked players.",
    },
    "S004": {
        "interest": StudentInterest.CLIMATE.value,
        "label": "Renewable Energy & Environmental Monitoring",
        "context": "Solar microgrids, battery storage nodes, weather station sensors, and unmonitored zones.",
    },
    "S005": {
        "interest": StudentInterest.FINTECH.value,
        "label": "E-Commerce & Digital Payments",
        "context": "Merchant stores, customer orders, payment gateway transactions, and unfulfilled shipments.",
    },
}


@dataclass
class ProjectMilestone:
    milestone_index: int  # 1, 2, 3
    title: str
    task_description: str
    target_concepts: List[str]
    difficulty_rank: int  # 1 (Foundational), 2 (Intermediate), 3 (Advanced)
    concept_depth: int  # Graph depth from InstructKG root
    reference_sql: str
    evaluation_rubric: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectSpecification:
    project_id: str
    student_id: str
    domain_interest: str
    title: str
    scenario_narrative: str
    schema_ddl: str
    milestones: List[ProjectMilestone]
    target_concepts: List[str]
    generation_provenance: Dict[str, Any]
    created_at: str
    instructor_approval_status: str = "PROVISIONAL"  # 'PROVISIONAL', 'APPROVED', 'REVISED'
    instructor_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["milestones"] = [m.to_dict() if hasattr(m, "to_dict") else m for m in self.milestones]
        return d
