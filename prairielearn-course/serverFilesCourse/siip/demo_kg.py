"""Small, honest knowledge-graph workflow for the local SIIP demonstration.

The default is a clearly labeled deterministic synthetic fixture. The local mode
uses bounded Ollama extraction with an explicit fixture fallback. The selected
ORIGINAL_INSTRUCTKG_CHUNK_ONLY mode invokes pinned external original functions,
defers embeddings/clustering, and fails without substituting a fixture. Every
returned graph and edge records its actual extraction boundary.

The caller owns the persistence directory.  No module-global database or demo
output path is used, which keeps tests isolated and lets the dashboard select its
artifact directory explicitly.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Mapping

PIPELINE_VERSION = "siip-demo-kg-synthetic-fixture-v1"
EXTRACTION_METHOD = "synthetic_fixture_keyword_mapping"
SOURCE_TYPE = "synthetic_fixture"
SCIENTIFIC_BOUNDARY = "SYNTHETIC EXAMPLE KNOWLEDGE GRAPH — NOT ACTUAL INSTRUCTKG EXTRACTION"
_MUTATION_LOCK = threading.RLock()


def _serialize_mutation(method):
    @wraps(method)
    def locked(*args, **kwargs):
        # Dashboard threads share mutable drafts; published versions additionally
        # use exclusive filesystem publication across independent processes.
        with _MUTATION_LOCK:
            return method(*args, **kwargs)

    return locked


_CONCEPTS = (
    ("INNER_JOIN", "Inner Join"),
    ("LEFT_OUTER_JOIN", "Left Outer Join"),
    ("NULL_SEMANTICS", "NULL Semantics"),
    ("JOIN_PREDICATE", "Join Predicate"),
    ("MISSING_MATCHING_ROWS", "Missing Matching Rows"),
)

# In this relation convention, ``A depends_on B`` means B is a prerequisite of A.
_EDGE_FIXTURES = (
    ("INNER_JOIN", "depends_on", "JOIN_PREDICATE", ("inner join", "predicate"), 0.74),
    (
        "LEFT_OUTER_JOIN",
        "depends_on",
        "JOIN_PREDICATE",
        ("left outer join", "predicate"),
        0.78,
    ),
    (
        "MISSING_MATCHING_ROWS",
        "depends_on",
        "LEFT_OUTER_JOIN",
        ("missing", "unmatched", "left outer join"),
        0.76,
    ),
    (
        "NULL_SEMANTICS",
        "part_of",
        "LEFT_OUTER_JOIN",
        ("null", "left outer join"),
        0.68,
    ),
)


class DemoKGError(ValueError):
    """Raised when a demo graph request or persisted record is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json_write(path: Path, record: Mapping[str, Any], *, immutable=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        if immutable:
            # Same-filesystem hard-link publication is atomic and never replaces
            # an existing version, even across independent worker processes.
            os.link(temporary_name, path)
            os.unlink(temporary_name)
        else:
            os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DemoKGError(f"Knowledge graph record not found: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoKGError(f"Knowledge graph record is unreadable: {path.name}") from exc
    if not isinstance(record, dict):
        raise DemoKGError(f"Knowledge graph record must be an object: {path.name}")
    return record


def _source_text(source_record: Mapping[str, Any]) -> str:
    for field in ("content", "text", "extracted_text"):
        value = source_record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise DemoKGError("Source record requires non-empty content, text, or extracted_text")


def _source_document_id(source_record: Mapping[str, Any]) -> str:
    value = source_record.get("source_document_id") or source_record.get("document_id")
    if not isinstance(value, str) or not value.strip():
        raise DemoKGError("Source record requires a non-empty source_document_id")
    return value.strip()


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]


def _evidence_excerpt(text: str, keywords: tuple[str, ...]) -> str:
    candidates = _sentences(text)
    if not candidates:
        raise DemoKGError("Source record contains no usable evidence text")
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (
            -sum(keyword in item[1].lower() for keyword in lowered_keywords),
            item[0],
        ),
    )
    excerpt = ranked[0][1]
    if len(excerpt) > 320:
        excerpt = excerpt[:317].rstrip() + "..."
    return excerpt


def _edge_id(source: str, relation: str, target: str) -> str:
    digest = hashlib.sha256(f"{source}|{relation}|{target}".encode("utf-8")).hexdigest()
    return f"edge-{digest[:12]}"


