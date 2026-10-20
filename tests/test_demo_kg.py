import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.demo_kg import (  # noqa: E402
    EXTRACTION_METHOD,
    PIPELINE_VERSION,
    SCIENTIFIC_BOUNDARY,
    DemoKGError,
    DemoKGRepository,
    generate_candidate_graph,
    list_candidate_graphs,
    list_graph_versions,
    retrieve_graph,
    review_candidate_edge,
    save_graph_version,
)

SOURCE = {
    "source_document_id": "source-sql-joins-001",
    "original_filename": "synthetic-sql-joins.md",
    "content_hash": "registered-demo-hash",
    "content": (
        "An INNER JOIN returns rows for which the join predicate matches. "
        "A LEFT OUTER JOIN keeps every row from the left table, even when a matching "
        "right row is missing. Missing matching rows produce NULL values in the right-side "
        "columns. SQL NULL semantics require IS NULL rather than equality with NULL."
    ),
}


class TestSyntheticCandidateGeneration(unittest.TestCase):
    def test_graph_is_deterministic_and_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = generate_candidate_graph(SOURCE, directory)
            second = generate_candidate_graph(SOURCE, directory)

            self.assertEqual(first, second)
            self.assertFalse(first["actual_instructkg_extraction"])
            self.assertEqual(first["scientific_boundary"], SCIENTIFIC_BOUNDARY)
            self.assertEqual(first["source_type"], "synthetic_fixture")
            self.assertEqual(first["extraction_method"], EXTRACTION_METHOD)
            self.assertEqual(first["pipeline_version"], PIPELINE_VERSION)
            self.assertEqual(
                {node["id"] for node in first["nodes"]},
                {
                    "INNER_JOIN",
                    "LEFT_OUTER_JOIN",
                    "NULL_SEMANTICS",
                    "JOIN_PREDICATE",
                    "MISSING_MATCHING_ROWS",
                },
            )

    def test_every_edge_has_complete_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            graph = generate_candidate_graph(SOURCE, directory)

            self.assertGreaterEqual(len(graph["edges"]), 4)
            for edge in graph["edges"]:
                self.assertEqual(edge["source_document_id"], SOURCE["source_document_id"])
                self.assertEqual(edge["extraction_method"], EXTRACTION_METHOD)
                self.assertEqual(edge["pipeline_version"], PIPELINE_VERSION)
                self.assertEqual(edge["scientific_boundary"], SCIENTIFIC_BOUNDARY)
                self.assertEqual(edge["review_state"], "UNREVIEWED")
                self.assertIsNone(edge["instructor_review_decision"])
                self.assertTrue(edge["evidence_excerpt"])
                self.assertIsInstance(edge["confidence"], float)

    def test_invalid_source_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DemoKGError, "source_document_id"):
                generate_candidate_graph({"content": "some text"}, directory)
            with self.assertRaisesRegex(DemoKGError, "non-empty content"):
                generate_candidate_graph({"source_document_id": "doc-1"}, directory)


class TestReviewAndVersionPersistence(unittest.TestCase):
    def test_review_decision_persists_and_saved_version_is_retrievable(self):
        with tempfile.TemporaryDirectory() as directory:
            graph = generate_candidate_graph(SOURCE, directory)
            graph_id = graph["graph_id"]
            edge_id = graph["edges"][0]["edge_id"]

            reviewed = review_candidate_edge(
                graph_id,
                edge_id,
                "approve",
                "synthetic-instructor-001",
                directory,
                notes="Direction and evidence accepted for this local demonstration.",
            )
            edge = next(edge for edge in reviewed["edges"] if edge["edge_id"] == edge_id)
            self.assertEqual(edge["review_state"], "APPROVED")
            self.assertEqual(edge["instructor_review_decision"], "APPROVE")
            self.assertEqual(edge["reviewed_by"], "synthetic-instructor-001")

            reloaded_draft = retrieve_graph(graph_id, directory)
            self.assertEqual(reloaded_draft, reviewed)

            saved = save_graph_version(graph_id, directory)
            self.assertEqual(saved["version"], 1)
            self.assertEqual(saved["status"], "SAVED")
            reloaded_version = retrieve_graph(graph_id, directory, version=1)
            self.assertEqual(reloaded_version, saved)
            saved_edge = next(
                edge for edge in reloaded_version["edges"] if edge["edge_id"] == edge_id
            )
            self.assertEqual(saved_edge["instructor_review_decision"], "APPROVE")

            on_disk = json.loads(
                (
                    Path(directory)
                    / graph_id
                    / "versions"
                    / "v0001.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(on_disk, saved)
            self.assertEqual(list_candidate_graphs(directory)[0]["graph_id"], graph_id)
            self.assertEqual(list_graph_versions(graph_id, directory)[0]["version"], 1)

    def test_reject_and_list_apis(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = DemoKGRepository(directory)
            graph = repository.generate_candidates(SOURCE)
            edge_id = graph["edges"][1]["edge_id"]
            repository.review_edge(
                graph["graph_id"], edge_id, "REJECT", "synthetic-instructor-001"
            )
            repository.save_version(graph["graph_id"])

            graphs = repository.list_graphs()
            versions = repository.list_versions(graph["graph_id"])
            self.assertEqual(len(graphs), 1)
            self.assertEqual(graphs[0]["scientific_boundary"], SCIENTIFIC_BOUNDARY)
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0]["review_counts"]["REJECTED"], 1)
            self.assertEqual(versions[0]["review_counts"]["UNREVIEWED"], 3)

    def test_invalid_review_inputs_do_not_change_persisted_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = DemoKGRepository(directory)
            graph = repository.generate_candidates(SOURCE)
            before = repository.retrieve(graph["graph_id"])

            with self.assertRaisesRegex(DemoKGError, "APPROVE or REJECT"):
                repository.review_edge(
                    graph["graph_id"], graph["edges"][0]["edge_id"], "maybe", "instructor"
                )
            with self.assertRaisesRegex(DemoKGError, "Unknown edge_id"):
                repository.review_edge(
                    graph["graph_id"], "edge-does-not-exist", "APPROVE", "instructor"
                )
            self.assertEqual(repository.retrieve(graph["graph_id"]), before)


if __name__ == "__main__":
    unittest.main()
