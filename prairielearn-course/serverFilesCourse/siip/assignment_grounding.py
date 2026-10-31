"""Resolve persisted local assignment lineage; never accept uploaded prompt instructions."""

import hashlib
import os
import re
from pathlib import Path

from .demo_authoring import DemoAuthoringRegistry
from .demo_kg import DemoKGRepository
from .identity import is_instructor_principal


def reviewed_concept_mapping(config, graph):
    """Apply only explicit synthetic-instructor mappings; never infer equivalence."""
    from .grader import QUESTIONS

    entries = config.get("concept_mapping", {})
    if not isinstance(entries, dict) or len(entries) > 12:
        raise ValueError("Invalid reviewed concept mapping")
    nodes = {node["id"] for node in graph["nodes"]}
    canonical = {tag for question in QUESTIONS.values() for tag in question["concepts"]}
    mapping = {}
    for source, entry in entries.items():
        if (
            source not in nodes
            or not isinstance(entry, dict)
            or set(entry) != {"canonical_id", "reviewed_by", "notes"}
            or not isinstance(entry["canonical_id"], str)
            or entry["canonical_id"] not in canonical
            or not is_instructor_principal(entry["reviewed_by"])
            or not isinstance(entry["notes"], str)
            or not 1 <= len(entry["notes"].strip()) <= 1000
        ):
            raise ValueError("Concept mapping requires source, canonical tag and instructor review")
        mapping[source] = entry["canonical_id"]
    resolved = [mapping.get(node, node) for node in nodes]
    if len(resolved) != len(set(resolved)):
        raise ValueError("Concept mapping would merge distinct graph nodes")
    return mapping


def validate_grounding(value):
    if not isinstance(value, dict) or set(value) != {
        "assignment_id",
        "course_id",
        "graph_id",
        "graph_version",
        "source_document_id",
        "source_version",
        "source_sha256",
    }:
        raise ValueError("Incomplete assignment grounding identifiers")
    for key in ("assignment_id", "course_id", "graph_id", "source_document_id"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value[key]):
            raise ValueError("Invalid grounding identifier")
    for key in ("graph_version", "source_version"):
        if type(value[key]) is not int or value[key] < 1:
            raise ValueError("Invalid grounding version")
    if not isinstance(value["source_sha256"], str) or not re.fullmatch(
        r"[a-f0-9]{64}", value["source_sha256"]
    ):
        raise ValueError("Invalid source digest")
    return dict(value)


def resolve_grounding(value, question_id=None):
    from .grader import QUESTIONS

    ids = validate_grounding(value)
    root = Path(
        os.environ.get("SIIP_DEMO_STATE_DIR")
        or Path(__file__).resolve().parents[3] / "artifacts/demo_state"
    )
    registry = DemoAuthoringRegistry(root / "authoring")
    assignment = registry.get_assignment(ids["assignment_id"])
    if assignment is None or assignment.publication_status != "PUBLISHED_LOCAL_DEMO":
        raise ValueError("Grounding assignment is unavailable")
    if question_id is not None and question_id not in assignment.question_ids:
        raise ValueError("Question does not belong to grounding assignment")
    selected = set(assignment.kg_node_ids)
    question_tags = [set(QUESTIONS[qid]["concepts"]) for qid in assignment.question_ids]
    config = assignment.grading_config
    for key in ("source_document_id", "source_version", "graph_id", "graph_version"):
        binding = getattr(assignment, key, None)
        if binding is not None and binding != ids[key]:
            raise ValueError("Assignment source or graph binding mismatch")
    if (
        assignment.course_id != ids["course_id"]
        or config.get("graph_id") != ids["graph_id"]
        or config.get("graph_version") != ids["graph_version"]
    ):
        raise ValueError("Assignment graph binding mismatch")
    source = registry.get_lesson(ids["source_document_id"], ids["source_version"])
    if (
        source is None
        or source.course_id != ids["course_id"]
        or source.sha256 != ids["source_sha256"]
    ):
        raise ValueError("Grounding source mismatch")
    graph = DemoKGRepository(root / "knowledge_graph").retrieve(
        ids["graph_id"], ids["graph_version"]
    )
    if not selected.issubset({node["id"] for node in graph["nodes"]}):
        raise ValueError("Assignment concepts are missing from saved graph version")
    if (
        graph["source_document_id"] != ids["source_document_id"]
        or graph.get("source_version") != ids["source_version"]
        or graph.get("course_id") != ids["course_id"]
    ):
        raise ValueError("Graph source mismatch")
    approved = [edge for edge in graph["edges"] if edge["review_state"] == "APPROVED"]
    if not approved:
        raise ValueError("Grounding requires reviewed graph evidence")
    mapping = reviewed_concept_mapping(config, graph)
    resolved_selected = {mapping.get(node, node) for node in selected}
    if not selected or not all(resolved_selected & tags for tags in question_tags):
        raise ValueError("Assignment KG nodes do not match the question concept tags")
    # Project graph IDs for this assignment only. Saved versions remain untouched.
    approved = [
        {
            **edge,
            "source": mapping.get(edge["source"], edge["source"]),
            "target": mapping.get(edge["target"], edge["target"]),
        }
        for edge in approved
    ]
    graph = {
        **graph,
        "assignment_concept_mapping": config.get("concept_mapping", {}),
        "assignment_kg_node_ids": list(assignment.kg_node_ids),
    }
    text = registry.read_lesson_text(ids["source_document_id"], ids["source_version"])
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if source.media_type == "application/pdf":
        if (
            source.extracted_source_sha256 != ids["source_sha256"]
            or source.extracted_text_sha256 != text_hash
            or graph.get("registered_content_hash") != ids["source_sha256"]
            or graph.get("source_content_sha256") != text_hash
            or graph.get("extracted_chunks") != list(source.extracted_chunks)
            or "\n\n".join(
                c.get("text", "")
                for c in source.extracted_chunks
                if isinstance(c, dict) and c.get("text")
            )
            != text
        ):
            raise ValueError("Grounding source bytes do not match persisted provenance")
        chunks = []
        for chunk in source.extracted_chunks:
            if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
                raise ValueError("Invalid persisted original chunk")
            chunk_id = chunk.get("chunk_id")
            pages = chunk.get("page_numbers") or []
            if not isinstance(chunk_id, str) or not isinstance(pages, list):
                raise ValueError("Invalid persisted original chunk metadata")
            chunks.append(
                {
                    "id": chunk_id,
                    "page": pages[0] if pages else None,
                    "page_numbers": pages,
                    "text": chunk["text"][:2200],
                }
            )
    else:
        if text_hash != ids["source_sha256"] or hashlib.sha256(
            text.strip().encode("utf-8")
        ).hexdigest() != graph.get("source_content_sha256"):
            raise ValueError("Grounding source bytes do not match persisted provenance")
        chunks = [
            {
                "id": f"{ids['source_document_id']}:v{ids['source_version']}:chunk:{i}",
                "page": i,
                "text": part[:2200],
            }
            for i, part in enumerate(text.split("\n\n"), 1)
            if part.strip()
        ]
    words = {item.replace("_", " ").lower() for item in assignment.kg_node_ids}
    chunks.sort(key=lambda part: -sum(word in part["text"].lower() for word in words))
    return ids, graph, approved, chunks[:6]
