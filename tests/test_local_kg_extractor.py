import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_kg import DemoKGRepository
from siip.local_kg_extractor import (
    MAX_SOURCE_CHARS,
    LocalExtractionError,
    extract_candidates,
    validate_candidates,
)

TEXT = "A join predicate matches rows. INNER JOIN depends on a join predicate."
PAYLOAD = {
    "nodes": [
        {
            "id": "INNER_JOIN",
            "label": "INNER JOIN",
            "pedagogical_role": "Definition",
            "evidence_excerpt": "INNER JOIN depends on a join predicate.",
        },
        {
            "id": "JOIN_PREDICATE",
            "label": "join predicate",
            "pedagogical_role": "Definition",
            "evidence_excerpt": "A join predicate matches rows.",
        },
    ],
    "edges": [
        {
            "source": "INNER_JOIN",
            "relation": "depends_on",
            "target": "JOIN_PREDICATE",
            "evidence_excerpt": "INNER JOIN depends on a join predicate.",
            "justification": "The source explicitly states this prerequisite.",
            "confidence": 0.8,
        }
    ],
}
SOURCE = {
    "source_document_id": "test-source",
    "content": TEXT,
    "version": 2,
    "course_id": "course-a",
    "module_id": "module-a",
    "content_hash": "raw-file-hash",
}


