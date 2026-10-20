import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.feedback import OllamaProvider, generate_feedback


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
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_native_transport_rejects_external_hosts(self):
        with self.assertRaises(ValueError):
            OllamaProvider("https://example.com/v1", "unused")


if __name__ == "__main__":
    unittest.main()
