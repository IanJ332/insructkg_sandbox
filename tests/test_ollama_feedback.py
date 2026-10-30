import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

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
            for required in (
                "current question tags",
                "possible causes",
                "question_count",
                "evidence_count",
                "reviewed_relationships",
                "not a trajectory",
                "prerequisite-specific",
                "attempt IDs",
                "approved_prerequisite_history",
                "MUST include",
                "matching keys",
            ):
                self.assertIn(required, prompt)
            self.assertIn(
                "No approved prerequisite history is supplied; make no claim about prior performance",
                prompt,
            )
            self.assertIn("lecture examples can use the reverse table orientation", prompt)
            self.assertIn("Do not prescribe replacement join types", prompt)
            self.assertEqual(result["prompt_version"], "siip-feedback-v9")
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

    def test_history_signal_uses_only_approved_prerequisites(self):
        class Provider:
            model = "fixture-model"
            context = None

            def generate(self, context):
                self.context = context
                return {
                    "feedback_text": "Consider which rows should remain in the result.",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }, None

        base = {
            "mode": "kg",
            "grade": {"status": "semantic_error", "score": 0},
            "lecture_evidence": [],
            "prerequisites": ["JOIN_CONDITION"],
            "student_mastery": {
                "JOIN_CONDITION": {
                    "mastery_estimate": 0.25,
                    "question_count": 1,
                    "evidence_count": 2,
                },
                "LEFT_OUTER_JOIN": {
                    "mastery_estimate": 0.75,
                    "question_count": 1,
                    "evidence_count": 2,
                },
            },
        }
        provider = Provider()
        result = {"status": "semantic_error", "score": 0, "observation": "wrong_rows"}
        with patch("siip.feedback.build_context", return_value=base):
            output = generate_feedback(
                "sql_join_02", "SELECT 1", result, provider=provider, grounding={"fixture": True}
            )
        self.assertEqual(output["inference_status"], "live_success")
        self.assertEqual(provider.context["grade"]["score"], 0)
        self.assertEqual(result["score"], 0)
        self.assertEqual(
            provider.context["approved_prerequisite_history"],
            [
                {
                    "concept": "JOIN_CONDITION",
                    "descriptive_estimate": 0.25,
                    "question_count": 1,
                    "evidence_count": 2,
                    "evidence_level": "weaker",
                }
            ],
        )

    def test_history_present_prioritizes_evidence_in_system_prompt(self):
        captured = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, *_):
                return json.dumps(
                    {
                        "done": True,
                        "message": {
                            "content": json.dumps(
                                {
                                    "feedback_text": "Consider which rows should remain in the result.",
                                    "candidate_concepts": [],
                                    "evidence_references": [],
                                }
                            )
                        },
                    }
                ).encode()

        class Opener:
            def open(self, request, timeout):
                captured.append(json.loads(request.data))
                return Response()

        history = [
            {
                "concept": "JOIN_CONDITION",
                "descriptive_estimate": 0.25,
                "question_count": 1,
                "evidence_count": 2,
                "evidence_level": "weaker",
            }
        ]
        provider = OllamaProvider("http://127.0.0.1:11434/v1", "fixture")
        with patch("urllib.request.build_opener", return_value=Opener()):
            provider.generate(
                {
                    "_question_id": "sql_join_02",
                    "mode": "kg",
                    "approved_prerequisite_history": history,
                    "student_mastery": {
                        "JOIN_CONDITION": {
                            "mastery_estimate": 0.25,
                            "question_count": 1,
                            "evidence_count": 2,
                        }
                    },
                }
            )
        self.assertEqual(provider.last_request_payload, captured[0])
        wire_context = json.loads(captured[0]["messages"][1]["content"])
        self.assertNotIn("student_mastery", wire_context)
        self.assertEqual(
            wire_context["historical_concept_evidence"]["JOIN_CONDITION"]["descriptive_estimate"],
            0.25,
        )
        prompt = captured[0]["messages"][0]["content"]
        self.assertIn("Start feedback_text with an uncertainty-qualified account", prompt)
        self.assertIn("including its attempt and question counts", prompt)
        self.assertIn(json.dumps(history), prompt)
        self.assertIn("QUALITY PRIORITY", prompt)
        self.assertIn("solid understanding", prompt)
        self.assertIn("which pairs match", prompt)
        self.assertIn("Do not prescribe replacement join types", prompt)
        self.assertNotIn("No approved prerequisite history is supplied", prompt)

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
        self.assertEqual(
            projected["historical_concept_evidence"]["JOIN_CONDITION"]["descriptive_estimate"], 0.75
        )
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

    def test_native_transport_rejects_external_hosts(self):
        with self.assertRaises(ValueError):
            OllamaProvider("https://example.com/v1", "unused")


if __name__ == "__main__":
    unittest.main()
