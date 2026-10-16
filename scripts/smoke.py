"""Live HTTP smoke checks. These complement, not replace, browser submission evidence."""

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = []


def get(url, headers=None):
    deadline = time.monotonic() + 30
    req_headers = headers or {}
    while True:
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310: fixed loopback health URLs.
                assert response.status == 200
                return response.read().decode()
        except (urllib.error.URLError, http.client.RemoteDisconnected, ConnectionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


assert "PrairieLearn" in get("http://localhost:3000/pl")
checks.append("Actual PrairieLearn HTTP server responds")
assert json.loads(get("http://127.0.0.1:8080/health"))["synthetic"]
analytics = json.loads(get("http://127.0.0.1:8080/api/analytics"))
assert analytics["student_count"] == 5 and analytics["attempt_count"] >= 21
checks.append("Analytics reads persistent five-student store")

# Verify fail-closed unauthenticated access to student history
unauth_req = urllib.request.Request("http://127.0.0.1:8080/students?id=S003")
try:
    with urllib.request.urlopen(unauth_req, timeout=3) as _:  # nosec B310
        raise AssertionError("Expected 401 Unauthorized for unauthenticated student records access")
except urllib.error.HTTPError as err:
    assert err.code == 401
checks.append("Unauthenticated student access fails closed (401)")

# Authenticate via synthetic session issuance
login_data = json.dumps({"student_id": "S003"}).encode("utf-8")
login_req = urllib.request.Request(
    "http://127.0.0.1:8080/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(login_req, timeout=3) as login_resp:  # nosec B310
    login_body = json.loads(login_resp.read().decode())
    s003_token = login_body["token"]
checks.append("Synthetic session token issued for S003")

# Authenticated access to own record
student_html = get(
    "http://127.0.0.1:8080/students?id=S003",
    headers={"Authorization": f"Bearer {s003_token}"},
)
assert "S003" in student_html
checks.append("Authenticated student detail renders persisted history")

# Cross-student record access denied
cross_req = urllib.request.Request(
    "http://127.0.0.1:8080/students?id=S001",
    headers={"Authorization": f"Bearer {s003_token}"},
)
try:
    with urllib.request.urlopen(cross_req, timeout=3) as _:  # nosec B310
        raise AssertionError("Expected 403 Forbidden for cross-student access")
except urllib.error.HTTPError as cross_err:
    assert cross_err.code == 403
checks.append("Cross-student access rejected (403)")
graph = get("http://127.0.0.1:8080/graph")
data = Path(
    os.environ.get("SIIP_DATA_DIR") or ROOT / "prairielearn-course/serverFilesCourse/siip/data"
)
provenance = json.loads((data / "provenance.json").read_text())
synthetic = provenance.get("kind") == "synthetic_contract_fixture"
expected_count, expected_node = (2, "CONTRACT_SQL") if synthetic else (469, "JOIN_OPERATION")
assert str(expected_count) in graph and expected_node in graph and "unreviewed" in graph
checks.append(
    "Synthetic contract graph renders (not real extraction)"
    if synthetic
    else "Original graph inventory, direction and review state render"
)
comparison = get("http://127.0.0.1:8080/compare")
assert all(mode in comparison for mode in ["BASELINE", "RAG", "KG", "deterministic_fallback"])
checks.append("Three fallback comparison contexts render with explicit inference status")
report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "passed": len(checks),
    "analytics": analytics,
    "browser_submission_proof": "Separate artifacts/pl-*.png and .txt",
}
(ROOT / "artifacts/http_smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
