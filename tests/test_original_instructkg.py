import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "prairielearn-course/serverFilesCourse")
)
from siip import demo_kg, original_instructkg


class OriginalIntegrationBoundaryTests(unittest.TestCase):
    def test_model_transport_rejects_remote_and_non_http_endpoints(self):
        for endpoint in (
            "file:///tmp/model",
            "https://example.com",
            "http://127.0.0.1@remote.invalid",
            "http://localhost:11434?url=remote",
        ):
            with (
                self.subTest(endpoint=endpoint),
                patch.dict(os.environ, {"SIIP_OLLAMA_URL": endpoint}),
            ):
                with self.assertRaises(original_instructkg.OriginalPipelineError):
                    original_instructkg.OllamaResponses(Path("unused.jsonl"))

    def test_relation_contract_rejects_silent_invalid_nulls(self):
        validate = original_instructkg.validate_relation_responses
        for value in (
            '{"relation":null}',
            '{"relation":"none"}',
            '{"relation":"depends_on"}',
            '{"relation":"part of"}',
        ):
            validate([value], json.loads)
        for value in (
            "{}",
            '{"relation":""}',
            '{"relation":"unrelated"}',
            '{"relation":42}',
            "invalid",
        ):
            with (
                self.subTest(value=value),
                self.assertRaises(original_instructkg.OriginalPipelineError),
            ):
                validate([value], json.loads)

    def setUp(self):
        self.source = {
            "source_document_id": "lesson-1",
            "content_hash": "abc",
            "source_path": "unused.pdf",
            "requested_extraction_mode": original_instructkg.MODE,
        }
        self.result = {
            "nodes": [
                {"id": "JOIN_PREDICATE", "label": "Join predicate"},
                {"id": "JOIN", "label": "Join"},
            ],
            "edges": [
                {
                    "source": "JOIN",
                    "target": "JOIN_PREDICATE",
                    "relation": "depends_on",
                    "evidence_excerpt": "A join uses a predicate.",
                    "original_relation": {"A": {"role": "definition"}},
                }
            ],
            "extracted_text": "A join uses a predicate.",
            "extracted_chunks": [{"chunk_id": "lecture__0000", "page_numbers": [1]}],
            "extraction_metadata": {"clustering": "DEFERRED"},
            "rejected_candidates": [],
        }

    def test_original_result_reaches_review_and_version_without_changing_direction(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(original_instructkg, "generate", return_value=self.result) as run,
        ):
            repo = demo_kg.DemoKGRepository(directory)
            graph = repo.generate_candidates(self.source)
            run.assert_called_once()
            self.assertTrue(graph["actual_instructkg_extraction"])
            self.assertEqual(graph["registered_content_hash"], "abc")
            self.assertEqual(
                graph["source_content_sha256"],
                hashlib.sha256(self.result["extracted_text"].encode()).hexdigest(),
            )
            edge = graph["edges"][0]
            self.assertEqual((edge["source"], edge["target"]), ("JOIN", "JOIN_PREDICATE"))
            self.assertEqual(edge["review_state"], "UNREVIEWED")
            repo.review_edge(graph["graph_id"], edge["edge_id"], "APPROVE", "synthetic-instructor")
            self.assertEqual(
                repo.save_version(graph["graph_id"])["edges"][0]["review_state"], "APPROVED"
            )

    def test_failure_does_not_fall_back(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                original_instructkg,
                "generate",
                side_effect=original_instructkg.OriginalPipelineError("offline"),
            ),
        ):
            with self.assertRaisesRegex(demo_kg.DemoKGError, "offline"):
                demo_kg.DemoKGRepository(directory).generate_candidates(self.source)
            self.assertEqual(list(Path(directory).rglob("draft.json")), [])

    def test_opposite_model_judgments_remain_independent_unreviewed_candidates(self):
        import copy

        result = copy.deepcopy(self.result)
        reverse = {**result["edges"][0], "source": "JOIN_PREDICATE", "target": "JOIN"}
        result["edges"].append(reverse)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(original_instructkg, "generate", return_value=result),
        ):
            graph = demo_kg.DemoKGRepository(directory).generate_candidates(self.source)
        self.assertEqual(len({edge["edge_id"] for edge in graph["edges"]}), 2)
        self.assertTrue(all(edge["review_state"] == "UNREVIEWED" for edge in graph["edges"]))
        self.assertEqual(
            {(e["source"], e["target"]) for e in graph["edges"]},
            {("JOIN", "JOIN_PREDICATE"), ("JOIN_PREDICATE", "JOIN")},
        )

    def test_source_snapshot_verification_rejects_modified_files(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"SIIP_INSTRUCTKG_SOURCE_DIR": directory}),
            patch.object(original_instructkg, "HASHES", {"ingest.py": "0" * 64}),
        ):
            (Path(directory) / "ingest.py").write_text("changed")
            with self.assertRaisesRegex(original_instructkg.OriginalPipelineError, "integrity"):
                original_instructkg.verified_source()


if __name__ == "__main__":
    unittest.main()
