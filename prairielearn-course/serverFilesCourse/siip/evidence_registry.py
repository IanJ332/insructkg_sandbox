"""Evidence Registry and Grounding Validator for SIIP Research Evaluation.

Maintains verifiable instructional evidence items, source provenance, hashes,
retrieval metrics, and knowledge graph relations. Distinguishes:
1. instructor_aligned: authentic course lecture excerpts and instructor-approved KG relations.
2. externally_curated: vetted SQL domain knowledge not directly from the course instructor.
3. developer_provisional: unreviewed research or engineering edges.
4. synthetic_fixture: offline software test fixtures.

Provides strict eligibility audits without fabricating instructional connections.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EvidenceItem:
    """A verified, immutable unit of pedagogical evidence."""

    evidence_id: str
    source_doc_id: str
    curriculum_origin: str
    text_excerpt: str
    location: str
    source_hash: str
    concept_identifiers: List[str]
    evidence_kind: (
        str  # instructor_aligned, externally_curated, developer_provisional, synthetic_fixture
    )
    instructor_approval_status: str  # approved, unreviewed, rejected, synthetic_fixture
    kg_version: Optional[str] = None
    kg_relation: Optional[str] = None
    kg_direction: Optional[List[str]] = None
    retrieval_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceRegistry:
    """Central registry of verified instructional excerpts and graph relations."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            self.root = Path(__file__).resolve().parents[3]
        else:
            self.root = root_dir

        self.items: Dict[str, EvidenceItem] = {}
        self._load_registered_evidence()

    def _load_registered_evidence(self) -> None:
        """Load known verifiable evidence sources."""
        # 1. ANU Course Database Schema Document
        schema_pdf = Path("D:/AI/Datasets/SIIP/anu/db_schema.pdf")
        if schema_pdf.exists():
            pdf_bytes = schema_pdf.read_bytes()
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            self.register(
                EvidenceItem(
                    evidence_id="ev-anu-schema-moviedb",
                    source_doc_id="anu-moviedb-schema-pdf",
                    curriculum_origin="ANU Relational Database Course (Wang et al., 2020)",
                    text_excerpt=(
                        "Database Schema: person(id, first_name, last_name, year_born); "
                        "movie(title, production_year, country, run_time, major_genre); "
                        "director(id, title, production_year); "
                        "writer(id, title, production_year, credits); "
                        "Role(id, title, production_year, description, credits); "
                        "movie_award(title, production_year, award_name, year_of_award, category, result); "
                        "director_award(id, title, production_year, award_name, year_of_award, category, result); "
                        "writer_award(id, title, production_year, award_name, year_of_award, category, result)."
                    ),
                    location="db_schema.pdf:page 1",
                    source_hash=pdf_hash,
                    concept_identifiers=["RELATIONAL_SCHEMA", "FOREIGN_KEYS", "PRIMARY_KEYS"],
                    evidence_kind="instructor_aligned",
                    instructor_approval_status="approved",
                    retrieval_score=1.0,
                )
            )

        # 2. Developer provisional relations (from provisional_relations.jsonl)
        prov_file = (
            self.root
            / "prairielearn-course/serverFilesCourse/siip/data/provisional_relations.jsonl"
        )
        if prov_file.exists():
            prov_bytes = prov_file.read_bytes()
            prov_hash = hashlib.sha256(prov_bytes).hexdigest()
            for line in prov_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    src = data["A"]["name"]
                    tgt = data["B"]["name"]
                    rel = data.get("relation", "depends_on")
                    just = data.get("justification", "")
                    self.register(
                        EvidenceItem(
                            evidence_id=f"ev-prov-{src}-{tgt}",
                            source_doc_id="siip-provisional-relations",
                            curriculum_origin="SIIP Sandbox Provisional Annotations",
                            text_excerpt=f"{src} {rel} {tgt}. {just}",
                            location=f"provisional_relations.jsonl:{src}->{tgt}",
                            source_hash=prov_hash,
                            concept_identifiers=[src, tgt],
                            evidence_kind="developer_provisional",
                            instructor_approval_status="unreviewed",
                            kg_version="siip-provisional-v1",
                            kg_relation=rel,
                            kg_direction=[src, tgt],
                            retrieval_score=None,
                        )
                    )
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        # 3. Synthetic contract fixture (explicitly marked synthetic)
        fixture_lesson = self.root / "tests/fixtures/lesson.md"
        if fixture_lesson.exists():
            f_bytes = fixture_lesson.read_bytes()
            f_hash = hashlib.sha256(f_bytes).hexdigest()
            self.register(
                EvidenceItem(
                    evidence_id="ev-fixture-lesson-join",
                    source_doc_id="tests/fixtures/lesson.md",
                    curriculum_origin="SIIP Offline Test Suite",
                    text_excerpt=(
                        "An inner join returns matching row pairs. A join condition states how table columns correspond. "
                        "A left outer join preserves each row of its left table even without a right-side match. "
                        "Unmatched right-side attributes become NULL."
                    ),
                    location="lesson.md:L3-L6",
                    source_hash=f_hash,
                    concept_identifiers=[
                        "INNER_JOIN",
                        "JOIN_CONDITION",
                        "LEFT_OUTER_JOIN",
                        "NULL_SEMANTICS",
                    ],
                    evidence_kind="synthetic_fixture",
                    instructor_approval_status="synthetic_fixture",
                    retrieval_score=None,
                )
            )

    def register(self, item: EvidenceItem) -> None:
        self.items[item.evidence_id] = item

    def check_instructor_aligned_eligibility(
        self, case: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Audit whether this case has verified instructor-aligned lecture and KG evidence.

        Returns:
            (eligible: bool, reason: str, audit_details: Dict)
        """
        concepts = case.get("pedagogical_concepts", [])
        eid = case.get("exercise_id")

        # 1. Check for authentic instructor-aligned lecture excerpts for this exercise
        lecture_evidence = [
            it
            for it in self.items.values()
            if it.evidence_kind == "instructor_aligned"
            and any(c in it.concept_identifiers for c in concepts)
        ]

        # 2. Check for instructor-approved KG relations
        approved_kg_edges = [
            it
            for it in self.items.values()
            if it.instructor_approval_status == "approved"
            and it.kg_relation is not None
            and any(c in it.concept_identifiers for c in concepts)
        ]

        # 3. Check for provisional / unreviewed KG edges
        unreviewed_kg_edges = [
            it
            for it in self.items.values()
            if it.instructor_approval_status == "unreviewed"
            and it.kg_relation is not None
            and any(c in it.concept_identifiers for c in concepts)
        ]

        details = {
            "exercise_id": eid,
            "concepts": concepts,
            "instructor_aligned_lecture_count": len(lecture_evidence),
            "instructor_approved_kg_edges": len(approved_kg_edges),
            "unreviewed_provisional_kg_edges": len(unreviewed_kg_edges),
        }

        # ANU dataset did not deposit lecture slides (only db_schema.pdf and Submission.sqlite).
        # Therefore, authentic instructor-approved lecture RAG and approved KG edges are empty.
        if not approved_kg_edges:
            reason = (
                f"Exercise {eid} has 0 instructor-approved Knowledge Graph edges "
                f"covering concepts {concepts}. Provisional edges are unreviewed."
            )
            return False, reason, details

        return True, "Eligible for instructor-aligned KG comparison", details

    def get_provisional_kg_subgraph(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """Extract available provisional KG edges matching the exercise concepts.

        Clearly labels them as developer-provisional and unreviewed.
        """
        concepts = set(case.get("pedagogical_concepts", []))
        matched_edges = []
        for it in self.items.values():
            if it.kg_relation and it.kg_direction:
                src, tgt = it.kg_direction
                if src in concepts or tgt in concepts:
                    matched_edges.append(
                        {
                            "source": src,
                            "relation": it.kg_relation,
                            "target": tgt,
                            "review_status": it.instructor_approval_status,
                            "evidence_kind": it.evidence_kind,
                            "source_doc": it.source_doc_id,
                        }
                    )

        return {
            "focus_concepts": list(concepts),
            "verified_subgraph": matched_edges,
            "instructor_approved": False,
            "graph_status": (
                "developer_provisional_unreviewed" if matched_edges else "no_coverage"
            ),
        }
