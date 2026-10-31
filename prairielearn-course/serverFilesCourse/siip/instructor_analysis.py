"""Deterministic, evidence-linked instructor view of an individual attempt."""

from collections import Counter


def analyze_attempt(attempt, prior_records, graph, mapping):
    """Summarize strictly prior same-student/course records and reviewed graph edges."""
    prior = [
        row
        for row in prior_records
        if row.get("student_id") == attempt["student_id"]
        and row.get("course_id") == attempt.get("course_id")
        and row.get("timestamp", "") < attempt["timestamp"]
    ]
    prior.sort(key=lambda row: (row["timestamp"], row["attempt_id"]))
    concepts = sorted(set(attempt.get("concepts", [])))
    concept_history = []
    for concept in concepts:
        relevant = [row for row in prior if concept in row.get("concepts", [])]
        concept_history.append(
            {
                "concept": concept,
                "prior_attempt_count": len(relevant),
                "prior_incorrect_count": sum(
                    row.get("grading", {}).get("score") == 0 for row in relevant
                ),
                "attempt_ids": [row["attempt_id"] for row in relevant],
            }
        )
    errors = Counter(
        row.get("diagnosis", {}).get("observed_error")
        for row in prior
        if row.get("grading", {}).get("score") == 0
        and row.get("diagnosis", {}).get("observed_error")
    )
    repeated = [
        {
            "observed_error": error,
            "prior_count": count,
            "attempt_ids": [
                row["attempt_id"]
                for row in prior
                if row.get("grading", {}).get("score") == 0
                and row.get("diagnosis", {}).get("observed_error") == error
            ],
        }
        for error, count in sorted(errors.items())
        if count >= 2
    ]
    prerequisites = []
    for edge in graph.get("edges", []):
        source = mapping.get(edge.get("source"), edge.get("source"))
        target = mapping.get(edge.get("target"), edge.get("target"))
        if (
            edge.get("review_state") == "APPROVED"
            and edge.get("relation") == "depends_on"
            and source in concepts
        ):
            prerequisites.append(
                {
                    "concept": source,
                    "prerequisite": target,
                    "edge_id": edge.get("edge_id"),
                    "evidence_excerpt": edge.get("evidence_excerpt", ""),
                }
            )
    return {
        "method": "deterministic_prior_attempt_summary",
        "current_concepts": concepts,
        "current_observed_error": attempt.get("diagnosis", {}).get("observed_error"),
        "prior_history": {
            "student_id": attempt["student_id"],
            "course_id": attempt.get("course_id"),
            "strictly_before": attempt["timestamp"],
            "attempt_count": len(prior),
        },
        "concept_history": concept_history,
        "repeated_prior_errors": repeated,
        "reviewed_prerequisites": prerequisites,
        "graph_provenance": {
            "graph_id": graph.get("graph_id"),
            "version": graph.get("version"),
            "source_document_id": graph.get("source_document_id"),
            "source_version": graph.get("source_version"),
        },
        "uncertainty": "Observed attempts and reviewed relations are evidence for instructor consideration, not proof of mastery or cause.",
    }