class DemoKGRepository:
    """Filesystem repository for one or more synthetic demo knowledge graphs."""

    def __init__(self, persistence_directory: str | Path):
        self.root = Path(persistence_directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def _graph_directory(self, graph_id: str) -> Path:
        if not isinstance(graph_id, str) or not re.fullmatch(r"kg-[a-f0-9]{16}", graph_id):
            raise DemoKGError("Invalid graph_id")
        return self.root / graph_id

    def generate_candidates(self, source_record: Mapping[str, Any]) -> dict[str, Any]:
        """Generate and persist a graph using the explicitly configured mode.

        Repeating the call with the same source ID and content returns the existing
        draft, preserving any instructor decisions already made.
        """

        if not isinstance(source_record, Mapping):
            raise DemoKGError("source_record must be a mapping")
        document_id = _source_document_id(source_record)
        requested_mode = str(
            source_record.get("requested_extraction_mode")
            or os.environ.get("SIIP_DEMO_KG_MODE", "synthetic")
        )
        original_requested = requested_mode.lower() == "original_instructkg_chunk_only"
        text = "" if original_requested else _source_text(source_record)
        content_sha256 = (
            str(source_record.get("content_hash") or "")
            if original_requested
            else hashlib.sha256(text.encode("utf-8")).hexdigest()
        )
        local_requested = requested_mode.lower() == "local"
        model = os.environ.get("SIIP_LOCAL_KG_MODEL", "qwen3:8b")
        local_result = None
        fallback_reason = None
        extraction_method, pipeline_version = EXTRACTION_METHOD, PIPELINE_VERSION
        source_type, boundary = SOURCE_TYPE, SCIENTIFIC_BOUNDARY
        mode = "SYNTHETIC_FIXTURE"
        identity = f"{document_id}|{content_sha256}|{PIPELINE_VERSION}"
        identity += json.dumps(
            [
                source_record.get("version"),
                source_record.get("course_id"),
                source_record.get("module_id"),
            ],
            separators=(",", ":"),
        )
        if original_requested:
            from . import original_instructkg

            identity += f"|{original_instructkg.PIPELINE_VERSION}|{model}"
        if local_requested:
            from . import local_kg_extractor

            identity += f"|{local_kg_extractor.PIPELINE_VERSION}|{model}"
        graph_id = "kg-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        graph_directory = self._graph_directory(graph_id)
        draft_path = graph_directory / "draft.json"
        if draft_path.exists():
            return _read_json(draft_path)

        if original_requested:
            try:
                local_result = original_instructkg.generate(
                    source_record, graph_directory / "original_artifacts"
                )
            except (original_instructkg.OriginalPipelineError, OSError, ValueError) as exc:
                raise DemoKGError(str(exc)) from exc
            text = local_result["extracted_text"]
            content_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            extraction_method = original_instructkg.EXTRACTION_METHOD
            pipeline_version = original_instructkg.PIPELINE_VERSION
            source_type = "original_instructkg"
            boundary = original_instructkg.BOUNDARY
            mode = original_instructkg.MODE
        if local_requested:
            try:
                local_result = local_kg_extractor.extract_candidates(text, document_id, model=model)
                extraction_method = local_kg_extractor.EXTRACTION_METHOD
                pipeline_version = local_kg_extractor.PIPELINE_VERSION
                source_type = "local_llm_assisted_extraction"
                boundary = local_kg_extractor.SCIENTIFIC_BOUNDARY
                mode = local_kg_extractor.MODE
            except local_kg_extractor.LocalExtractionError as exc:
                fallback_reason = str(exc)

        nodes = [
            {
                "id": concept_id,
                "label": label,
                "source_document_id": document_id,
                "extraction_method": EXTRACTION_METHOD,
                "pipeline_version": PIPELINE_VERSION,
                "source_type": SOURCE_TYPE,
            }
            for concept_id, label in _CONCEPTS
        ]
        edges = []
        for source, relation, target, keywords, confidence in (
            () if original_requested else _EDGE_FIXTURES
        ):
            edges.append(
                {
                    "edge_id": _edge_id(source, relation, target),
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "evidence_excerpt": _evidence_excerpt(text, keywords),
                    "source_document_id": document_id,
                    "extraction_method": EXTRACTION_METHOD,
                    "pipeline_version": PIPELINE_VERSION,
                    "confidence": confidence,
                    "review_state": "UNREVIEWED",
                    "instructor_review_decision": None,
                    "reviewed_by": None,
                    "reviewed_at_utc": None,
                    "review_notes": "",
                    "source_type": SOURCE_TYPE,
                    "scientific_boundary": SCIENTIFIC_BOUNDARY,
                }
            )

        if local_result is not None:
            nodes = local_result["nodes"]
            edges = local_result["edges"]
        for node in nodes:
            node.setdefault("source_document_id", document_id)
            node.update(
                {
                    "extraction_method": extraction_method,
                    "pipeline_version": pipeline_version,
                    "source_type": source_type,
                    "scientific_boundary": boundary,
                }
            )
        for edge in edges:
            edge.setdefault("source_document_id", document_id)
            edge.update(
                {
                    "edge_id": _edge_id(edge["source"], edge["relation"], edge["target"]),
                    "extraction_method": extraction_method,
                    "pipeline_version": pipeline_version,
                    "source_type": source_type,
                    "scientific_boundary": boundary,
                    "review_state": "UNREVIEWED",
                    "instructor_review_decision": None,
                    "reviewed_by": None,
                    "reviewed_at_utc": None,
                    "review_notes": "",
                }
            )

        graph = {
            "graph_id": graph_id,
            "version": 0,
            "status": "DRAFT",
            "source_document_id": document_id,
            "source_version": source_record.get("version"),
            "course_id": source_record.get("course_id"),
            "module_id": source_record.get("module_id"),
            "source_original_filename": str(
                source_record.get("original_filename") or source_record.get("filename") or ""
            ),
            "source_content_sha256": content_sha256,
            "registered_content_hash": source_record.get("content_hash"),
            "generated_at_utc": _utc_now(),
            "updated_at_utc": None,
            "saved_at_utc": None,
            "extraction_method": extraction_method,
            "pipeline_version": pipeline_version,
            "source_type": source_type,
            "extraction_mode": mode,
            "requested_extraction_mode": requested_mode,
            "fallback_reason": fallback_reason,
            "extraction_metadata": local_result["extraction_metadata"] if local_result else {},
            "rejected_candidates": local_result["rejected_candidates"] if local_result else [],
            "actual_instructkg_extraction": original_requested,
            "extracted_text": local_result.get("extracted_text") if original_requested else None,
            "extracted_chunks": local_result.get("extracted_chunks")
            if original_requested
            else None,
            "scientific_boundary": boundary,
            "relation_direction_contract": (
                "For A depends_on B, B is a prerequisite of A; "
                "for A part_of B, A is a component of B."
            ),
            "nodes": nodes,
            "edges": edges,
        }
        _atomic_json_write(draft_path, graph)
        return copy.deepcopy(graph)

    def retrieve(self, graph_id: str, version: int | None = None) -> dict[str, Any]:
        """Retrieve the current draft or an immutable saved version."""

        graph_directory = self._graph_directory(graph_id)
        if version is None:
            path = graph_directory / "draft.json"
        else:
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise DemoKGError("version must be a positive integer")
            path = graph_directory / "versions" / f"v{version:04d}.json"
        return _read_json(path)

    def list_graphs(self) -> list[dict[str, Any]]:
        """List draft graphs without exposing their full evidence payloads."""

        result = []
        for path in sorted(self.root.glob("kg-*/draft.json")):
            graph = _read_json(path)
            result.append(
                {
                    "graph_id": graph["graph_id"],
                    "source_document_id": graph["source_document_id"],
                    "version": graph["version"],
                    "status": graph["status"],
                    "source_type": graph["source_type"],
                    "scientific_boundary": graph["scientific_boundary"],
                    "extraction_mode": graph.get("extraction_mode", "SYNTHETIC_FIXTURE"),
                }
            )
        return result

    def list_versions(self, graph_id: str) -> list[dict[str, Any]]:
        """List saved versions and their review counts."""

        versions_directory = self._graph_directory(graph_id) / "versions"
        result = []
        for path in sorted(versions_directory.glob("v*.json")):
            graph = _read_json(path)
            counts = {
                state: 0 for state in ("UNREVIEWED", "APPROVED", "REJECTED", "NEEDS_REVISION")
            }
            for edge in graph["edges"]:
                state = edge.get("review_state", "UNREVIEWED")
                counts[state] = counts.get(state, 0) + 1
            result.append(
                {
                    "graph_id": graph_id,
                    "version": graph["version"],
                    "saved_at_utc": graph["saved_at_utc"],
                    "review_counts": counts,
                    "source_type": graph["source_type"],
                }
            )
        return result

    @_serialize_mutation
    def review_edge(
        self,
        graph_id: str,
        edge_id: str,
        decision: str,
        reviewer_id: str,
        notes: str = "",
    ) -> dict[str, Any]:
        """Persist an instructor approval or rejection on the mutable draft."""

        normalized = decision.strip().upper() if isinstance(decision, str) else ""
        if normalized not in {"APPROVE", "REJECT", "NEEDS_REVISION"}:
            raise DemoKGError("decision must be APPROVE or REJECT or NEEDS_REVISION")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise DemoKGError("reviewer_id must identify the synthetic instructor")
        if not isinstance(notes, str):
            raise DemoKGError("notes must be a string")

        graph = self.retrieve(graph_id)
        matched = False
        reviewed_at = _utc_now()
        for edge in graph.get("edges", []):
            if edge.get("edge_id") == edge_id:
                edge.setdefault("review_history", []).append(
                    {
                        "decision": normalized,
                        "reviewer_id": reviewer_id.strip(),
                        "reviewed_at_utc": reviewed_at,
                        "notes": notes.strip(),
                    }
                )
                edge.update(
                    {
                        "review_state": {
                            "APPROVE": "APPROVED",
                            "REJECT": "REJECTED",
                            "NEEDS_REVISION": "NEEDS_REVISION",
                        }[normalized],
                        "instructor_review_decision": normalized,
                        "reviewed_by": reviewer_id.strip(),
                        "reviewed_at_utc": reviewed_at,
                        "review_notes": notes.strip(),
                    }
                )
                matched = True
                break
        if not matched:
            raise DemoKGError(f"Unknown edge_id: {edge_id}")
        graph["status"] = "DRAFT"
        graph["updated_at_utc"] = reviewed_at
        _atomic_json_write(self._graph_directory(graph_id) / "draft.json", graph)
        return copy.deepcopy(graph)

    @_serialize_mutation
    def save_version(self, graph_id: str) -> dict[str, Any]:
        """Save an immutable numbered snapshot of the reviewed draft."""

        graph = self.retrieve(graph_id)
        existing = self.list_versions(graph_id)
        next_version = max((item["version"] for item in existing), default=0) + 1
        saved_at = _utc_now()
        snapshot = copy.deepcopy(graph)
        snapshot.update(
            {
                "version": next_version,
                "status": "SAVED",
                "saved_at_utc": saved_at,
                "updated_at_utc": saved_at,
            }
        )
        version_path = self._graph_directory(graph_id) / "versions" / f"v{next_version:04d}.json"
        while True:
            try:
                _atomic_json_write(version_path, snapshot, immutable=True)
                break
            except FileExistsError:
                next_version += 1
                snapshot["version"] = next_version
                version_path = (
                    self._graph_directory(graph_id) / "versions" / f"v{next_version:04d}.json"
                )

        # Continue from the saved snapshot while clearly retaining draft mutability.
        draft = copy.deepcopy(snapshot)
        draft["status"] = "DRAFT"
        _atomic_json_write(self._graph_directory(graph_id) / "draft.json", draft)
        return snapshot


def generate_candidate_graph(
    source_record: Mapping[str, Any], persistence_directory: str | Path
) -> dict[str, Any]:
    """Functional integration API for candidate generation."""

    return DemoKGRepository(persistence_directory).generate_candidates(source_record)


def retrieve_graph(
    graph_id: str, persistence_directory: str | Path, version: int | None = None
) -> dict[str, Any]:
    """Functional integration API for graph retrieval."""

    return DemoKGRepository(persistence_directory).retrieve(graph_id, version)


def list_candidate_graphs(persistence_directory: str | Path) -> list[dict[str, Any]]:
    """Functional integration API for listing current graph drafts."""

    return DemoKGRepository(persistence_directory).list_graphs()


def list_graph_versions(graph_id: str, persistence_directory: str | Path) -> list[dict[str, Any]]:
    """Functional integration API for listing immutable graph versions."""

    return DemoKGRepository(persistence_directory).list_versions(graph_id)


def review_candidate_edge(
    graph_id: str,
    edge_id: str,
    decision: str,
    reviewer_id: str,
    persistence_directory: str | Path,
    notes: str = "",
) -> dict[str, Any]:
    """Functional integration API for instructor review."""

    return DemoKGRepository(persistence_directory).review_edge(
        graph_id, edge_id, decision, reviewer_id, notes
    )


def save_graph_version(graph_id: str, persistence_directory: str | Path) -> dict[str, Any]:
    """Functional integration API for version saving."""

    return DemoKGRepository(persistence_directory).save_version(graph_id)
