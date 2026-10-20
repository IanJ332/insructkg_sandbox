from __future__ import annotations

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_observability import (  # noqa: E402
    LINEAGE_PHASES,
    DemoObservabilityRepository,
)


class DemoObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="siip-observability-test-")
        self.directory = Path(self.temporary.name)
        self.repository = DemoObservabilityRepository(self.directory)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(self, phase: str, event_type: str, at: str, **changes: str):
        defaults = {
            "actor_type": "system",
            "actor_id": "siip-demo-system",
            "phase": phase,
            "event_type": event_type,
            "entity_id": f"entity-{phase}",
            "correlation_id": "workflow-001",
            "status": "completed",
            "artifact_path": f"outputs/{phase}.json",
            "source_type": "actual_execution",
            "timestamp_utc": at,
        }
        defaults.update(changes)
        return self.repository.record_event(**defaults)

    def test_exact_schema_persistence_and_chronological_order(self) -> None:
        later = self.event(
            "grade", "grading_completed", "2026-10-20T01:00:03Z", entity_id="grade-1"
        )
        earlier = self.event(
            "submission",
            "sql_submitted",
            "2026-10-20T01:00:01Z",
            actor_type="student",
            actor_id="S001",
            entity_id="attempt-1",
        )

        records = self.repository.list_events()
        self.assertEqual([item.event_id for item in records], [earlier.event_id, later.event_id])
        raw_lines = [
            json.loads(line)
            for line in (self.directory / "system_event_log.jsonl").read_text("utf-8").splitlines()
        ]
        self.assertEqual(raw_lines[0]["event_id"], later.event_id)  # JSONL remains append-only.
        self.assertEqual(
            set(raw_lines[0]),
            {
                "event_id",
                "timestamp_utc",
                "actor_type",
                "actor_id",
                "phase",
                "event_type",
                "entity_id",
                "correlation_id",
                "status",
                "artifact_path",
                "source_type",
            },
        )
        reopened = DemoObservabilityRepository(self.directory)
        self.assertEqual(reopened.list_events(), records)

    def test_source_type_and_real_duration_are_retained(self) -> None:
        self.event(
            "feedback",
            "feedback_generation_started",
            "2026-10-20T01:00:00.250000Z",
            status="started",
            entity_id="feedback-1",
            source_type="synthetic_fixture",
        )
        completed = self.event(
            "feedback",
            "feedback_generation_completed",
            "2026-10-20T01:00:02.750000Z",
            entity_id="feedback-1",
            source_type="synthetic_fixture",
        )
        pairs = self.repository.operation_durations()
        self.assertEqual(pairs[0]["terminal_event_id"], completed.event_id)
        self.assertEqual(pairs[0]["duration_seconds"], 2.5)
        manifest = self.repository.build_lineage()
        node = next(node for node in manifest["nodes"] if node["event_id"] == completed.event_id)
        self.assertEqual(node["source_type"], "synthetic_fixture")
        self.assertEqual(node["operation_duration_seconds"], 2.5)

    def test_complete_referential_lineage_html_and_mermaid(self) -> None:
        phase_events = {
            "source": "instructor_uploaded_lesson",
            "knowledge_graph": "kg_extraction_completed",
            "graph_review": "kg_reviewed",
            "assignment": "assignment_published",
            "submission": "sql_submitted",
            "grade": "grading_completed",
            "diagnosis": "concept_diagnosis_completed",
            "history": "profile_updated",
            "feedback": "feedback_generation_completed",
            "em": "em_reflection_submitted",
            "analytics": "instructor_analytics_viewed",
            "project": "personalized_project_generated",
        }
        for index, (phase, event_type) in enumerate(phase_events.items()):
            self.event(
                phase,
                event_type,
                f"2026-10-20T01:00:{index:02d}Z",
                source_type="synthetic_fixture" if phase == "knowledge_graph" else "actual_execution",
            )

        paths = self.repository.render_all()
        manifest = json.loads(paths["lineage"].read_text("utf-8"))
        node_ids = {node["node_id"] for node in manifest["nodes"]}
        self.assertEqual(manifest["stage_order"], list(LINEAGE_PHASES))
        self.assertTrue(manifest["workflows"][0]["complete"])
        self.assertTrue(
            all(
                edge["from_node_id"] in node_ids and edge["to_node_id"] in node_ids
                for edge in manifest["edges"]
            )
        )
        mermaid = paths["mermaid"].read_text("utf-8")
        timeline = paths["timeline"].read_text("utf-8")
        self.assertIn("flowchart LR", mermaid)
        self.assertIn("synthetic_fixture", mermaid)
        self.assertIn("SIIP System Event Timeline", timeline)
        self.assertIn("instructor_uploaded_lesson", timeline)
        self.assertNotIn("https://", timeline)

    def test_invalid_enums_paths_schema_and_duplicate_ids_are_rejected(self) -> None:
        base = {
            "actor_type": "system",
            "actor_id": "worker-1",
            "phase": "grade",
            "event_type": "grading_completed",
            "entity_id": "grade-1",
            "correlation_id": "workflow-1",
            "status": "completed",
            "artifact_path": "outputs/grade.json",
            "source_type": "actual_execution",
            "timestamp_utc": "2026-10-20T01:00:00Z",
        }
        for field, bad in (
            ("actor_type", "grader"),
            ("phase", "unknown"),
            ("event_type", "made_up_success"),
            ("status", "success"),
            ("source_type", "pretend"),
            ("artifact_path", "../escape.json"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.repository.record_event(**{**base, field: bad})
        with self.assertRaisesRegex(ValueError, "belongs to phase"):
            self.repository.record_event(**{**base, "phase": "source"})
        event_id = str(uuid.uuid4())
        self.repository.record_event(**base, event_id=event_id)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.repository.record_event(**base, event_id=event_id)
        self.assertEqual(len(self.repository.list_events()), 1)

    def test_no_success_is_inferred_and_actual_records_are_exported_verbatim(self) -> None:
        self.event(
            "knowledge_graph",
            "kg_extraction_requested",
            "2026-10-20T01:00:00Z",
            status="started",
            entity_id="graph-1",
        )
        self.repository.render_all()
        self.assertEqual(len(self.repository.list_events()), 1)
        manifest = json.loads(self.repository.lineage_path.read_text("utf-8"))
        self.assertEqual(len(manifest["nodes"]), 1)

        records = [{"concept_id": "LEFT_OUTER_JOIN", "incorrect_count": 1}]
        exported = self.repository.export_actual_records(
            "08_concept_gap_analytics.json", records, source_type="actual_execution"
        )
        payload = json.loads(exported.read_text("utf-8"))
        self.assertEqual(payload["records"], records)
        self.assertEqual(payload["record_count"], 1)
        cohort = self.repository.export_cohort_summary(records, source_type="synthetic_fixture")
        self.assertEqual(cohort.name, "08_cohort_summary.json")
        concept = self.repository.export_concept_gap_analytics(
            records, source_type="actual_execution"
        )
        self.assertEqual(concept.name, "08_concept_gap_analytics.json")


if __name__ == "__main__":
    unittest.main()
