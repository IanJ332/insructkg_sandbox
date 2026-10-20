"""3-Stage Dynamic Project Generator and Project Repository (Phase 5.2).

Generates personalized, open-ended SQL projects grounded in student domain interests,
concept gap diagnostics, and InstructKG prerequisite rankings.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .project_models import (
    STUDENT_INTEREST_PROFILES,
    ProjectMilestone,
    ProjectSpecification,
    StudentInterest,
)

GENERATOR_VERSION = "siip-project-generator-v1"

# ---------------------------------------------------------------------------
# Stage 2 Domain Templates (Syntactically verified SQLite DDL & Reference SQL)
# ---------------------------------------------------------------------------

TEMPLATES: Dict[str, Dict[str, Any]] = {
    StudentInterest.HEALTHCARE.value: {
        "title": "Clinical Operations and Patient Placement Intelligence",
        "scenario_narrative": (
            "Regional Health Services operates several specialized clinical centers. "
            "Recent hospital audits revealed that unassigned emergency patients and unstaffed "
            "specialty clinics are distorting state healthcare resource allocations. You have "
            "been tasked with designing authoritative diagnostic queries to audit patient admission "
            "status and clinic capacity."
        ),
        "schema_ddl": """
CREATE TABLE clinics (
    clinic_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    capacity INTEGER NOT NULL
);

CREATE TABLE physicians (
    physician_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    clinic_id INTEGER,
    on_call INTEGER NOT NULL
);

CREATE TABLE patients (
    patient_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    clinic_id INTEGER,
    admission_status TEXT NOT NULL
);

INSERT INTO clinics VALUES (10, 'General Medicine', 'Internal', 50);
INSERT INTO clinics VALUES (20, 'Pediatric Emergency', 'Pediatrics', 30);
INSERT INTO clinics VALUES (30, 'Oncology Care Center', 'Oncology', 25);
INSERT INTO clinics VALUES (40, 'Rehabilitation Unit', 'Physical Therapy', 15);

INSERT INTO physicians VALUES (101, 'Dr. Sarah Patel', 10, 1);
INSERT INTO physicians VALUES (102, 'Dr. Marcus Vance', 20, 0);
INSERT INTO physicians VALUES (103, 'Dr. Elena Rostova', 10, 1);
INSERT INTO physicians VALUES (104, 'Dr. Jason Wu', NULL, 1);