class TestEvidenceValidation(unittest.TestCase):
    def test_direction_offsets_role_and_order_preserved(self):
        graph = validate_candidates(PAYLOAD, TEXT, "source-a")
        self.assertEqual(graph["nodes"][0]["id"], "JOIN_PREDICATE")
        self.assertEqual(graph["nodes"][0]["teaching_order"], 1)
        edge = graph["edges"][0]
        self.assertEqual((edge["source"], edge["target"]), ("INNER_JOIN", "JOIN_PREDICATE"))
        self.assertEqual(
            TEXT[edge["evidence_start_char"] : edge["evidence_end_char"]], edge["evidence_excerpt"]
        )
        self.assertEqual(edge["confidence_kind"], "uncalibrated_model_self_report")

    def test_ungrounded_and_malformed_concepts_fail_closed(self):
        for mutate in (
            lambda p: p["nodes"][0].update(label="Imaginary topic"),
            lambda p: p["nodes"][0].update(
                evidence_excerpt="A made-up quotation nowhere in source."
            ),
            lambda p: p["nodes"][0].update(pedagogical_role=["Definition"]),
            lambda p: p["nodes"][0].update(id="../unsafe"),
        ):
            payload = copy.deepcopy(PAYLOAD)
            mutate(payload)
            with self.assertRaises(LocalExtractionError):
                validate_candidates(payload, TEXT, "source-a")

    def test_duplicate_concept_is_rejected_while_valid_graph_survives(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["nodes"].append(copy.deepcopy(payload["nodes"][0]))
        graph = validate_candidates(payload, TEXT, "source-a")
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(graph["rejected_candidates"][0]["candidate_kind"], "node")

    def test_invalid_edges_are_rejected_without_losing_valid_evidence(self):
        payload = copy.deepcopy(PAYLOAD)
        for extra in (
            {"target": "MISSING"},
            {"target": "INNER_JOIN"},
            {"relation": "similar_to"},
            {"evidence_excerpt": "Not present in this source."},
            {"confidence": float("nan")},
            {"confidence": True},
            {"source": "JOIN_PREDICATE", "target": "INNER_JOIN"},
            {},
        ):
            edge = copy.deepcopy(PAYLOAD["edges"][0])
            edge.update(extra)
            payload["edges"].append(edge)
        graph = validate_candidates(payload, TEXT, "source-a")
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(len(graph["rejected_candidates"]), 8)

    def test_empty_and_arbitrary_json_fail_closed(self):
        for payload in (
            [],
            {},
            {"nodes": [], "edges": []},
            {"nodes": PAYLOAD["nodes"], "edges": []},
        ):
            with self.assertRaises(LocalExtractionError):
                validate_candidates(payload, TEXT, "source-a")

    def test_explicit_part_of_reversal_is_rejected(self):
        text = "NULL values are part of LEFT OUTER JOIN output."
        payload = {
            "nodes": [
                {"id": "NULL_SEMANTICS", "label": "NULL values", "evidence_excerpt": text},
                {"id": "LEFT_OUTER_JOIN", "label": "LEFT OUTER JOIN", "evidence_excerpt": text},
            ],
            "edges": [
                {
                    "source": "NULL_SEMANTICS",
                    "target": "LEFT_OUTER_JOIN",
                    "relation": "part_of",
                    "evidence_excerpt": text,
                    "justification": "NULL values form a component of this output.",
                }
            ],
        }
        self.assertEqual(
            validate_candidates(payload, text, "source-a")["edges"][0]["source"], "NULL_SEMANTICS"
        )
        payload["edges"][0].update(source="LEFT_OUTER_JOIN", target="NULL_SEMANTICS")
        with self.assertRaisesRegex(LocalExtractionError, "No evidence-validated"):
            validate_candidates(payload, text, "source-a")


class TestLocalRuntimeAndRepository(unittest.TestCase):
    @patch("siip.local_kg_extractor._post")
    def test_model_passage_selection_binds_exact_source_quotes(self, post):
        payload = copy.deepcopy(PAYLOAD)
        for record in payload["nodes"] + payload["edges"]:
            del record["evidence_excerpt"]
            record["evidence_id"] = "P001"
        post.return_value = {"response": json.dumps(payload), "done": True}
        graph = extract_candidates(TEXT, "source-a")
        self.assertEqual(graph["edges"][0]["evidence_excerpt"], TEXT)
        self.assertEqual(
            post.call_args.args[0]["format"]["properties"]["nodes"]["items"]["properties"][
                "evidence_id"
            ]["enum"],
            ["P001"],
        )
        payload["nodes"][0]["evidence_id"] = "invented"
        post.return_value = {"response": json.dumps(payload), "done": True}
        with self.assertRaisesRegex(LocalExtractionError, "unknown source passage"):
            extract_candidates(TEXT, "source-a")

    @patch("siip.local_kg_extractor._post")
    def test_bounded_runtime_and_provenance(self, post):
        post.return_value = {
            "response": json.dumps(PAYLOAD),
            "done": True,
            "prompt_eval_count": 100,
            "eval_count": 200,
        }
        graph = extract_candidates(TEXT, "source-a")
        self.assertEqual(graph["extraction_metadata"]["model"], "qwen3:8b")
        self.assertFalse(graph["extraction_metadata"]["truncated_source"])
        self.assertEqual(post.call_args.args[0]["options"]["num_predict"], 2400)
        self.assertFalse(post.call_args.args[0]["think"])
        for text in ("", "x" * (MAX_SOURCE_CHARS + 1)):
            with self.assertRaises(LocalExtractionError):
                extract_candidates(text, "source-a")
        self.assertEqual(post.call_count, 1)

    @patch.dict(os.environ, {"SIIP_DEMO_KG_MODE": "local"})
    @patch("siip.local_kg_extractor._post")
    def test_actual_mode_review_version_and_source_lineage(self, post):
        post.return_value = {"response": json.dumps(PAYLOAD), "done": True}
        with tempfile.TemporaryDirectory() as directory:
            repository = DemoKGRepository(directory)
            graph = repository.generate_candidates(SOURCE)
            self.assertEqual(graph["extraction_mode"], "LOCAL_LLM_ASSISTED_EXTRACTION")
            self.assertFalse(graph["actual_instructkg_extraction"])
            self.assertEqual(graph["source_version"], 2)
            self.assertEqual(graph["course_id"], "course-a")
            self.assertEqual(graph["registered_content_hash"], "raw-file-hash")
            edge = graph["edges"][0]
            self.assertEqual(edge["source_type"], "local_llm_assisted_extraction")
            repository.review_edge(
                graph["graph_id"], edge["edge_id"], "NEEDS_REVISION", "instructor"
            )
            repository.save_version(graph["graph_id"])
            self.assertEqual(
                repository.list_versions(graph["graph_id"])[0]["review_counts"]["NEEDS_REVISION"], 1
            )
            self.assertEqual(
                repository.generate_candidates(SOURCE)["edges"][0]["review_state"], "NEEDS_REVISION"
            )
            self.assertEqual(post.call_count, 1)
            changed = dict(SOURCE, version=3)
            self.assertNotEqual(
                repository.generate_candidates(changed)["graph_id"], graph["graph_id"]
            )

    @patch.dict(os.environ, {"SIIP_DEMO_KG_MODE": "local"})
    @patch(
        "siip.local_kg_extractor._post", side_effect=LocalExtractionError("Local model timed out")
    )
    def test_explicit_fixture_fallback_and_local_identity(self, post):
        with tempfile.TemporaryDirectory() as directory:
            repository = DemoKGRepository(directory)
            fallback = repository.generate_candidates(SOURCE)
            self.assertEqual(fallback["extraction_mode"], "SYNTHETIC_FIXTURE")
            self.assertEqual(fallback["source_type"], "synthetic_fixture")
            self.assertEqual(fallback["requested_extraction_mode"], "local")
            self.assertIn("timed out", fallback["fallback_reason"])
            self.assertIn("SYNTHETIC", fallback["scientific_boundary"])
            with patch.dict(os.environ, {"SIIP_DEMO_KG_MODE": "synthetic"}):
                fixture = repository.generate_candidates(SOURCE)
            self.assertNotEqual(fallback["graph_id"], fixture["graph_id"])


if __name__ == "__main__":
    unittest.main()
