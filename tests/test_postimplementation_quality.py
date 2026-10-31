"""Regressions for observed PR #9 output/provenance and directional boundaries."""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip import feedback, original_instructkg


class PostimplementationQualityTests(unittest.TestCase):
    def test_actual_captured_response_is_rejected_at_output_validation(self):
        call = json.loads(
            (
                ROOT / "docs/release/evidence/original_chunk_integration/provider_calls.json"
            ).read_text()
        )[0]
        context = copy.deepcopy(call["context"])
        provider = SimpleNamespace(model="qwen3:8b", generate=lambda _: tuple(call["raw_return"]))
        with patch.object(feedback, "build_context", return_value=context):
            result = feedback.generate_feedback(
                context["_question_id"],
                context["student_sql"],
                context["grade"],
                "kg",
                provider=provider,
            )
        self.assertEqual(result["inference_status"], "provider_error_fallback")
        self.assertEqual(result["failure_stage"], "output_validation")
        self.assertEqual(result["error_details"], "potential_sql_solution_leakage")
        self.assertNotEqual(result["feedback_text"], call["raw_return"][0]["feedback_text"])
        self.assertNotIn("SELECT", result["feedback_text"])

    def test_reviewed_metadata_filter_preserves_mixed_content_and_ids(self):
        chunks = [
            {"chunk_id": f"lecture__{i}", "text": text, "page_numbers": [1], "chunk_index": i}
            for i, text in enumerate(("License", "Teaching", "Mixed"))
        ]
        original = copy.deepcopy(chunks)
        items = {"#/texts/0": {"text": "License"}, "#/texts/1": {"text": "Teaching"}}
        exclusion = {
            "item_ref": "#/texts/0",
            "text_sha256": hashlib.sha256(b"License").hexdigest(),
            "reviewed_by": "instructor_alawini",
            "reason": "Synthetic license, not a lesson concept.",
        }
        selected, selection = original_instructkg.instructional_chunks(
            chunks, [["#/texts/0"], ["#/texts/1"], ["#/texts/0", "#/texts/1"]], items, [exclusion]
        )
        self.assertEqual(selected, chunks[1:])
        self.assertEqual(selection["mixed_chunks_retained"], ["lecture__2"])
        self.assertEqual(chunks, original)
        for changed in (
            {**exclusion, "text_sha256": "0" * 64},
            {**exclusion, "reviewed_by": "S001"},
            {**exclusion, "item_ref": "unknown"},
        ):
            with self.assertRaises(original_instructkg.OriginalPipelineError):
                original_instructkg.instructional_chunks(
                    chunks, [["#/texts/0"]] * 3, items, [changed]
                )

    def test_directional_passes_recompute_and_restore_original_helper(self):
        module = SimpleNamespace(_cooc_counts=lambda _: {("A", "B"): 1})
        original = module._cooc_counts

        def build(**kwargs):
            self.assertEqual(kwargs["clusters"], [])
            return [
                {"pair": list(pair), "source_specific_evidence": pair[0]}
                for pair in module._cooc_counts({})
            ]

        module.build_pairpackets = build
        forward, reverse = original_instructkg.directional_pairpackets(module, [], [])
        self.assertEqual(forward[0]["source_specific_evidence"], "A")
        self.assertEqual(reverse[0]["source_specific_evidence"], "B")
        self.assertIs(module._cooc_counts, original)
        module.build_pairpackets = lambda **_: [{"pair": ["A", "B"]}]
        with self.assertRaises(original_instructkg.OriginalPipelineError):
            original_instructkg.directional_pairpackets(module, [], [])
        self.assertIs(module._cooc_counts, original)


if __name__ == "__main__":
    unittest.main()