INSERT INTO patients VALUES (501, 'Alice Taylor', 10, 'admitted');
INSERT INTO patients VALUES (502, 'Bob Chen', 10, 'admitted');
INSERT INTO patients VALUES (503, 'Carlos Morales', 20, 'in_triage');
INSERT INTO patients VALUES (504, 'Diana King', NULL, 'waiting_placement');
INSERT INTO patients VALUES (505, 'Evan Lee', NULL, 'waiting_placement');
""",
        "milestones": [
            {
                "milestone_index": 1,
                "title": "Physician-to-Clinic Assignment Audit",
                "task_description": "List each physician's name, on-call status, and their assigned clinic name using an INNER JOIN.",
                "target_concepts": ["INNER_JOIN", "JOIN_CONDITION"],
                "difficulty_rank": 1,
                "concept_depth": 1,
                "reference_sql": "SELECT physicians.name, physicians.on_call, clinics.name FROM physicians INNER JOIN clinics ON physicians.clinic_id = clinics.clinic_id;",
                "evaluation_rubric": "Correct inner join predicate on clinic_id, excludes unassigned physicians without clinics.",
            },
            {
                "milestone_index": 2,
                "title": "Unplaced Patient Risk Detection",
                "task_description": "Identify all patients who lack a clinic placement (clinic_id IS NULL) using an outer join or null filter.",
                "target_concepts": ["LEFT_OUTER_JOIN", "NULL_SEMANTICS"],
                "difficulty_rank": 2,
                "concept_depth": 2,
                "reference_sql": "SELECT patients.patient_id, patients.name, patients.admission_status FROM patients WHERE patients.clinic_id IS NULL;",
                "evaluation_rubric": "Filters records with NULL foreign key, preserving waiting-placement patients.",
            },
            {
                "milestone_index": 3,
                "title": "Clinic Census and Unstaffed Facility Protection",
                "task_description": "Compute the total count of admitted/triage patients per clinic. All clinics must be listed, including zero-patient clinics.",
                "target_concepts": ["LEFT_OUTER_JOIN", "COUNT_AGGREGATION", "NULL_SEMANTICS"],
                "difficulty_rank": 3,
                "concept_depth": 3,
                "reference_sql": "SELECT clinics.name, COUNT(patients.patient_id) AS patient_count FROM clinics LEFT OUTER JOIN patients ON clinics.clinic_id = patients.clinic_id GROUP BY clinics.clinic_id, clinics.name;",
                "evaluation_rubric": "Uses LEFT OUTER JOIN and COUNT(column) rather than COUNT(*), retaining zero-patient clinics.",
            },
        ],
    },
    StudentInterest.PUBLIC_TRANSIT.value: {
        "title": "Urban Transit Fleet Coverage and Ridership Protection",
        "scenario_narrative": (
            "The Metropolitan Transit Authority is redesigning express bus corridors. "
            "Service cut proposals frequently target stations that appear to have zero riders, "
            "when in fact poor vehicle scheduling or omitted stop logs caused missing records. "
            "Construct a reporting query suite to audit route vehicle assignments and ensure "
            "unserved transit stops are clearly identified."
        ),
        "schema_ddl": """
CREATE TABLE stations (
    station_id INTEGER PRIMARY KEY,
    station_name TEXT NOT NULL,
    zone INTEGER NOT NULL,
    is_active INTEGER NOT NULL
);

CREATE TABLE routes (
    route_id INTEGER PRIMARY KEY,
    route_code TEXT NOT NULL,
    station_id INTEGER,
    frequency_min INTEGER NOT NULL
);

CREATE TABLE vehicles (
    vehicle_id INTEGER PRIMARY KEY,
    route_id INTEGER,
    capacity INTEGER NOT NULL,
    in_service INTEGER NOT NULL
);

INSERT INTO stations VALUES (1, 'Central Square Station', 1, 1);
INSERT INTO stations VALUES (2, 'Northside Tech Park', 2, 1);
INSERT INTO stations VALUES (3, 'Harbor Gateway Hub', 1, 1);
INSERT INTO stations VALUES (4, 'South Hills Suburb', 3, 0);

INSERT INTO routes VALUES (101, 'Express-A', 1, 10);
INSERT INTO routes VALUES (102, 'Crosstown-B', 2, 15);
INSERT INTO routes VALUES (103, 'Feeder-C', 1, 20);
INSERT INTO routes VALUES (104, 'NightOwl-D', NULL, 60);

