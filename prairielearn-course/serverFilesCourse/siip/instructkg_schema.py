"""InstructKG Schema definitions, deterministic validators, and error handling.
Validates upstream InstructKG artifacts: concept cards, pedagogical roles,
context clusters, candidate relationship pairs, and relation judgments.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Set

# Canonical pedagogical roles recognized in InstructKG extraction
PEDAGOGICAL_ROLES: Set[str] = {
    "Definition",
    "Example",
    "Explanation",
    "Observation",
    "Procedure",
    "Principle",
    "Caveat",
    "NA",
}

# Supported relation types
ALLOWED_RELATIONS: Set[str] = {"depends_on", "part_of"}

# Regex for uppercase concept identifiers (e.g. INNER_JOIN, LEFT_OUTER_JOIN, NULL_SEMANTICS)
CONCEPT_ID_PATTERN = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)*$")


class InstructKGSchemaError(ValueError):
    """Raised when an InstructKG record fails schema validation."""

    pass


def parse_instructkg_json(text: str) -> Any:
    """Robustly parse JSON produced by LLMs or JSONL pipelines.
    Strips markdown code fences (```json ... ```) and leading/trailing whitespace.
    """
    if not isinstance(text, str):
        raise InstructKGSchemaError(
            f"Expected string input for JSON parsing, got {type(text).__name__}"
        )

    cleaned = text.strip()
    if not cleaned:
        raise InstructKGSchemaError("Cannot parse empty JSON string")

    # Strip markdown code blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InstructKGSchemaError(
            f"Malformed JSON: {exc.msg} at line {exc.lineno} col {exc.colno}"
        ) from exc


def validate_pedagogical_role(role: Any) -> str:
    """Validate and normalize a pedagogical role string."""
    if not isinstance(role, str) or not role.strip():
        return "NA"

    normalized = role.strip()
    title_norm = normalized.title()
    if title_norm in PEDAGOGICAL_ROLES:
        return title_norm
    if normalized.upper() == "NA":
        return "NA"

    raise InstructKGSchemaError(
        f"Invalid pedagogical role '{role}'. Allowed roles: {sorted(PEDAGOGICAL_ROLES)}"
    )


def validate_concept_identifier(name: Any) -> str:
    """Ensure concept identifier conforms to uppercase token format."""
    if not isinstance(name, str) or not name.strip():
        raise InstructKGSchemaError("Concept identifier must be a non-empty string")

    clean_name = name.strip()
    if not CONCEPT_ID_PATTERN.match(clean_name):
        raise InstructKGSchemaError(
            f"Concept identifier '{clean_name}' does not match pattern [A-Z0-9]+(?:_[A-Z0-9]+)*"
        )
    return clean_name


def validate_concept_card(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate concept card schema from concept_cards.jsonl."""
    if not isinstance(record, dict):
        raise InstructKGSchemaError("Concept card record must be a JSON object")

    raw_id = record.get("concept_id") or record.get("name") or record.get("id")
    concept_id = validate_concept_identifier(raw_id)
    role = validate_pedagogical_role(record.get("pedagogical_role") or record.get("role"))

    summary = record.get("summary") or record.get("definition") or ""
    if not isinstance(summary, str):
        raise InstructKGSchemaError("Concept summary/definition must be a string")

    evidence_chunks = record.get("evidence_chunks", [])
    if not isinstance(evidence_chunks, list):
        raise InstructKGSchemaError("evidence_chunks must be a list")

    for i, chunk in enumerate(evidence_chunks):
        if isinstance(chunk, str):
            continue
        elif isinstance(chunk, dict):
            if "chunk_id" not in chunk and "text" not in chunk:
                raise InstructKGSchemaError(f"Evidence chunk at index {i} missing chunk_id or text")
        else:
            raise InstructKGSchemaError(
                f"Invalid evidence chunk type at index {i}: {type(chunk).__name__}"
            )

    frequency = record.get("frequency", len(evidence_chunks))
    if not isinstance(frequency, int) or frequency < 0:
        raise InstructKGSchemaError("Frequency must be a non-negative integer")

    return {
        "concept_id": concept_id,
        "name": concept_id,
        "pedagogical_role": role,
        "summary": summary,
        "evidence_chunks": evidence_chunks,
        "frequency": frequency,
        "source_lecture": str(record.get("source_lecture", "")),
    }


