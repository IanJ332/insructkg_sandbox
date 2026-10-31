"""Focused tests for the isolated synthetic instructor-authoring registry."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_authoring import (  # noqa: E402
    LOCAL_PUBLICATION_LABEL,
    SYNTHETIC_PROVENANCE_LABEL,
    DemoAuthoringRegistry,
)


class TrustedPdfBoundaryTests(unittest.TestCase):
    def test_pdf_manifest_integrity_and_extracted_view_survive_restart(self):
        import io

        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)
        raw = output.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            manifest = {digest: {"provenance": "synthetic educational fixture", "license": "CC0"}}
            registry = DemoAuthoringRegistry(directory, trusted_pdf_manifest=manifest)
            record = registry.upload_lesson(
                raw, source_document_id="pdf", course_id="course", original_filename="lesson.pdf"
            )
            self.assertEqual(registry.read_lesson_bytes("pdf", 1), raw)
            self.assertEqual(record.sha256, digest)
            with self.assertRaises(ValueError):
                registry.set_extracted_view(
                    "pdf", 1, source_sha256="0" * 64, text="text", chunks=[]
                )
            view = registry.set_extracted_view(
                "pdf", 1, source_sha256=digest, text="extracted text", chunks=[{"id": "chunk-1"}]
            )
            self.assertEqual(len(Path(view.extracted_text_path).name), 68)
            self.assertEqual(view.extracted_source_sha256, digest)
            self.assertEqual(
                view.extracted_text_sha256, hashlib.sha256(b"extracted text").hexdigest()
            )
            restarted = DemoAuthoringRegistry(directory, trusted_pdf_manifest=manifest)
            self.assertEqual(restarted.read_lesson_text("pdf", 1), "extracted text")
            self.assertEqual(restarted.get_lesson("pdf", 1).extracted_chunks[0]["id"], "chunk-1")
            with self.assertRaises(ValueError):
                registry.upload_lesson(
                    raw, source_document_id="pdf", course_id="other", original_filename="lesson.pdf"
                )
            with self.assertRaises(ValueError):
                DemoAuthoringRegistry(directory).upload_lesson(
                    raw,
                    source_document_id="other",
                    course_id="course",
                    original_filename="lesson.pdf",
                )
            with self.assertRaises(ValueError):
                DemoAuthoringRegistry(
                    directory, max_lesson_bytes=2, trusted_pdf_manifest=manifest
                ).upload_lesson(
                    raw, source_document_id="x", course_id="course", original_filename="lesson.pdf"
                )
            bad = b"%PDF-invalid"
            with self.assertRaises(ValueError):
                DemoAuthoringRegistry(
                    directory,
                    trusted_pdf_manifest={
                        hashlib.sha256(bad).hexdigest(): {
                            "provenance": "synthetic",
                            "license": "CC0",
                        }
                    },
                ).upload_lesson(
                    bad, source_document_id="bad", course_id="course", original_filename="bad.pdf"
                )


class DemoAuthoringRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.storage = Path(self.temp_dir.name) / "isolated-authoring"
        self.registry = DemoAuthoringRegistry(self.storage)
        self.lesson = (
            f"# Joins\n\n{SYNTHETIC_PROVENANCE_LABEL}\n\n"
            "INNER JOIN matches rows. LEFT OUTER JOIN preserves missing rows as NULL.\n"
        ).encode("utf-8")

    def test_upload_bytes_versions_retrieves_and_persists_metadata(self) -> None:
        first = self.registry.upload_lesson(
            self.lesson,
            source_document_id="lesson-joins",
            original_filename="joins.md",
            course_id="sql-demo",
        )
        second = self.registry.upload_lesson(
            self.lesson + b"Version two.\n",
            source_document_id="lesson-joins",
            original_filename="joins-v2.md",
            course_id="sql-demo",
        )

        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(first.sha256, hashlib.sha256(self.lesson).hexdigest())
        self.assertEqual(first.processing_status, "UPLOADED")
        self.assertEqual(first.synthetic_provenance_label, SYNTHETIC_PROVENANCE_LABEL)
        self.assertIsNotNone(datetime.fromisoformat(first.upload_timestamp_utc).tzinfo)
        self.assertEqual(self.registry.get_lesson("lesson-joins"), second)
        self.assertEqual(self.registry.get_lesson("lesson-joins", 1), first)
        self.assertEqual(self.registry.read_lesson_bytes("lesson-joins", 1), self.lesson)

        reopened = DemoAuthoringRegistry(self.storage)
        self.assertEqual(reopened.get_lesson("lesson-joins", 2), second)
        self.assertEqual(len(reopened.list_lessons(course_id="sql-demo")), 2)

    def test_path_upload_status_and_integrity_check(self) -> None:
        source_path = Path(self.temp_dir.name) / "source.md"
        source_path.write_bytes(self.lesson)
        record = self.registry.upload_lesson(
            source_path, source_document_id="doc:path", course_id="course:1"
        )
        processing = self.registry.set_lesson_processing_status("doc:path", 1, "PROCESSING")
        processed = self.registry.set_lesson_processing_status("doc:path", 1, "PROCESSED")

        self.assertEqual(record.original_filename, "source.md")
        self.assertEqual(processing.processing_status, "PROCESSING")
        self.assertEqual(processed.processing_status, "PROCESSED")
        stored = self.storage / processed.stored_content_path
        stored.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.registry.read_lesson_bytes("doc:path", 1)

    def test_upload_rejects_unsafe_or_unlabelled_material(self) -> None:
        with self.assertRaisesRegex(ValueError, "provenance label"):
            self.registry.upload_lesson(
                b"ordinary material",
                source_document_id="doc-1",
                original_filename="lesson.md",
                course_id="course-1",
            )
        with self.assertRaisesRegex(ValueError, "basename"):
            self.registry.upload_lesson(
                self.lesson,
                source_document_id="doc-1",
                original_filename="../lesson.md",
                course_id="course-1",
            )
        with self.assertRaises(ValueError):
            self.registry.upload_lesson(
                self.lesson,
                source_document_id="../../escape",
                original_filename="lesson.md",
                course_id="course-1",
            )

    def test_assignment_draft_publish_and_filter_are_local_only(self) -> None:
        draft = self.registry.create_assignment(
            assignment_id="assignment-left-join",
            course_id="sql-demo",
            question_ids=["sql_join_02"],
            kg_node_ids=["LEFT_OUTER_JOIN", "MISSING_MATCHING_ROWS"],
            grading_config={
                "grader": "deterministic_sql",
                "required_result": "all_departments",
                "max_points": 1,
            },
        )
        self.assertEqual(draft.publication_status, "DRAFT")
        self.assertIsNone(draft.publication_timestamp_utc)
        self.assertEqual(draft.publication_label, LOCAL_PUBLICATION_LABEL)
        self.assertFalse(draft.native_prairielearn_publication)
        self.assertEqual(self.registry.list_assignments(published_only=True), [])

        published = self.registry.publish_assignment(draft.assignment_id)
        self.assertEqual(published.publication_status, "PUBLISHED_LOCAL_DEMO")
        self.assertIsNotNone(published.publication_timestamp_utc)
        self.assertIsNotNone(datetime.fromisoformat(published.publication_timestamp_utc).tzinfo)
        self.assertEqual(published.publication_channel, "LOCAL_SIIP_DEMO_REGISTRY")
        self.assertFalse(published.native_prairielearn_publication)
        self.assertEqual(
            self.registry.list_assignments(course_id="sql-demo", published_only=True),
            [published],
        )

        # Publishing is idempotent and preserves the first publication timestamp.
        self.assertEqual(self.registry.publish_assignment(draft.assignment_id), published)
        reopened = DemoAuthoringRegistry(self.storage)
        self.assertEqual(reopened.get_assignment(draft.assignment_id), published)

        raw = json.loads((self.storage / "demo_authoring_registry.json").read_text("utf-8"))
        self.assertFalse(raw["assignments"][0]["native_prairielearn_publication"])

    def test_duplicate_assignment_and_invalid_config_fail_closed(self) -> None:
        kwargs = {
            "assignment_id": "assignment-1",
            "course_id": "course-1",
            "question_ids": ["question-1"],
            "kg_node_ids": ["INNER_JOIN"],
            "grading_config": {"grader": "deterministic_sql"},
        }
        self.registry.create_assignment(**kwargs)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.registry.create_assignment(**kwargs)
        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            self.registry.create_assignment(
                **{**kwargs, "assignment_id": "assignment-2", "grading_config": {"bad": {1}}}
            )

    def test_course_module_and_assignment_lineage_survive_restart(self) -> None:
        self.registry.create_course(course_id="course-a", title="Database systems")
        self.registry.create_module(course_id="course-a", module_id="joins", title="JOINs")
        lesson = self.registry.upload_lesson(
            self.lesson,
            source_document_id="joins-lesson",
            original_filename="joins.md",
            course_id="course-a",
            module_id="joins",
        )
        self.registry.set_lesson_processing_status("joins-lesson", 1, "PROCESSING")
        self.registry.set_lesson_processing_status("joins-lesson", 1, "PROCESSED")
        assignment = self.registry.create_assignment(
            assignment_id="joins-assignment",
            course_id="course-a",
            module_id="joins",
            source_document_id=lesson.source_document_id,
            source_version=lesson.version,
            graph_id="kg-joins",
            graph_version=1,
            question_ids=["sql_join_04"],
            kg_node_ids=["LEFT_OUTER_JOIN"],
            grading_config={"engine": "deterministic_sql"},
        )
        reopened = DemoAuthoringRegistry(self.storage)
        self.assertEqual(reopened.get_assignment(assignment.assignment_id), assignment)
        self.assertEqual(reopened.list_courses()[0]["course_id"], "course-a")
        self.assertEqual(reopened.list_modules(course_id="course-a")[0]["module_id"], "joins")
        self.assertEqual(reopened.get_lesson("joins-lesson").module_id, "joins")

    def test_module_and_source_cannot_cross_course_boundaries(self) -> None:
        self.registry.create_course(course_id="course-a", title="A")
        self.registry.create_course(course_id="course-b", title="B")
        self.registry.create_module(course_id="course-a", module_id="joins", title="JOINs")
        with self.assertRaisesRegex(ValueError, "selected course"):
            self.registry.upload_lesson(
                self.lesson,
                source_document_id="lesson",
                original_filename="joins.md",
                course_id="course-b",
                module_id="joins",
            )
        self.assertEqual(self.registry.list_lessons(), [])

    def test_invalid_upload_formats_and_processing_transitions_fail_closed(self) -> None:
        for filename, content in (
            ("lesson.pdf", self.lesson),
            ("lesson.md", self.lesson + b"\x00"),
            ("lesson.txt", self.lesson + b"\xff"),
            ("C:\\lesson.md", self.lesson),
        ):
            with self.subTest(filename=filename, content_suffix=content[-1:]):
                with self.assertRaises(ValueError):
                    self.registry.upload_lesson(
                        content,
                        source_document_id="invalid",
                        course_id="course",
                        original_filename=filename,
                    )
        self.registry.upload_lesson(
            self.lesson,
            source_document_id="valid",
            course_id="course",
            original_filename="lesson.md",
        )
        with self.assertRaisesRegex(ValueError, "transition"):
            self.registry.set_lesson_processing_status("valid", 1, "PROCESSED")
        self.registry.set_lesson_processing_status("valid", 1, "PROCESSING")
        self.registry.set_lesson_processing_status("valid", 1, "FAILED")
        self.registry.set_lesson_processing_status("valid", 1, "PROCESSING")
        self.registry.set_lesson_processing_status("valid", 1, "PROCESSED")

    def test_multiple_registry_instances_do_not_lose_concurrent_uploads(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        registries = [DemoAuthoringRegistry(self.storage) for _ in range(2)]

        def upload(index):
            return registries[index % 2].upload_lesson(
                self.lesson,
                source_document_id="concurrent",
                course_id="course",
                original_filename="lesson.md",
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            records = list(executor.map(upload, range(10)))
        self.assertEqual(sorted(row.version for row in records), list(range(1, 11)))
        self.assertEqual(len(self.registry.list_lessons()), 10)


class SyntheticLessonContentTests(unittest.TestCase):
    def test_full_lesson_covers_required_concepts_and_boundary(self) -> None:
        lesson_path = ROOT / "demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md"
        lesson = lesson_path.read_text(encoding="utf-8")
        for required_text in (
            SYNTHETIC_PROVENANCE_LABEL,
            "INNER JOIN",
            "LEFT OUTER JOIN",
            "NULL",
            "missing matching records",
            "Business scenario",
        ):
            self.assertIn(required_text.casefold(), lesson.casefold())
        self.assertIn("not authored or", lesson)
        self.assertIn("not presented as institutional course material", lesson)


if __name__ == "__main__":
    unittest.main()
