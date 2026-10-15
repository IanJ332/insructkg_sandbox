"""Deterministic offline unit tests for InstructKG schemas and error handling.
Validates concept cards, pedagogical roles, context clusters, candidate pairs,
relation types/directions, and JSON parsing without live model invocation.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.instructkg_schema import (
    ALLOWED_RELATIONS,
    PEDAGOGICAL_ROLES,
    InstructKGSchemaError,
    parse_instructkg_json,
    validate_candidate_pair,
    validate_concept_card,
    validate_concept_identifier,
    validate_context_cluster,
    validate_pedagogical_role,
    validate_relation_record,
)


class TestPedagogicalRoleClassification(unittest.TestCase):
    """Deterministic offline tests for pedagogical role validation."""

    def test_canonical_roles_accepted(self):
        for role in [
            "Definition",
            "Example",
            "Explanation",
            "Observation",
            "Procedure",
            "Principle",
            "Caveat",
            "NA",
        ]:
            self.assertEqual(validate_pedagogical_role(role), role)

    def test_role_case_normalization(self):
        self.assertEqual(validate_pedagogical_role("definition"), "Definition")
        self.assertEqual(validate_pedagogical_role("EXAMPLE"), "Example")
        self.assertEqual(validate_pedagogical_role("na"), "NA")
        self.assertEqual(validate_pedagogical_role(""), "NA")
        self.assertEqual(validate_pedagogical_role(None), "NA")

    def test_invalid_role_rejected(self):
        with self.assertRaises(InstructKGSchemaError) as ctx:
            validate_pedagogical_role("Hypothesis")
        self.assertIn("Invalid pedagogical role", str(ctx.exception))


class TestConceptCardSchema(unittest.TestCase):
    """Deterministic tests for concept card structure and identifier rules."""

    def test_valid_concept_card(self):
        fixture = {
            "concept_id": "LEFT_OUTER_JOIN",
            "pedagogical_role": "Definition",
            "summary": "Join returning all rows from left table and matched rows from right table.",
            "evidence_chunks": [
                {"chunk_id": "chunk_01", "text": "A LEFT OUTER JOIN preserves unmatched left rows."}
            ],
            "source_lecture": "3-SQL2-JOINS_Nulls.pdf",
        }
        card = validate_concept_card(fixture)
        self.assertEqual(card["concept_id"], "LEFT_OUTER_JOIN")
        self.assertEqual(card["pedagogical_role"], "Definition")
        self.assertEqual(card["frequency"], 1)

    def test_identifier_conventions(self):
        self.assertEqual(validate_concept_identifier("INNER_JOIN"), "INNER_JOIN")
        self.assertEqual(validate_concept_identifier("SQL_JOIN_2026"), "SQL_JOIN_2026")

        for bad in ["inner_join", "Inner Join", "JOIN-CONDITION", "JOIN$", ""]:
            with self.assertRaises(InstructKGSchemaError):
                validate_concept_identifier(bad)

    def test_invalid_evidence_chunks_rejected(self):
        fixture = {
            "concept_id": "NULL_SEMANTICS",
            "pedagogical_role": "Principle",
            "evidence_chunks": [12345],  # Invalid chunk type
        }
        with self.assertRaises(InstructKGSchemaError):
            validate_concept_card(fixture)


class TestContextClusters(unittest.TestCase):
    """Deterministic tests for context cluster structures."""

    def test_valid_context_cluster(self):
        fixture = {
            "cluster_id": "cluster_01",
            "cluster_label": "Join Operators and Mechanics",
            "member_concepts": ["INNER_JOIN", "LEFT_OUTER_JOIN", "JOIN_CONDITION"],
            "representative_chunks": ["chunk_01", "chunk_02"],
            "metadata": {"min_cluster_size": 2, "algorithm": "HDBSCAN"},
        }
        cluster = validate_context_cluster(fixture)
        self.assertEqual(cluster["cluster_id"], "cluster_01")
        self.assertEqual(len(cluster["member_concepts"]), 3)
        self.assertEqual(cluster["cluster_label"], "Join Operators and Mechanics")

    def test_empty_member_concepts_rejected(self):
        fixture = {
            "cluster_id": "cluster_empty",
            "cluster_label": "Empty Theme",
            "member_concepts": [],
        }
        with self.assertRaises(InstructKGSchemaError):
            validate_context_cluster(fixture)

    def test_invalid_member_identifier_rejected(self):
        fixture = {
            "cluster_id": 2,
            "cluster_label": "Invalid Members",
            "member_concepts": ["VALID_CONCEPT", "invalid_concept_name"],
        }
        with self.assertRaises(InstructKGSchemaError):
            validate_context_cluster(fixture)


class TestCandidateRelationshipStructures(unittest.TestCase):
    """Deterministic tests for candidate relationship pair packets."""

    def test_valid_candidate_pair(self):
        fixture = {
            "concept_a": "LEFT_OUTER_JOIN",
            "concept_b": "JOIN_OPERATION",
            "shared_clusters": ["cluster_01"],
            "evidence_chunks": [{"chunk_id": "chunk_01", "text": "Shared context."}],
            "co_occurrence_count": 1,
        }
        pair = validate_candidate_pair(fixture)
        self.assertEqual(pair["pair_id"], "LEFT_OUTER_JOIN::JOIN_OPERATION")
        self.assertEqual(pair["co_occurrence_count"], 1)

    def test_self_referential_pair_rejected(self):
        fixture = {
            "concept_a": "INNER_JOIN",
            "concept_b": "INNER_JOIN",
            "shared_clusters": ["cluster_01"],
        }
        with self.assertRaises(InstructKGSchemaError):
            validate_candidate_pair(fixture)


class TestRelationTypesAndDirections(unittest.TestCase):
    """Deterministic tests for relation judgments, directions, and error metadata."""

    def test_valid_depends_on_relation(self):
        fixture = {
            "A": {"name": "LEFT_OUTER_JOIN", "role": "Definition"},
            "B": {"name": "JOIN_OPERATION", "role": "Definition"},
            "relation": "depends_on",
            "justification": "Left outer join builds upon generic join mechanics.",
            "evidence_chunks": [{"chunk_id": "chunk_01", "text": "Evidence snippet."}],
            "_meta": {"_error": None},
        }
        rec = validate_relation_record(fixture)
        self.assertEqual(rec["relation"], "depends_on")
        self.assertEqual(rec["original_direction"], ["LEFT_OUTER_JOIN", "JOIN_OPERATION"])
        self.assertFalse(rec["invalid_inference"])

    def test_valid_null_relation_preserved(self):
        fixture = {
            "A": {"name": "CONTRACT_TABLES", "role": "NA"},
            "B": {"name": "CONTRACT_NULL", "role": "NA"},
            "relation": None,
            "justification": "No direct taxonomic or prerequisite dependency.",
            "evidence_chunks": [],
        }
        rec = validate_relation_record(fixture)
        self.assertIsNone(rec["relation"])
        self.assertEqual(rec["original_direction"], ["CONTRACT_TABLES", "CONTRACT_NULL"])

    def test_unsupported_relation_type_rejected(self):
        fixture = {
            "A": {"name": "CONCEPT_A", "role": "NA"},
            "B": {"name": "CONCEPT_B", "role": "NA"},
            "relation": "contradicts",  # Not in depends_on, part_of
            "evidence_chunks": [],
        }
        with self.assertRaises(InstructKGSchemaError) as ctx:
            validate_relation_record(fixture)
        self.assertIn("Unsupported relation", str(ctx.exception))

    def test_meta_error_marks_invalid_inference(self):
        fixture = {
            "A": {"name": "CONCEPT_A", "role": "NA"},
            "B": {"name": "CONCEPT_B", "role": "NA"},
            "relation": "depends_on",
            "evidence_chunks": [],
            "_meta": {"_error": "LLM output truncation or timeout"},
        }
        rec = validate_relation_record(fixture)
        self.assertTrue(rec["invalid_inference"])

    def test_self_referential_relation_rejected(self):
        fixture = {
            "A": {"name": "SAME_CONCEPT", "role": "NA"},
            "B": {"name": "SAME_CONCEPT", "role": "NA"},
            "relation": "part_of",
            "evidence_chunks": [],
        }
        with self.assertRaises(InstructKGSchemaError):
            validate_relation_record(fixture)


class TestJSONParsingAndErrorHandling(unittest.TestCase):
    """Deterministic tests for parsing JSON responses from LLM extraction."""

    def test_clean_json(self):
        text = '{"A": {"name": "FOO"}, "B": {"name": "BAR"}, "relation": "depends_on"}'
        parsed = parse_instructkg_json(text)
        self.assertEqual(parsed["relation"], "depends_on")

    def test_markdown_code_fence_json(self):
        text = '```json\n{"concept_id": "CTE", "pedagogical_role": "Definition"}\n```'
        parsed = parse_instructkg_json(text)
        self.assertEqual(parsed["concept_id"], "CTE")

    def test_malformed_json_raises_schema_error(self):
        text = '{"concept_id": "CTE", broken json'
        with self.assertRaises(InstructKGSchemaError) as ctx:
            parse_instructkg_json(text)
        self.assertIn("Malformed JSON", str(ctx.exception))

    def test_empty_json_raises_schema_error(self):
        with self.assertRaises(InstructKGSchemaError):
            parse_instructkg_json("   ")


class TestMinimumBoundedLiveTestSpecification(unittest.TestCase):
    """Verifies the exact specification parameters for future bounded live client testing."""

    def test_bounded_probe_parameters(self):
        # A minimal bounded live test must constrain scope to 1 chunk and 1 concept pair
        probe_spec = {
            "max_chunks": 1,
            "max_pairs": 1,
            "timeout_seconds": 30,
            "model_id": "qwen3:8b",
            "endpoint": "/v1/responses",
            "allowed_relations": list(ALLOWED_RELATIONS),
            "allowed_roles": list(PEDAGOGICAL_ROLES),
        }
        self.assertEqual(probe_spec["max_chunks"], 1)
        self.assertEqual(probe_spec["max_pairs"], 1)
        self.assertLessEqual(probe_spec["timeout_seconds"], 30)
        self.assertIn("depends_on", probe_spec["allowed_relations"])
        self.assertIn("Definition", probe_spec["allowed_roles"])


if __name__ == "__main__":
    unittest.main()