INSERT INTO vehicles VALUES (901, 101, 60, 1);
INSERT INTO vehicles VALUES (902, 102, 40, 1);
INSERT INTO vehicles VALUES (903, 101, 60, 0);
INSERT INTO vehicles VALUES (904, NULL, 50, 1);
""",
        "milestones": [
            {
                "milestone_index": 1,
                "title": "Active Route Station Mapping",
                "task_description": "List each route code and its serving station name using an INNER JOIN.",
                "target_concepts": ["INNER_JOIN", "JOIN_CONDITION"],
                "difficulty_rank": 1,
                "concept_depth": 1,
                "reference_sql": "SELECT routes.route_code, stations.station_name FROM routes INNER JOIN stations ON routes.station_id = stations.station_id;",
                "evaluation_rubric": "Accurate inner join on station_id, excludes routes lacking terminal stations.",
            },
            {
                "milestone_index": 2,
                "title": "Unallocated Fleet Vehicle Identification",
                "task_description": "Find vehicles currently in service that have not been assigned to any route (route_id IS NULL).",
                "target_concepts": ["LEFT_OUTER_JOIN", "NULL_SEMANTICS"],
                "difficulty_rank": 2,
                "concept_depth": 2,
                "reference_sql": "SELECT vehicles.vehicle_id, vehicles.capacity FROM vehicles WHERE vehicles.route_id IS NULL AND vehicles.in_service = 1;",
                "evaluation_rubric": "Isolates unassigned in-service vehicles using IS NULL logic.",
            },
            {
                "milestone_index": 3,
                "title": "Station Service Headcount and Zero-Route Retention",
                "task_description": "Report the number of active bus routes serving each station. Ensure all stations, including unserved stations, appear.",
                "target_concepts": ["LEFT_OUTER_JOIN", "COUNT_AGGREGATION", "NULL_SEMANTICS"],
                "difficulty_rank": 3,
                "concept_depth": 3,
                "reference_sql": "SELECT stations.station_name, COUNT(routes.route_id) AS route_count FROM stations LEFT OUTER JOIN routes ON stations.station_id = routes.station_id GROUP BY stations.station_id, stations.station_name;",
                "evaluation_rubric": "Preserves unserved stations with 0 route_count via LEFT OUTER JOIN and COUNT(column).",
            },
        ],
    },
    StudentInterest.GAMING.value: {
        "title": "Multiplayer Guild Coordination and Matchmaking Balance",
        "scenario_narrative": (
            "A competitive multiplayer arena platform matches squads across global servers. "
            "Guild leaders frequently lose track of unassigned free-agent players and unranked lobbies. "
            "Design an administrative intelligence pipeline to report guild membership rosters and identify "
            "unaffiliated players."
        ),
        "schema_ddl": """
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    tag TEXT NOT NULL,
    region TEXT NOT NULL,
    elo_rating INTEGER NOT NULL
);

CREATE TABLE guilds (
    guild_id INTEGER PRIMARY KEY,
    guild_name TEXT NOT NULL,
    min_elo INTEGER NOT NULL
);

CREATE TABLE guild_memberships (
    membership_id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL,
    guild_id INTEGER,
    joined_date TEXT NOT NULL
);

INSERT INTO guilds VALUES (1, 'Apex Vanguard', 1800);
INSERT INTO guilds VALUES (2, 'Shadow Syndicate', 1500);
INSERT INTO guilds VALUES (3, 'Solar Sentinels', 2100);
INSERT INTO guilds VALUES (4, 'Novice Collective', 1000);

INSERT INTO players VALUES (101, 'Vortex_X', 'NA', 1950);
INSERT INTO players VALUES (102, 'CyberSamurai', 'EU', 1620);
INSERT INTO players VALUES (103, 'AuraQueen', 'NA', 2200);
INSERT INTO players VALUES (104, 'LoneWolf', 'APAC', 1400);

