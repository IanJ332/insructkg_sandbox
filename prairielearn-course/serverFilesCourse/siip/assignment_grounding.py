"""Resolve persisted local assignment lineage; never accept uploaded prompt instructions."""

import os
import re
from pathlib import Path

from .demo_authoring import DemoAuthoringRegistry
from .demo_kg import DemoKGRepository


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


def resolve_grounding(value):
    ids = validate_grounding(value)
    root = Path(
        os.environ.get("SIIP_DEMO_STATE_DIR")
        or Path(__file__).resolve().parents[3] / "artifacts/demo_state"
    )
    registry = DemoAuthoringRegistry(root / "authoring")
    assignment = registry.get_assignment(ids["assignment_id"])
    if assignment is None or assignment.publication_status != "PUBLISHED_LOCAL_DEMO":
        raise ValueError("Grounding assignment is unavailable")
    config = assignment.grading_config
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
    if graph["source_document_id"] != ids["source_document_id"]:
        raise ValueError("Graph source mismatch")
    approved = [edge for edge in graph["edges"] if edge["review_state"] == "APPROVED"]
    if not approved:
        raise ValueError("Grounding requires reviewed graph evidence")
    text = registry.read_lesson_bytes(ids["source_document_id"], ids["source_version"]).decode(
        "utf-8"
    )
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
