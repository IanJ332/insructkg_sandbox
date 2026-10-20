"""Read-only entity lineage derived from explicit persisted demo associations.

Derived profiles/recommendations are labeled computed views. Missing references
are reported rather than replaced with invented successful lifecycle entities.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .grader import public_grade
from .recommender import recommend_next_activity


def _dict(value):
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def build_entity_lineage(
    authoring_registry,
    kg_repo,
    submission_repo,
    feedback_repo,
    em_repo,
    project_repo,
    correlation_id,
) -> dict[str, Any]:
    """Join actual IDs; never infer a relationship merely from phase ordering."""
    nodes, edges, unresolved = {}, {}, []

    def node(
        kind, entity_id, data, *, version=None, course_id=None, assignment_id=None, persisted=True
    ):
        key = f"{kind}:{entity_id}" + (f":v{version}" if version is not None else "")
        nodes[key] = {
            "id": key,
            "entity_type": kind,
            "entity_id": entity_id,
            "version": version,
            "course_id": course_id,
            "assignment_id": assignment_id,
            "persisted": persisted,
            "data": data,
        }
        return key

    def edge(source, target, relation):
        if source in nodes and target in nodes:
            key = (source, target, relation)
            edges[key] = {"source": source, "target": target, "relation": relation}
        else:
            unresolved.append({"source": source, "target": target, "relation": relation})

    for course in authoring_registry.list_courses():
        node("course", course["course_id"], course, course_id=course["course_id"])
    for module in authoring_registry.list_modules():
        key = node("module", module["module_id"], module, course_id=module["course_id"])
        edge(key, f"course:{module['course_id']}", "belongs_to_course")
    sources = [_dict(row) for row in authoring_registry.list_lessons()]
    for source in sources:
        key = node(
            "source",
            source["source_document_id"],
            source,
            version=source["version"],
            course_id=source["course_id"],
        )
        edge(key, f"course:{source['course_id']}", "belongs_to_course")
        if source.get("module_id"):
            edge(key, f"module:{source['module_id']}", "belongs_to_module")

    for item in kg_repo.list_graphs():
        gid = item["graph_id"]
        snapshots = [("draft", kg_repo.retrieve(gid))]
        snapshots += [
            (version["version"], kg_repo.retrieve(gid, version["version"]))
            for version in kg_repo.list_versions(gid)
        ]
        for version, graph in snapshots:
            matches = [
                source
                for source in sources
                if source["source_document_id"] == graph.get("source_document_id")
                and source["sha256"]
                == (
                    graph.get("registered_content_hash")
                    or graph.get("source_sha256")
                    or graph.get("source_content_sha256")
                )
                and (
                    graph.get("source_version") is None
                    or source["version"] == graph["source_version"]
                )
            ]
            course_id = matches[0]["course_id"] if len(matches) == 1 else None
            key = node("graph", gid, graph, version=version, course_id=course_id)
            if len(matches) == 1:
                source = matches[0]
                edge(
                    key,
                    f"source:{source['source_document_id']}:v{source['version']}",
                    "extracted_from",
                )
            else:
                unresolved.append(
                    {
                        "entity_id": gid,
                        "relation": "extracted_from",
                        "reason": "missing_or_ambiguous_source_version",
                    }
                )
            for concept in graph.get("nodes", []):
                concept_key = node(
                    "concept",
                    f"{gid}/{concept['id']}",
                    concept,
                    version=version,
                    course_id=course_id,
                )
                nodes[concept_key]["entity_id"] = concept["id"]
                edge(concept_key, key, "contained_in_graph")
            for relation in graph.get("edges", []):
                relation_key = node(
                    "relation",
                    f"{gid}/{relation['edge_id']}",
                    relation,
                    version=version,
                    course_id=course_id,
                )
                nodes[relation_key]["entity_id"] = relation["edge_id"]
                edge(relation_key, key, "contained_in_graph")
                for endpoint in ("source", "target"):
                    edge(
                        relation_key,
                        f"concept:{gid}/{relation[endpoint]}:v{version}",
                        f"relation_{endpoint}",
                    )

    assignments = {}
    for value in authoring_registry.list_assignments():
        assignment = _dict(value)
        aid, cid = assignment["assignment_id"], assignment["course_id"]
        assignments[aid] = assignment
        key = node("assignment", aid, assignment, course_id=cid, assignment_id=aid)
        edge(key, f"course:{cid}", "belongs_to_course")
        config = assignment.get("grading_config", {})
        gid = assignment.get("graph_id") or config.get("graph_id")
        version = assignment.get("graph_version") or config.get("graph_version")
        if gid is not None and version is not None:
            target = f"graph:{gid}:v{version}"
            if target in nodes and nodes[target]["course_id"] == cid:
                edge(key, target, "grounded_in_saved_graph")
            else:
                unresolved.append(
                    {
                        "entity_id": aid,
                        "relation": "grounded_in_saved_graph",
                        "reason": "missing_or_cross_course_graph",
                    }
                )
        if assignment.get("source_document_id") and assignment.get("source_version"):
            target = f"source:{assignment['source_document_id']}:v{assignment['source_version']}"
            if target in nodes and nodes[target]["course_id"] == cid:
                edge(key, target, "uses_source_version")
            else:
                unresolved.append(
                    {
                        "entity_id": aid,
                        "relation": "uses_source_version",
                        "reason": "missing_or_cross_course_source",
                    }
                )

    attempts = submission_repo.records()
    student_ids = set()
    for attempt in attempts:
        sid, attempt_id = attempt["student_id"], attempt["attempt_id"]
        student_ids.add(sid)
        node("student", sid, {"student_id": sid})
        aid = attempt.get("assessment_id")
        assignment = assignments.get(aid)
        cid = assignment["course_id"] if assignment else None
        key = node(
            "attempt", attempt_id, attempt, course_id=cid, assignment_id=aid if assignment else None
        )
        edge(key, f"student:{sid}", "submitted_by")
        if assignment:
            edge(key, f"assignment:{aid}", "submitted_to")
        grade = node(
            "grade",
            attempt_id,
            public_grade(attempt.get("grading", {})),
            course_id=cid,
            assignment_id=aid if assignment else None,
        )
        edge(grade, key, "deterministic_grade_of")
        if attempt.get("diagnosis"):
            diagnosis = node(
                "diagnosis",
                attempt_id,
                attempt["diagnosis"],
                course_id=cid,
                assignment_id=aid if assignment else None,
            )
            edge(diagnosis, key, "diagnosis_of")
        job_value = feedback_repo.get_by_attempt(attempt_id)
        if job_value is not None:
            job = _dict(job_value)
            if job.get("student_id") != sid:
                unresolved.append(
                    {
                        "entity_id": job.get("job_id"),
                        "relation": "feedback_for",
                        "reason": "owner_mismatch",
                    }
                )
                continue
            # Internal lease credentials are never useful lineage evidence.
            for field in ("lease_token", "claimed_by"):
                job.pop(field, None)
            job_key = node(
                "feedback_job",
                job["job_id"],
                job,
                course_id=cid,
                assignment_id=aid if assignment else None,
            )
            edge(job_key, key, "feedback_for")
            grounding = job.get("grading", {}).get("_grounding") or {}
            graph_key = f"graph:{grounding.get('graph_id')}:v{grounding.get('graph_version')}"
            if (
                graph_key in nodes
                and grounding.get("assignment_id") == aid
                and grounding.get("course_id") == cid
                and nodes[graph_key]["course_id"] == cid
            ):
                edge(job_key, graph_key, "queued_grounding_graph")

    for value in em_repo.list_all_evidence():
        evidence = _dict(value)
        sid, attempt_id = evidence["student_id"], evidence.get("attempt_id")
        student_ids.add(sid)
        node("student", sid, {"student_id": sid})
        attempt_key = f"attempt:{attempt_id}"
        parent = nodes.get(attempt_key)
        owner_matches = parent is not None and parent["data"].get("student_id") == sid
        key = node(
            "em_evidence",
            evidence["evidence_id"],
            evidence,
            course_id=parent["course_id"] if owner_matches else None,
            assignment_id=parent["assignment_id"] if owner_matches else None,
        )
        edge(key, f"student:{sid}", "observed_for_student")
        if owner_matches:
            edge(key, attempt_key, "reflection_evidence_for_attempt")
        elif attempt_id:
            unresolved.append(
                {
                    "entity_id": evidence["evidence_id"],
                    "relation": "reflection_evidence_for_attempt",
                    "reason": "missing_attempt_or_owner_mismatch",
                }
            )

    for value in project_repo.list_all_projects():
        project = _dict(value)
        sid = project["student_id"]
        student_ids.add(sid)
        node("student", sid, {"student_id": sid})
        key = node("project", project["project_id"], project)
        edge(key, f"student:{sid}", "generated_for_student")
        grounding = project.get("generation_provenance", {}).get("graph_grounding")
        if grounding:
            graph_key = f"graph:{grounding['graph_id']}:v{grounding['version']}"
            if graph_key in nodes:
                edge(key, graph_key, "scaffolded_from_reviewed_prerequisites")
    for sid in sorted(student_ids):
        profile = submission_repo.profile(sid)
        key = node("profile", sid, profile, persisted=False)
        edge(key, f"student:{sid}", "computed_profile_for")
        for history in profile.get("history", []):
            attempt_key = f"attempt:{history['attempt_id']}"
            if attempt_key in nodes and nodes[attempt_key]["data"]["student_id"] == sid:
                edge(key, attempt_key, "aggregates_attempt")
        recommendation = node(
            "recommendation", sid, recommend_next_activity(sid, profile), persisted=False
        )
        edge(recommendation, key, "computed_from_current_profile")
    return {
        "schema_version": 1,
        "correlation_id": correlation_id,
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(
            edges.values(), key=lambda row: (row["source"], row["target"], row["relation"])
        ),
        "unresolved_references": unresolved,
        "interpretation": "Persisted entities and explicit associations; computed views are marked persisted=false. Correlation ID labels this export, not historical membership.",
    }


def derive_enriched_events(events, lineage) -> list[dict[str, Any]]:
    """Enrich only unambiguous exact entity matches; retain unknown values as null."""
    lookup = defaultdict(list)
    for node in lineage["nodes"]:
        lookup[str(node["entity_id"])].append(node)
    enriched = []
    for value in events:
        event = _dict(value)
        matches = lookup.get(str(event.get("entity_id")), [])
        for field in ("course_id", "assignment_id"):
            choices = {match[field] for match in matches if match.get(field) is not None}
            event[field] = event.get(field) or (next(iter(choices)) if len(choices) == 1 else None)
        event.setdefault("duration_ms", None)
        start = event.get("started_at_utc") or event.get("started_at")
        end = event.get("completed_at_utc") or event.get("completed_at")
        if event["duration_ms"] is None and start and end:
            try:
                begin = datetime.fromisoformat(start.replace("Z", "+00:00"))
                finish = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if begin.tzinfo is not None and finish.tzinfo is not None and finish >= begin:
                    event["duration_ms"] = (finish - begin).total_seconds() * 1000
            except (ValueError, TypeError):
                pass
        enriched.append(event)
    return enriched