def validate_context_cluster(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate context cluster schema from context_clusters.jsonl."""
    if not isinstance(record, dict):
        raise InstructKGSchemaError("Context cluster record must be a JSON object")

    cluster_id = record.get("cluster_id")
    if cluster_id is None or (not isinstance(cluster_id, (int, str))):
        raise InstructKGSchemaError("cluster_id must be an integer or non-empty string")

    cluster_label = record.get("cluster_label") or record.get("label", "")
    if not isinstance(cluster_label, str):
        raise InstructKGSchemaError("cluster_label must be a string")

    member_concepts = record.get("member_concepts", [])
    if not isinstance(member_concepts, list):
        raise InstructKGSchemaError("member_concepts must be a list of concept identifiers")

    validated_members = [validate_concept_identifier(m) for m in member_concepts]
    if len(validated_members) == 0:
        raise InstructKGSchemaError("Context cluster must have at least one member concept")

    representative_chunks = record.get("representative_chunks", [])
    if not isinstance(representative_chunks, list):
        raise InstructKGSchemaError("representative_chunks must be a list")

    return {
        "cluster_id": str(cluster_id),
        "cluster_label": cluster_label,
        "member_concepts": validated_members,
        "representative_chunks": representative_chunks,
        "metadata": record.get("metadata", {}),
    }


def validate_candidate_pair(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate candidate relationship pair from pairpackets.jsonl."""
    if not isinstance(record, dict):
        raise InstructKGSchemaError("Candidate pair record must be a JSON object")

    raw_a = record.get("concept_a")
    if raw_a is None and isinstance(record.get("A"), dict):
        raw_a = record["A"].get("name")
    raw_b = record.get("concept_b")
    if raw_b is None and isinstance(record.get("B"), dict):
        raw_b = record["B"].get("name")

    concept_a = validate_concept_identifier(raw_a)
    concept_b = validate_concept_identifier(raw_b)

    if concept_a == concept_b:
        raise InstructKGSchemaError(f"Candidate pair cannot connect concept to itself: {concept_a}")

    shared_clusters = record.get("shared_clusters", [])
    if not isinstance(shared_clusters, list):
        raise InstructKGSchemaError("shared_clusters must be a list")

    evidence_chunks = record.get("evidence_chunks", [])
    if not isinstance(evidence_chunks, list):
        raise InstructKGSchemaError("evidence_chunks must be a list")

    co_occurrence_count = record.get("co_occurrence_count", len(evidence_chunks))
    if not isinstance(co_occurrence_count, int) or co_occurrence_count < 0:
        raise InstructKGSchemaError("co_occurrence_count must be a non-negative integer")

    pair_id = record.get("pair_id") or f"{concept_a}::{concept_b}"

    return {
        "pair_id": str(pair_id),
        "concept_a": concept_a,
        "concept_b": concept_b,
        "shared_clusters": shared_clusters,
        "evidence_chunks": evidence_chunks,
        "co_occurrence_count": co_occurrence_count,
    }


def validate_relation_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate relationship judgment from relations.jsonl."""
    if not isinstance(record, dict):
        raise InstructKGSchemaError("Relation record must be a JSON object")

    for key in ["A", "B"]:
        if key not in record or not isinstance(record[key], dict):
            raise InstructKGSchemaError(f"Relation record missing '{key}' node object")
        if "name" not in record[key]:
            raise InstructKGSchemaError(f"Node '{key}' missing 'name' attribute")

    a_name = validate_concept_identifier(record["A"]["name"])
    b_name = validate_concept_identifier(record["B"]["name"])

    if a_name == b_name:
        raise InstructKGSchemaError(f"Self-referential relations prohibited: {a_name} -> {b_name}")

    a_role = validate_pedagogical_role(record["A"].get("role"))
    b_role = validate_pedagogical_role(record["B"].get("role"))

    raw_rel = record.get("relation")
    relation: Optional[str] = None
    if isinstance(raw_rel, str):
        cleaned_rel = raw_rel.strip().lower().replace("-", "_").replace(" ", "_")
        if cleaned_rel not in {"null", "none", ""}:
            if cleaned_rel not in ALLOWED_RELATIONS:
                raise InstructKGSchemaError(
                    f"Unsupported relation '{raw_rel}'. Allowed: {sorted(ALLOWED_RELATIONS)} or null"
                )
            relation = cleaned_rel
    elif raw_rel is not None:
        raise InstructKGSchemaError(f"Invalid relation type: {type(raw_rel).__name__}")

    evidence_chunks = record.get("evidence_chunks", [])
    if not isinstance(evidence_chunks, list):
        raise InstructKGSchemaError("evidence_chunks must be a list")

    for i, chunk in enumerate(evidence_chunks):
        if not isinstance(chunk, dict) or not isinstance(chunk.get("text", ""), str):
            raise InstructKGSchemaError(
                f"Evidence chunk {i} must be a dictionary with 'text' string"
            )

    justification = record.get("justification", "")
    if not isinstance(justification, str):
        raise InstructKGSchemaError("justification must be a string")

    meta = record.get("_meta", {})
    if not isinstance(meta, dict):
        raise InstructKGSchemaError("_meta must be a dictionary")

    has_error = bool(meta.get("_error"))

    return {
        "A": {"name": a_name, "role": a_role},
        "B": {"name": b_name, "role": b_role},
        "relation": relation,
        "original_direction": [a_name, b_name],
        "justification": justification,
        "evidence_chunks": evidence_chunks,
        "_meta": meta,
        "invalid_inference": has_error,
    }
