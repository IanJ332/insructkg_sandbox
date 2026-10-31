import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.assignment_grounding import resolve_grounding, reviewed_concept_mapping
from siip.demo_authoring import DemoAuthoringRegistry
from siip.demo_kg import DemoKGRepository
from siip.feedback import build_context, generate_feedback
from siip.grader import grade
from siip.jobs import AttemptConflictError, FeedbackJobRepository, FeedbackWorker
from siip.store import SubmissionRepository


class AssignmentGroundingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.environment = patch.dict(
            os.environ, {"SIIP_DEMO_STATE_DIR": str(self.root), "SIIP_DEMO_KG_MODE": "synthetic"}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        registry = DemoAuthoringRegistry(self.root / "authoring")
        lesson = registry.upload_lesson(
            (ROOT / "demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md").read_bytes(),
            source_document_id="fresh-lesson",
            course_id="intro-relational-databases",
            original_filename="fresh.md",
        )
        registry.set_lesson_processing_status(
            lesson.source_document_id, lesson.version, "PROCESSING"
        )
        registry.set_lesson_processing_status(
            lesson.source_document_id, lesson.version, "PROCESSED"
        )
        kg = DemoKGRepository(self.root / "knowledge_graph")
        graph = kg.generate_candidates(
            {
                **lesson.to_dict(),
                "content": registry.read_lesson_bytes(
                    lesson.source_document_id, lesson.version
                ).decode(),
            }
        )
        self.edge_id = graph["edges"][0]["edge_id"]
        kg.review_edge(graph["graph_id"], self.edge_id, "APPROVE", "instructor-admin")
        saved = kg.save_version(graph["graph_id"])
        registry.create_assignment(
            assignment_id="bound-assignment",
            course_id=lesson.course_id,
            question_ids=["sql_join_04"],
            kg_node_ids=["LEFT_OUTER_JOIN"],
            grading_config={
                "engine": "siip_deterministic_sql_grader",
                "question_id": "sql_join_04",
                "graph_id": graph["graph_id"],
                "graph_version": saved["version"],
            },
        )
        registry.publish_assignment("bound-assignment")
        self.ids = {
            "assignment_id": "bound-assignment",
            "course_id": lesson.course_id,
            "graph_id": graph["graph_id"],
            "graph_version": saved["version"],
            "source_document_id": lesson.source_document_id,
            "source_version": lesson.version,
            "source_sha256": lesson.sha256,
        }

    def test_worker_uses_immutable_uploaded_graph_and_source(self):
        queue = FeedbackJobRepository(self.root / "jobs.sqlite3")
        sql = "SELECT department_name FROM Departments"
        result = grade("sql_join_04", sql)
        queued = queue.enqueue(
            "attempt-bound", "S001", "sql_join_04", sql, result, grounding=self.ids
        )
        DemoKGRepository(self.root / "knowledge_graph").review_edge(
            self.ids["graph_id"], self.edge_id, "REJECT", "instructor-admin"
        )
        completed = FeedbackWorker(queue).process_one()
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.grading["score"], queued.grading["score"])
        self.assertEqual(
            completed.result["grounding_provenance"]["source_sha256"], self.ids["source_sha256"]
        )
        self.assertTrue(
            completed.result["evidence_references"][0].startswith("fresh-lesson:v1:chunk:")
        )
        self.assertEqual(completed.result["context_status"], "available")
        self.assertNotIn("reference_sql", str(completed.to_learner_dict()))

    def test_digest_and_identifier_mismatch_fail_closed(self):
        with self.assertRaises(ValueError):
            resolve_grounding({**self.ids, "source_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            resolve_grounding({**self.ids, "source_document_id": "../secret"})

    def test_grounding_rejects_question_outside_assignment(self):
        with self.assertRaisesRegex(ValueError, "Question does not belong"):
            resolve_grounding(self.ids, question_id="sql_join_01")

    def test_reviewed_mapping_keeps_actual_prerequisite_history_without_rewriting_graph(self):
        kg = DemoKGRepository(self.root / "knowledge_graph")
        edge = next(
            e
            for e in kg.retrieve(self.ids["graph_id"])["edges"]
            if e["source"] == "LEFT_OUTER_JOIN" and e["target"] == "JOIN_PREDICATE"
        )
        kg.review_edge(self.ids["graph_id"], edge["edge_id"], "APPROVE", "instructor_alawini")
        snapshot = kg.save_version(self.ids["graph_id"])
        mapping = {
            "JOIN_PREDICATE": {
                "canonical_id": "JOIN_CONDITION",
                "reviewed_by": "instructor_alawini",
                "notes": "The ON predicate is this join condition.",
            }
        }
        registry = DemoAuthoringRegistry(self.root / "authoring")
        registry.create_assignment(
            assignment_id="mapped",
            course_id=self.ids["course_id"],
            question_ids=["sql_join_02"],
            kg_node_ids=["LEFT_OUTER_JOIN"],
            grading_config={
                "graph_id": self.ids["graph_id"],
                "graph_version": snapshot["version"],
                "concept_mapping": mapping,
            },
        )
        registry.publish_assignment("mapped")
        ids = {**self.ids, "assignment_id": "mapped", "graph_version": snapshot["version"]}
        submissions = SubmissionRepository(self.root / "history.sqlite3")
        submissions.process(
            {
                "attempt_id": "foundation",
                "student_id": "S001",
                "question_id": "sql_join_01",
                "submitted_sql": "SELECT 1",
                "timestamp": "2026-01-01T00:00:00Z",
                "course_id": self.ids["course_id"],
            }
        )
        mastery = submissions.profile("S001", course_id=self.ids["course_id"])["concepts"]
        result = grade("sql_join_02", "SELECT 1")
        context = build_context("sql_join_02", "SELECT 1", result, "kg", mastery, ids)
        self.assertEqual(context["prerequisites"], ["JOIN_CONDITION"])
        self.assertEqual(set(context["student_mastery"]), {"JOIN_CONDITION"})
        self.assertEqual(context["grounding_provenance"]["reviewed_concept_mapping"], mapping)
        feedback = generate_feedback(
            "sql_join_02", "SELECT 1", result, "kg", mastery, grounding=ids
        )
        self.assertEqual(feedback["historical_personalization"]["concept_count"], 1)
        self.assertIn("JOIN_PREDICATE", {e["target"] for e in snapshot["edges"]})
        self.assertEqual(kg.retrieve(self.ids["graph_id"], snapshot["version"]), snapshot)

    def test_concept_mapping_requires_review_and_cannot_merge_nodes(self):
        graph = DemoKGRepository(self.root / "knowledge_graph").retrieve(self.ids["graph_id"])
        entry = {"canonical_id": "JOIN_CONDITION", "reviewed_by": "S001", "notes": "claim"}
        with self.assertRaises(ValueError):
            reviewed_concept_mapping({"concept_mapping": {"JOIN_PREDICATE": entry}}, graph)
        with self.assertRaises(ValueError):
            reviewed_concept_mapping(
                {"concept_mapping": {"missing": {**entry, "reviewed_by": "instructor_alawini"}}},
                graph,
            )
        with self.assertRaises(ValueError):
            reviewed_concept_mapping(
                {
                    "concept_mapping": {
                        "JOIN_PREDICATE": {
                            **entry,
                            "reviewed_by": "instructor_alawini",
                            "canonical_id": "LEFT_OUTER_JOIN",
                        }
                    }
                },
                graph,
            )

    def test_grounding_rejects_incompatible_concept_mapping(self):
        registry = DemoAuthoringRegistry(self.root / "authoring")
        registry.create_assignment(
            assignment_id="wrong-tags",
            course_id=self.ids["course_id"],
            question_ids=["sql_join_04"],
            kg_node_ids=["INNER_JOIN"],
            grading_config={"graph_id": self.ids["graph_id"], "graph_version": 1},
        )
        registry.publish_assignment("wrong-tags")
        with self.assertRaisesRegex(ValueError, "concept tags"):
            resolve_grounding({**self.ids, "assignment_id": "wrong-tags"})

    def test_replay_cannot_replace_grounding(self):
        queue = FeedbackJobRepository(self.root / "jobs.sqlite3")
        result = {"status": "semantic_error", "score": 0, "observation": "wrong_rows"}
        queue.enqueue(
            "attempt-bound", "S001", "sql_join_04", "SELECT 1", result, grounding=self.ids
        )
        with self.assertRaises(AttemptConflictError):
            queue.enqueue(
                "attempt-bound",
                "S001",
                "sql_join_04",
                "SELECT 1",
                result,
                grounding={**self.ids, "source_sha256": "0" * 64},
            )

    def test_same_lesson_new_version_cannot_use_old_graph(self):
        registry = DemoAuthoringRegistry(self.root / "authoring")
        lesson = registry.upload_lesson(
            (ROOT / "demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md").read_bytes()
            + b"\nRevised LEFT OUTER JOIN material and NULL semantics.",
            source_document_id=self.ids["source_document_id"],
            course_id=self.ids["course_id"],
            original_filename="revised.md",
        )
        with self.assertRaisesRegex(ValueError, "Graph source mismatch"):
            resolve_grounding(
                {**self.ids, "source_version": lesson.version, "source_sha256": lesson.sha256}
            )

    def test_nonidentity_selected_mapping_and_student_submission_persist_lineage(self):
        from siip.demo_student import DemoStudentJourney

        kg = DemoKGRepository(self.root / "knowledge_graph")
        draft = kg.retrieve(self.ids["graph_id"])
        for node in draft["nodes"]:
            if node["id"] == "LEFT_OUTER_JOIN":
                node["id"] = "RESEARCH_LEFT_JOIN"
        for edge in draft["edges"]:
            for key in ("source", "target"):
                if edge[key] == "LEFT_OUTER_JOIN":
                    edge[key] = "RESEARCH_LEFT_JOIN"
                    edge["review_state"] = "APPROVED"
        import json

        (kg._graph_directory(draft["graph_id"]) / "draft.json").write_text(json.dumps(draft))
        saved = kg.save_version(draft["graph_id"])
        registry = DemoAuthoringRegistry(self.root / "authoring")
        mapping = {
            "RESEARCH_LEFT_JOIN": {
                "canonical_id": "LEFT_OUTER_JOIN",
                "reviewed_by": "instructor_alawini",
                "notes": "Reviewed match.",
            }
        }
        config = {
            "graph_id": draft["graph_id"],
            "graph_version": saved["version"],
            "concept_mapping": mapping,
        }
        registry.create_assignment(
            assignment_id="nonidentity",
            course_id=self.ids["course_id"],
            question_ids=["sql_join_04"],
            kg_node_ids=["RESEARCH_LEFT_JOIN"],
            grading_config=config,
        )
        assignment = registry.publish_assignment("nonidentity")
        ids = {**self.ids, "assignment_id": "nonidentity", "graph_version": saved["version"]}
        _, graph, approved, _ = resolve_grounding(ids, question_id="sql_join_04")
        self.assertIn("RESEARCH_LEFT_JOIN", {n["id"] for n in graph["nodes"]})
        self.assertTrue(any("LEFT_OUTER_JOIN" in (e["source"], e["target"]) for e in approved))
        adapter = {
            "assignment_id": "nonidentity",
            "course_id": ids["course_id"],
            "question_id": "sql_join_04",
            "relevant_kg_node_ids": ["RESEARCH_LEFT_JOIN"],
            "publication_timestamp": assignment.publication_timestamp_utc,
            "grading_configuration": config,
            "publication_status": assignment.publication_status,
            "native_prairielearn_publication": False,
            "feedback_grounding": ids,
        }
        journey = DemoStudentJourney(self.root / "journey")
        result = journey.submit(adapter, "S001", "SELECT 1", timestamp="2026-01-01T00:00:00Z")
        restart = SubmissionRepository(self.root / "journey" / "submissions.sqlite3")
        self.assertEqual(
            restart.attempt_for_student(result["attempt_id"], "S001")["feedback_grounding"], ids
        )
        self.assertEqual(
            restart.profile(
                "S001", before=True, as_of="2026-01-01T00:00:00Z", course_id=ids["course_id"]
            )["attempt_count"],
            0,
        )
        with self.assertRaises(ValueError):
            journey.submit(
                {**adapter, "feedback_grounding": {**ids, "source_sha256": "0" * 64}},
                "S001",
                "SELECT 1",
            )
        with self.assertRaises(ValueError):
            journey.submit(
                {**adapter, "relevant_kg_node_ids": ["LEFT_OUTER_JOIN"]}, "S001", "SELECT 1"
            )

    def test_nonidentity_without_review_and_wrong_course_fail(self):
        registry = DemoAuthoringRegistry(self.root / "authoring")
        registry.create_assignment(
            assignment_id="unmapped",
            course_id=self.ids["course_id"],
            question_ids=["sql_join_04"],
            kg_node_ids=["INNER_JOIN"],
            grading_config={"graph_id": self.ids["graph_id"], "graph_version": 1},
        )
        registry.publish_assignment("unmapped")
        with self.assertRaisesRegex(ValueError, "concept tags"):
            resolve_grounding({**self.ids, "assignment_id": "unmapped"})
        with self.assertRaises(ValueError):
            resolve_grounding({**self.ids, "course_id": "wrong-course"})

    def test_attempt_grounding_validation_and_replay_conflict(self):
        store = SubmissionRepository(self.root / "durable.sqlite3")
        record = {
            "attempt_id": "with-grounding",
            "student_id": "S001",
            "question_id": "sql_join_04",
            "submitted_sql": "SELECT 1",
            "timestamp": "2026-01-01T00:00:00Z",
            "assessment_id": self.ids["assignment_id"],
            "course_id": self.ids["course_id"],
            "feedback_grounding": self.ids,
        }
        store.process(record, mode="baseline")
        with self.assertRaisesRegex(ValueError, "collision"):
            store.process(
                {**record, "feedback_grounding": {**self.ids, "graph_version": 2}}, mode="baseline"
            )
        with self.assertRaises(ValueError):
            store.process(
                {
                    **record,
                    "attempt_id": "bad",
                    "feedback_grounding": {**self.ids, "course_id": "other"},
                },
                mode="baseline",
            )

    def test_pdf_grounding_uses_original_chunks_and_both_hashes(self):
        import hashlib
        import io

        from pypdf import PdfWriter
        from siip import original_instructkg

        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)
        raw = output.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        registry = DemoAuthoringRegistry(
            self.root / "authoring",
            trusted_pdf_manifest={digest: {"provenance": "synthetic fixture", "license": "CC0"}},
        )
        lesson = registry.upload_lesson(
            raw,
            source_document_id="pdf-source",
            course_id=self.ids["course_id"],
            original_filename="lesson.pdf",
        )
        text = "A left outer join preserves unmatched rows."
        chunks = [
            {
                "chunk_id": "lecture__0000",
                "page_numbers": [1],
                "text": text,
                "prev_chunk_id": None,
                "next_chunk_id": None,
            }
        ]
        registry.set_extracted_view("pdf-source", 1, source_sha256=digest, text=text, chunks=chunks)
        result = {
            "nodes": [
                {"id": "LEFT_OUTER_JOIN", "label": "Left join"},
                {"id": "JOIN_PREDICATE", "label": "Predicate"},
            ],
            "edges": [
                {
                    "source": "LEFT_OUTER_JOIN",
                    "target": "JOIN_PREDICATE",
                    "relation": "depends_on",
                    "evidence_excerpt": text,
                }
            ],
            "extracted_text": text,
            "extracted_chunks": chunks,
            "extraction_metadata": {},
            "rejected_candidates": [],
        }
        kg = DemoKGRepository(self.root / "knowledge_graph")
        with patch.object(original_instructkg, "generate", return_value=result):
            graph = kg.generate_candidates(
                {
                    **lesson.to_dict(),
                    "content_hash": digest,
                    "source_path": "unused",
                    "requested_extraction_mode": original_instructkg.MODE,
                }
            )
        kg.review_edge(
            graph["graph_id"], graph["edges"][0]["edge_id"], "APPROVE", "instructor-admin"
        )
        saved = kg.save_version(graph["graph_id"])
        registry.create_assignment(
            assignment_id="pdf-assignment",
            course_id=self.ids["course_id"],
            question_ids=["sql_join_04"],
            kg_node_ids=["LEFT_OUTER_JOIN"],
            grading_config={"graph_id": graph["graph_id"], "graph_version": saved["version"]},
        )
        registry.publish_assignment("pdf-assignment")
        ids = {
            "assignment_id": "pdf-assignment",
            "course_id": self.ids["course_id"],
            "graph_id": graph["graph_id"],
            "graph_version": saved["version"],
            "source_document_id": "pdf-source",
            "source_version": 1,
            "source_sha256": digest,
        }
        _, _, _, evidence = resolve_grounding(ids, question_id="sql_join_04")
        self.assertEqual(evidence[0]["id"], "lecture__0000")
        self.assertEqual(evidence[0]["page_numbers"], [1])
        self.assertNotEqual(graph["source_content_sha256"], digest)
        with self.assertRaises(ValueError):
            resolve_grounding({**ids, "source_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