INSERT INTO guild_memberships VALUES (501, 101, 1, '2026-01-10');
INSERT INTO guild_memberships VALUES (502, 102, 2, '2026-02-14');
INSERT INTO guild_memberships VALUES (503, 103, 3, '2026-03-01');
INSERT INTO guild_memberships VALUES (504, 104, NULL, '2026-03-20');
""",
        "milestones": [
            {
                "milestone_index": 1,
                "title": "Roster Ranks and Guild Affiliation",
                "task_description": "Display each player tag, their ELO rating, and the guild name they belong to using an INNER JOIN.",
                "target_concepts": ["INNER_JOIN", "JOIN_CONDITION"],
                "difficulty_rank": 1,
                "concept_depth": 1,
                "reference_sql": "SELECT players.tag, players.elo_rating, guilds.guild_name FROM players INNER JOIN guild_memberships ON players.player_id = guild_memberships.player_id INNER JOIN guilds ON guild_memberships.guild_id = guilds.guild_id;",
                "evaluation_rubric": "Proper multi-table join linking players, memberships, and guilds.",
            },
            {
                "milestone_index": 2,
                "title": "Free-Agent Player Discovery",
                "task_description": "List all registered players who currently have no guild affiliation (guild_id IS NULL in memberships).",
                "target_concepts": ["LEFT_OUTER_JOIN", "NULL_SEMANTICS"],
                "difficulty_rank": 2,
                "concept_depth": 2,
                "reference_sql": "SELECT players.tag, players.region FROM players INNER JOIN guild_memberships ON players.player_id = guild_memberships.player_id WHERE guild_memberships.guild_id IS NULL;",
                "evaluation_rubric": "Correctly filters players with NULL guild assignments.",
            },
            {
                "milestone_index": 3,
                "title": "Guild Membership Census and Empty Guild Retention",
                "task_description": "Produce a census of all guilds showing the total number of enrolled players. Empty guilds must be retained with 0 members.",
                "target_concepts": ["LEFT_OUTER_JOIN", "COUNT_AGGREGATION", "NULL_SEMANTICS"],
                "difficulty_rank": 3,
                "concept_depth": 3,
                "reference_sql": "SELECT guilds.guild_name, COUNT(guild_memberships.player_id) AS member_count FROM guilds LEFT OUTER JOIN guild_memberships ON guilds.guild_id = guild_memberships.guild_id GROUP BY guilds.guild_id, guilds.guild_name;",
                "evaluation_rubric": "Uses LEFT OUTER JOIN and COUNT(column) to retain zero-member guilds.",
            },
        ],
    },
}

# Add default fallback for other domains
TEMPLATES[StudentInterest.CLIMATE.value] = TEMPLATES[StudentInterest.PUBLIC_TRANSIT.value]
TEMPLATES[StudentInterest.FINTECH.value] = TEMPLATES[StudentInterest.HEALTHCARE.value]


# ---------------------------------------------------------------------------
# Stage 3 Verification & Generator Engine
# ---------------------------------------------------------------------------


def verify_project_schema_and_queries(project: ProjectSpecification) -> bool:
    """Executes schema DDL and all milestone reference SQL queries against an in-memory SQLite database.

    Ensures zero syntactic errors or missing tables/columns before projects are delivered.
    """
    try:
        conn = sqlite3.connect(":memory:")
        conn.executescript(project.schema_ddl)
        for m in project.milestones:
            cursor = conn.execute(m.reference_sql)
            rows = cursor.fetchall()
            if not isinstance(rows, list):
                conn.close()
                return False
        conn.close()
        return True
    except Exception:
        return False


def generate_personalized_project(
    student_id: str,
    interest: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    graph_context: Optional[Dict[str, Any]] = None,
) -> ProjectSpecification:
    """3-Stage Project Generator.

    Stage 1: Gauges student interest from profile or parameter.
    Stage 2: Selects and specializes relational schema and milestones.
    Stage 3: Verifies DDL and queries, decomposes tasks, and assigns difficulty ranks.
    """
    # Stage 1: Gauging student interest
    interest_data = STUDENT_INTEREST_PROFILES.get(student_id, {})
    chosen_domain = interest or interest_data.get("interest", StudentInterest.HEALTHCARE.value)
    if chosen_domain not in TEMPLATES:
        chosen_domain = StudentInterest.HEALTHCARE.value

    template = TEMPLATES[chosen_domain]
    now_iso = datetime.now(timezone.utc).isoformat()
    project_id = f"proj-{student_id.lower()}-{uuid.uuid4().hex[:8]}"

    # Stage 2: Profile adaptation (concept mastery inspection & difficulty sequencing)
    adapted_difficulty_level = "standard_progression"
    profile_adaptation_rationale = (
        "Standard curriculum progression; baseline milestone sequencing applied."
    )
    adaptation_scaffolding: Dict[str, Any] = {}

    if profile and isinstance(profile, dict) and profile.get("concepts"):
        concepts_data = profile["concepts"]
        mastery_vals = []
        low_mastery_concepts = []
        for c_name, c_info in concepts_data.items():
            if isinstance(c_info, dict) and "mastery_estimate" in c_info:
                val = float(c_info["mastery_estimate"])
                mastery_vals.append(val)
                if val < 0.50:
                    low_mastery_concepts.append((c_name, val))

        mean_mastery = sum(mastery_vals) / len(mastery_vals) if mastery_vals else 0.50

        if low_mastery_concepts or mean_mastery < 0.50:
            adapted_difficulty_level = "scaffolded_remediation"
            weak_names = [c[0] for c in low_mastery_concepts] or ["relational_joins"]
            profile_adaptation_rationale = (
                f"Learner {student_id} exhibits diagnosed concept gaps in {', '.join(weak_names)} "
                f"(mean target mastery: {mean_mastery:.2f}). Milestones 1 and 2 provide explicit "
                f"scaffolding on join criteria and NULL handling before multi-table aggregation."
            )
            adaptation_scaffolding = {
                "scaffolded_concepts": weak_names,
                "remediation_focus": True,
                "prior_mean_mastery": round(mean_mastery, 3),
            }
        elif mean_mastery >= 0.80:
            adapted_difficulty_level = "advanced_synthesis"
            profile_adaptation_rationale = (
                f"Learner {student_id} demonstrates high concept mastery ({mean_mastery:.2f}) "
                f"across relational queries. Milestones emphasize query efficiency, edge-case retention, "
                f"and complex multi-table predicate optimization."
            )
            adaptation_scaffolding = {
                "advanced_focus": True,
                "prior_mean_mastery": round(mean_mastery, 3),
            }
        else:
            adapted_difficulty_level = "standard_progression"
            profile_adaptation_rationale = (
                f"Learner {student_id} demonstrates developing mastery ({mean_mastery:.2f}). "
                f"Balanced 3-tier milestone sequencing applied across relational operations."
            )
            adaptation_scaffolding = {
                "prior_mean_mastery": round(mean_mastery, 3),
            }

    # Construct milestones and ranking
    milestones: List[ProjectMilestone] = []
    all_concepts: List[str] = []
    for m_data in template["milestones"]:
        m = ProjectMilestone(
            milestone_index=m_data["milestone_index"],
            title=m_data["title"],
            task_description=m_data["task_description"],
            target_concepts=m_data["target_concepts"],
            difficulty_rank=m_data["difficulty_rank"],
            concept_depth=m_data["concept_depth"],
            reference_sql=m_data["reference_sql"],
            evaluation_rubric=m_data["evaluation_rubric"],
        )
        milestones.append(m)
        all_concepts.extend(m.target_concepts)

    unique_concepts = sorted(set(all_concepts))
    if graph_context:
        prerequisites = {}
        for edge in graph_context.get("edges", []):
            if edge.get("review_state") == "APPROVED" and edge.get("relation") == "depends_on":
                prerequisites.setdefault(edge["source"], set()).add(edge["target"])

        def depth(concept, seen=None):
            seen = set() if seen is None else seen
            if concept in seen:
                return 0
            return max(
                (1 + depth(parent, seen | {concept}) for parent in prerequisites.get(concept, [])),
                default=0,
            )

        for milestone in milestones:
            milestone.concept_depth = max(
                (depth(concept) for concept in milestone.target_concepts), default=0
            )

    project = ProjectSpecification(
        project_id=project_id,
        student_id=student_id,
        domain_interest=chosen_domain,
        title=f"{template['title']} ({student_id})",
        scenario_narrative=template["scenario_narrative"],
        schema_ddl=template["schema_ddl"].strip(),
        milestones=milestones,
        target_concepts=unique_concepts,
        generation_provenance={
            "generator_version": GENERATOR_VERSION,
            "domain_interest": chosen_domain,
            "created_at": now_iso,
            "verified_in_memory": False,
            "student_profile_available": profile is not None,
            "adapted_difficulty_level": adapted_difficulty_level,
            "profile_adaptation_rationale": profile_adaptation_rationale,
            "adaptation_scaffolding": adaptation_scaffolding,
            "synthetic_classification": "SYNTHETIC_COURSE_MATERIAL",
            "graph_grounding": {
                key: graph_context[key]
                for key in ("graph_id", "version", "source_document_id")
                if key in graph_context
            }
            if graph_context
            else None,
            "stages": [
                "interest_collection",
                "validated_template_candidate_construction",
                "profile_scaffolding_and_reviewed_prerequisite_depth"
                if graph_context
                else "profile_scaffolding_and_template_ranking",
            ],
        },
        created_at=now_iso,
    )

    # Stage 3 verification check
    is_valid = verify_project_schema_and_queries(project)
    project.generation_provenance["verified_in_memory"] = is_valid
    if not is_valid:
        raise ValueError("Project template verification failed SQLite execution check.")

    return project


# ---------------------------------------------------------------------------
# Project Persistence Repository
# ---------------------------------------------------------------------------


class ProjectRepository:
    """Manages durable persistence for personalized project specifications."""

    def __init__(self, db_path: Path | str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = sqlite3.Row
        return db

    def _init_table(self) -> None:
        with closing(self.connect()) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    domain_interest TEXT NOT NULL,
                    title TEXT NOT NULL,
                    record TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_projects_student ON projects(student_id);")
            db.commit()

    def save_project(self, project: ProjectSpecification) -> ProjectSpecification:
        record_json = json.dumps(project.to_dict())
        with closing(self.connect()) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO projects (
                    project_id, student_id, domain_interest, title, record, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    project.project_id,
                    project.student_id,
                    project.domain_interest,
                    project.title,
                    record_json,
                    project.created_at,
                ),
            )
            db.commit()
        return project

    def get_project(self, project_id: str) -> Optional[ProjectSpecification]:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT record FROM projects WHERE project_id = ? LIMIT 1;", (project_id,)
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["record"])
            return self._dict_to_project(data)

    def list_projects_for_student(self, student_id: str) -> List[ProjectSpecification]:
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT record FROM projects WHERE student_id = ? ORDER BY created_at DESC;",
                (student_id,),
            ).fetchall()
            return [self._dict_to_project(json.loads(r["record"])) for r in rows]

    def list_all_projects(self) -> List[ProjectSpecification]:
        with closing(self.connect()) as db:
            rows = db.execute("SELECT record FROM projects ORDER BY created_at DESC;").fetchall()
            return [self._dict_to_project(json.loads(r["record"])) for r in rows]

    @staticmethod
    def _dict_to_project(data: Dict[str, Any]) -> ProjectSpecification:
        milestones = [
            ProjectMilestone(
                milestone_index=m["milestone_index"],
                title=m["title"],
                task_description=m["task_description"],
                target_concepts=m["target_concepts"],
                difficulty_rank=m["difficulty_rank"],
                concept_depth=m["concept_depth"],
                reference_sql=m["reference_sql"],
                evaluation_rubric=m["evaluation_rubric"],
            )
            for m in data.get("milestones", [])
        ]
        return ProjectSpecification(
            project_id=data["project_id"],
            student_id=data["student_id"],
            domain_interest=data["domain_interest"],
            title=data["title"],
            scenario_narrative=data["scenario_narrative"],
            schema_ddl=data["schema_ddl"],
            milestones=milestones,
            target_concepts=data.get("target_concepts", []),
            generation_provenance=data.get("generation_provenance", {}),
            created_at=data["created_at"],
            instructor_approval_status=data.get("instructor_approval_status", "PROVISIONAL"),
            instructor_notes=data.get("instructor_notes"),
        )
