from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_lineage import build_entity_lineage, derive_enriched_events


class DemoEntityLineageTests(unittest.TestCase):
    def build(self, *, wrong_course=False, duplicate_source=False, wrong_em_owner=False):
        source = {
            "source_document_id": "lesson",
            "version": 1,
            "sha256": "abc",
            "course_id": "course-a",
            "module_id": "joins",
        }
        sources = [source, {**source, "version": 2}] if duplicate_source else [source]
        assignment = {
            "assignment_id": "assignment",
            "course_id": "course-b" if wrong_course else "course-a",
            "source_document_id": "lesson",
            "source_version": 1,
            "graph_id": "kg-one",
            "graph_version": 1,
            "publication_status": "PUBLISHED_LOCAL_DEMO",
        }
        authoring = SimpleNamespace(
            list_courses=lambda: [{"course_id": "course-a"}, {"course_id": "course-b"}],
            list_modules=lambda: [{"module_id": "joins", "course_id": "course-a"}],
            list_lessons=lambda: sources,
            list_assignments=lambda: [assignment],
        )
        graph = {
            "graph_id": "kg-one",
            "source_document_id": "lesson",
            "registered_content_hash": "abc",
            "nodes": [{"id": "LEFT_OUTER_JOIN"}, {"id": "NULL_SEMANTICS"}],
            "edges": [
                {
                    "edge_id": "approved",
                    "source": "NULL_SEMANTICS",
                    "target": "LEFT_OUTER_JOIN",
                    "review_state": "APPROVED",
                },
                {
                    "edge_id": "rejected",
                    "source": "LEFT_OUTER_JOIN",
                    "target": "NULL_SEMANTICS",
                    "review_state": "REJECTED",
                },
            ],
        }
        kg = SimpleNamespace(
            list_graphs=lambda: [{"graph_id": "kg-one"}],
            list_versions=lambda gid: [{"version": 1}],
            retrieve=lambda gid, version=None: {**graph, "version": version or 0},
        )
        attempt = {
            "attempt_id": "attempt",
            "student_id": "S001",
            "assessment_id": "assignment",
            "grading": {
                "status": "semantic_error",
                "score": 0,
                "observation": "result_mismatch",
                "datasets": [{"hidden": "secret"}],
            },
            "diagnosis": {"candidate_concepts": ["LEFT_OUTER_JOIN"]},
        }
        submissions = SimpleNamespace(
            records=lambda: [attempt],
            profile=lambda sid: {
                "history": [{"attempt_id": "attempt"}] if sid == "S001" else [],
                "concepts": {},
            },
        )
        jobs = SimpleNamespace(
            get_by_attempt=lambda aid: {
                "job_id": "job",
                "student_id": "S001",
                "status": "pending",
                "result": None,
                "lease_token": "hidden",
                "grading": {
                    "_grounding": {
                        "assignment_id": "assignment",
                        "course_id": assignment["course_id"],
                        "graph_id": "kg-one",
                        "graph_version": 1,
                    }
                },
            }
        )
        em = SimpleNamespace(
            list_all_evidence=lambda: [
                {
                    "evidence_id": "em",
                    "student_id": "S002" if wrong_em_owner else "S001",
                    "attempt_id": "attempt",
                    "review_status": "PROPOSED",
                }
            ]
        )
        projects = SimpleNamespace(
            list_all_projects=lambda: [
                {
                    "project_id": "project",
                    "student_id": "S001",
                    "instructor_approval_status": "PROVISIONAL",
                }
            ]
        )
        return build_entity_lineage(authoring, kg, submissions, jobs, em, projects, "export-1")

    def test_real_ids_and_explicit_links_preserve_pending_and_review_states(self):
        result = self.build()
        nodes = {node["id"]: node for node in result["nodes"]}
        self.assertEqual(nodes["feedback_job:job"]["data"]["status"], "pending")
        self.assertIsNone(nodes["feedback_job:job"]["data"]["result"])
        self.assertNotIn("lease_token", nodes["feedback_job:job"]["data"])
        self.assertEqual(
            nodes["project:project"]["data"]["instructor_approval_status"], "PROVISIONAL"
        )
        self.assertEqual(nodes["relation:kg-one/rejected:v1"]["data"]["review_state"], "REJECTED")
        self.assertNotIn("datasets", nodes["grade:attempt"]["data"])
        self.assertFalse(nodes["recommendation:S001"]["persisted"])
        self.assertTrue(any(edge["relation"] == "submitted_to" for edge in result["edges"]))
        self.assertTrue(
            all(edge["source"] in nodes and edge["target"] in nodes for edge in result["edges"])
        )
        self.assertFalse(
            any(
                edge["source"] == "project:project" and edge["target"].startswith("assignment:")
                for edge in result["edges"]
            )
        )

    def test_cross_course_or_ambiguous_sources_do_not_create_false_lineage(self):
        result = self.build(wrong_course=True)
        self.assertFalse(
            any(
                edge["source"] == "assignment:assignment"
                and edge["relation"] in {"grounded_in_saved_graph", "uses_source_version"}
                for edge in result["edges"]
            )
        )
        self.assertTrue(result["unresolved_references"])
        result = self.build(duplicate_source=True)
        self.assertFalse(any(edge["relation"] == "extracted_from" for edge in result["edges"]))

    def test_em_attempt_ownership_must_match(self):
        result = self.build(wrong_em_owner=True)
        self.assertFalse(
            any(
                edge["source"] == "em_evidence:em"
                and edge["relation"] == "reflection_evidence_for_attempt"
                for edge in result["edges"]
            )
        )

    def test_enrichment_keeps_unknowns_and_uses_actual_timestamps(self):
        result = self.build()
        events = derive_enriched_events(
            [
                {
                    "entity_id": "attempt",
                    "started_at": "2026-10-19T12:00:00Z",
                    "completed_at": "2026-10-19T12:00:01.250Z",
                },
                {"entity_id": "missing"},
                {"entity_id": "project", "status": "pending"},
            ],
            result,
        )
        self.assertEqual(events[0]["assignment_id"], "assignment")
        self.assertEqual(events[0]["course_id"], "course-a")
        self.assertEqual(events[0]["duration_ms"], 1250)
        self.assertIsNone(events[1]["assignment_id"])
        self.assertIsNone(events[1]["duration_ms"])
        self.assertEqual(events[2]["status"], "pending")
        self.assertIsNone(events[2]["course_id"])


if __name__ == "__main__":
    unittest.main()
