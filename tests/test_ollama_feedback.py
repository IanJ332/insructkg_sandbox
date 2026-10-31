import copy
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.feedback import FeedbackQualityError, OllamaProvider, generate_feedback, valid_output


class OllamaTransportTests(unittest.TestCase):
    def test_native_transport_is_local_structured_and_non_thinking(self):
        receipts = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                receipts.append(
                    (self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                )
                result = {
                    "model": "fixture-local-model",
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 8,
                    "message": {
                        "content": json.dumps(
                            {
                                "feedback_text": "Consider which rows the task requires retaining.",
                                "candidate_concepts": [],
                                "evidence_references": [],
                            }
                        )
                    },
                }
                data = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = OllamaProvider(
                f"http://127.0.0.1:{server.server_port}/v1", "fixture-local-model"
            )
            result = generate_feedback(
                "sql_join_04",
                "SELECT 1",
                {"status": "semantic_error", "score": 0, "observation": "wrong_rows"},
                mode="baseline",
                provider=provider,
            )
            self.assertEqual(result["inference_status"], "live_success")
            self.assertEqual(result["token_usage"]["total_tokens"], 20)
            path, payload = receipts[0]
            self.assertEqual(path, "/api/chat")
            self.assertFalse(payload["think"])
            self.assertFalse(payload["stream"])
            self.assertFalse(payload["format"]["additionalProperties"])
            prompt = payload["messages"][0]["content"]
            self.assertIn("deterministic grade is authoritative", prompt)
            self.assertIn("sparse histories can warrant the same advice", prompt)
            self.assertIn("Do not infer understanding", prompt)
            self.assertLess(len(prompt), 2000)
            self.assertEqual(result["prompt_version"], "siip-feedback-v11")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_nonsemantic_statuses_bypass_provider(self):
        class Provider:
            model = "fixture-model"

            def generate(self, context):
                raise AssertionError("provider must be bypassed")

        for status, score in (
            ("correct", 1),
            ("compilation_error", 0),
            ("unsupported_query", 0),
            ("execution_error", 0),
            ("unknown", 0),
        ):
            with self.subTest(status=status):
                result = generate_feedback(
                    "sql_join_02",
                    "SELECT 1",
                    {"status": status, "score": score, "observation": status},
                    mode="baseline",
                    provider=Provider(),
                )
                self.assertEqual(result["inference_status"], "provider_bypassed_nonsemantic")
                self.assertEqual(result["provider_routing"], "bypassed_nonsemantic")
                self.assertIsNone(result["attempted_provider_identifier"])
                self.assertEqual(result["provider_identifier"], "deterministic")
                self.assertEqual(result["requested_model_identifier"], "fixture-model")
                self.assertEqual(result["candidate_concepts"], [])
                self.assertIsNone(result["token_usage"])

    def test_history_projection_and_observed_claim_guard(self):
        context = {
            "mode": "kg",
            "grade": {"status": "semantic_error"},
            "student_sql": "SELECT 1",
            "lecture_evidence": [],
            "student_mastery": {
                "JOIN_CONDITION": {
                    "mastery_estimate": 0.75,
                    "question_count": 1,
                    "evidence_count": 2,
                }
            },
        }
        from siip.feedback import model_context_projection

        projected = model_context_projection(context)
        self.assertNotIn("student_mastery", projected)
        self.assertNotIn("historical_concept_evidence", projected)
        self.assertEqual(context["student_mastery"]["JOIN_CONDITION"]["mastery_estimate"], 0.75)
        for claim in (
            "weaker understanding",
            "stronger mastery",
            "solid understanding",
            "suggests they understand",
        ):
            with self.subTest(claim=claim):
                obj = {
                    "feedback_text": "Prior evidence " + claim + " this concept.",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }
                with self.assertRaises(FeedbackQualityError):
                    valid_output(obj, context, "sql_join_02", check_quality=True)
        valid_output(
            {
                "feedback_text": "Two attempts offer limited evidence; inspect matching keys.",
                "candidate_concepts": [],
                "evidence_references": [],
            },
            context,
            "sql_join_02",
            check_quality=True,
        )

    def test_model_projection_preserves_evidence_ids_and_graph_policy(self):
        from siip.feedback import model_context_projection

        context = {
            "question": "Which rows should remain?",
            "student_sql": "SELECT 1",
            "grade": {"status": "semantic_error", "score": 0},
            "diagnosis": {"candidate_concepts": ["LEFT_OUTER_JOIN"], "internal": "secret"},
            "lecture_evidence": [
                {"id": "p1", "text": "first", "sha": "private"},
                {"id": "p2", "text": "second", "reviewer": "private"},
            ],
            "reviewed_relationships": [
                {"source": "A", "target": "B", "relation": "depends_on", "edge_id": "private"}
            ],
            "development_relationships": [
                {"source": "A", "target": "C", "relation": "depends_on", "id": "private"}
            ],
            "graph_policy": "Development relationships are unreviewed.",
            "prerequisites": ["B"],
            "student_mastery": {"B": {"mastery_estimate": 0.3}},
            "grounding_provenance": {"sha": "private"},
            "_question_id": "sql_join_02",
        }
        original = copy.deepcopy(context)
        wire = model_context_projection(context)
        self.assertEqual(context, original)
        self.assertEqual(
            wire["lecture_evidence"],
            [{"id": "p1", "text": "first"}, {"id": "p2", "text": "second"}],
        )
        self.assertEqual(wire["graph_policy"], context["graph_policy"])
        self.assertEqual(
            wire["reviewed_relationships"],
            [{"source": "A", "target": "B", "relation": "depends_on"}],
        )
        self.assertEqual(
            wire["development_relationships"],
            [{"source": "A", "target": "C", "relation": "depends_on"}],
        )
        self.assertEqual(wire["candidate_concepts"], ["LEFT_OUTER_JOIN"])
        self.assertNotIn("private", json.dumps(wire))
        self.assertNotIn("mastery", json.dumps(wire))
        self.assertNotIn("_question_id", wire)
        valid_output(
            {
                "feedback_text": "Check which rows remain in the result.",
                "candidate_concepts": [],
                "evidence_references": ["p1", "p2"],
            },
            {**context, "mode": "kg"},
            "sql_join_02",
            check_quality=True,
        )

    def test_native_transport_rejects_external_hosts(self):
        with self.assertRaises(ValueError):
            OllamaProvider("https://example.com/v1", "unused")


if __name__ == "__main__":
    unittest.main()
