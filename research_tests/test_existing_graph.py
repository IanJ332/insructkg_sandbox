"""Explicit local-only original artifact verification; not part of public contract CI."""

import sys
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "prairielearn-course/serverFilesCourse")
)
from siip.feedback import load_graphs


class ExistingResearchGraphTests(unittest.TestCase):
    def test_real_schema_counts_provenance(self):
        graph, _ = load_graphs()
        self.assertEqual(len(graph.records), 469)
        self.assertEqual(len(graph.nodes), 121)
        self.assertEqual(sum(r["relation"] is not None for r in graph.records), 319)
        self.assertEqual(len(graph.errors), 0)
        self.assertEqual(
            graph.records[0]["provenance"]["commit"], "c34a7786528e78766f15d918ab17aca2a9f7dc0b"
        )

    def test_questionable_direction_unchanged(self):
        g, _ = load_graphs()
        r = next(
            r
            for r in g.records
            if r["source"] == "JOIN_OPERATION" and r["target"] == "LEFT_OUTER_JOIN"
        )
        self.assertEqual(r["relation"], "part_of")
        self.assertEqual(r["original_direction"], ["JOIN_OPERATION", "LEFT_OUTER_JOIN"])
        self.assertEqual(r["review_status"], "unreviewed")
        self.assertTrue(r["evidence"])
        self.assertEqual(g.edges(), [])
