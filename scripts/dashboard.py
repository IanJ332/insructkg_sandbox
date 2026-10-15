"""Loopback-only synthetic instructor analytics and experiment viewer."""

import html
import json
import logging
import os
import sys
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.feedback import generate_feedback, load_graphs
from siip.grader import QUESTIONS, grade
from siip.identity import (
    create_signed_session_token,
    create_signed_ticket,
    verify_service_request,
    verify_signed_session_token,
    verify_signed_ticket,
)
from siip.jobs import AttemptConflictError, FeedbackJobRepository, JobQueueFullError
from siip.observability import event
from siip.store import STUDENTS, SubmissionRepository

REPO = None
STYLE = """body{margin:0;background:#f2f5f7;color:#172b3a;font:16px/1.55 system-ui}header{background:#132e40;color:white;padding:28px 6%}main{max-width:1150px;margin:30px auto;padding:0 24px}h1{margin:0}h2{font-size:22px}a{color:#087674}nav a{color:#b9eeee;margin-right:22px}section,.card{background:white;border:1px solid #dce4e8;border-radius:12px;padding:22px;margin-bottom:22px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{font-size:34px;font-weight:650}table{border-collapse:collapse;width:100%;text-align:left}td,th{padding:10px;border-bottom:1px solid #e4e9ec;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;color:#087674}textarea{width:98%;height:100px;font:14px monospace}button{background:#087674;color:white;border:0;border-radius:6px;padding:12px 20px;cursor:pointer}select{padding:9px}small,.muted{color:#526672}.badge{background:#fff0d4;color:#744800;padding:3px 10px;border-radius:20px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}@media(max-width:760px){.cards,.grid{grid-template-columns:1fr}td,th{padding:6px}}"""


def esc(value):
    return html.escape(str(value))


def pretty(value):
    return "<pre>" + esc(json.dumps(value, indent=2)) + "</pre>"


def table(headers, rows):
    return (
        "<table><thead><tr>"
        + "".join("<th>" + esc(h) + "</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join("<td>" + str(c) + "</td>" for c in row) + "</tr>" for row in rows
        )
        + "</tbody></table>"
    )


def shell(title, body):
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'
        + esc(title)
        + " · SIIP</title><style>"
        + STYLE
        + '</style><header><span class="badge">SYNTHETIC DATA · LOCAL RESEARCH</span><h1>SQL learning observatory</h1><p>PrairieLearn × InstructKG · JOINs and NULL semantics</p><nav><a href="/">Overview</a><a href="/students">Students</a><a href="/graph">Graph review</a><a href="/compare">Feedback lab</a><a href="http://localhost:3000/pl">PrairieLearn</a></nav></header><main>'
        + body
        + "</main></html>"
    )


def overview(repo):
    data = repo.analytics()
    cards = "".join(
        '<div class="card"><div class="metric">' + str(v) + "</div>" + esc(k) + "</div>"
        for k, v in [
            ("Synthetic students", data["student_count"]),
            ("Attempts", data["attempt_count"]),
            ("Correct", data["correct"]),
            ("Needs revision", data["attempt_count"] - data["correct"]),
        ]
    )
    body = (
        '<div class="cards">'
        + cards
        + "</div><section><h2>Question performance</h2>"
        + table(
            ["Question", "Attempts", "Correct"],
            [[esc(q), v["attempts"], v["correct"]] for q, v in data["questions"].items()],
        )
        + "</section>"
    )
    body += (
        '<section><h2>Concepts associated with errors</h2><p class="muted">Candidates inferred from task tags and observed errors. These are not confirmed misconceptions.</p>'
        + table(
            ["Concept", "Associated errors", "Mean heuristic estimate"],
            [
                [esc(c), n, round(data["mean_mastery"].get(c, 0), 3)]
                for c, n in data["associated_error_concepts"].items()
            ],
        )
        + "</section>"
    )
    body += (
        "<section><h2>Source boundaries</h2>"
        + pretty(data["sources"])
        + "<p>PrairieLearn owns its real assessment history. Offline fixture attempts are labeled separately. Import only authorized local sandbox exports. No production data connection is active.</p></section>"
    )
    return shell("Overview", body)


def students(repo, sid=None):
    if sid is None:
        return shell(
            "Students",
            "<section><h2>Synthetic students</h2>"
            + "".join(
                f'<p><a href="/students?id={s}">{s}</a> · {repo.profile(s)["attempt_count"]} attempts</p>'
                for s in STUDENTS
            )
            + "</section>",
        )
    profile = repo.profile(sid)
    body = (
        "<section><h2>"
        + esc(sid)
        + " · synthetic learning history</h2><p>"
        + esc(profile["model"])
        + "</p>"
        + table(
            ["Concept", "Attempts", "Correct", "Estimate", "Prerequisites"],
            [
                [
                    esc(c),
                    p["attempt_count"],
                    p["correct_count"],
                    round(p["mastery_estimate"], 3),
                    esc(", ".join(p["prerequisites"])),
                ]
                for c, p in profile["concepts"].items()
            ],
        )
        + "</section>"
    )
    body += (
        "<section><h2>Attempt trajectory</h2>"
        + table(
            ["Time (UTC)", "Question", "Result", "Observed error", "Source"],
            [
                [
                    esc(a["timestamp"]),
                    esc(a["question_id"]),
                    esc(a["grading"]["status"]),
                    esc(a["diagnosis"]["observed_error"]),
                    esc(a["source"]),
                ]
                for a in profile["history"]
            ],
        )
        + "</section>"
    )
    body += (
        '<section><h2>Add a synthetic attempt</h2><p>This form exercises the shared engine and updates this synthetic profile. Use the PrairieLearn link for actual platform submissions.</p><form method="post" action="/attempt"><input type="hidden" name="student_id" value="'
        + esc(sid)
        + '"><label>Question <select name="question_id">'
        + "".join("<option>" + q + "</option>" for q in QUESTIONS)
        + '</select></label><p><label>SQL query<textarea name="sql" required maxlength="12000"></textarea></label></p><button>Evaluate and update synthetic profile</button></form></section>'
    )
    return shell("Student " + sid, body)


def graph_page():
    existing, provisional = load_graphs()
    synthetic = existing.provenance.get("kind") == "synthetic_contract_fixture"
    source_label = (
        "Original synthetic contract fixture; no real extraction."
        if synthetic
        else "Existing model output covering multiple SQL lectures."
    )
    body = (
        "<section><h2>Graph provenance and review queue</h2><p>"
        + str(len(existing.records))
        + " loaded judgments · "
        + str(len(existing.nodes))
        + " concepts · "
        + str(len(existing.edges(True)))
        + " unique non-null edges.</p><p>"
        + esc(source_label)
        + '</p><p class="badge">All loaded judgments remain unreviewed. Development edges are provisional.</p><p>Direction means source → target. A depends_on B means B is a prerequisite of A. No questionable edge is silently reversed.</p></section>'
    )
    module = existing.evidence(["JOIN_OPERATION", "LEFT_OUTER_JOIN"])
    body += "<section><h2>JOIN module judgments</h2>"
    for record in module:
        body += (
            "<details><summary>"
            + esc(record["source"] + " → " + str(record["relation"]) + " → " + record["target"])
            + " · "
            + esc(record["review_status"])
            + "</summary>"
            + pretty(record)
            + "</details>"
        )
    body += (
        "</section><section><h2>Developer provisional dependencies</h2>"
        + table(
            ["Source", "Relation", "Target"],
            [
                [esc(e["source"]), esc(e["relation"]), esc(e["target"])]
                for e in provisional.edges(True)
            ],
        )
        + "</section>"
    )
    body += "<section><h2>Full loaded judgment inventory</h2>"
    for rec in existing.records:
        body += (
            "<details><summary>"
            + esc(f"{rec['id']} · {rec['source']} → {rec['relation']} → {rec['target']}")
            + "</summary>"
            + pretty(rec)
            + "</details>"
        )
    return shell("Graph review", body + "</section>")


def compare(params):
    qid = params.get("question_id", ["sql_join_02"])[0]
    sql = params.get("sql", [QUESTIONS["sql_join_01"]["reference_sql"]])[0]
    result = grade(qid, sql)
    body = (
        '<section><h2>Feedback comparison lab</h2><p>All three outputs below use deterministic development fallback. Live LLM comparison is pending model resources; these are not inference-quality measurements.</p><form><label>Question <select name="question_id">'
        + "".join(
            "<option " + ("selected" if q == qid else "") + ">" + q + "</option>" for q in QUESTIONS
        )
        + '</select></label><p><label>Submitted SQL<textarea name="sql" maxlength="12000">'
        + esc(sql)
        + '</textarea></label></p><button>Compare contexts</button></form></section><div class="grid">'
    )
    for mode in ["baseline", "rag", "kg"]:
        feedback = generate_feedback(qid, sql, result, mode)
        body += (
            "<section><h2>"
            + mode.upper()
            + "</h2><p>"
            + esc(feedback["feedback_text"])
            + "</p><p>"
            + esc(", ".join(feedback["evidence_references"]))
            + "</p><small>"
            + esc(feedback["inference_status"])
            + "</small></section>"
        )
    return shell("Feedback lab", body + "</div>")


def get_jobs_repo():
    jobs_db = os.environ.get("SIIP_FEEDBACK_JOBS_DB") or str(
        ROOT / "artifacts/jobs/feedback_jobs.sqlite3"
    )
    return FeedbackJobRepository(jobs_db)


def authenticate_feedback_request(headers, params, job_id):
    """
    Authenticate caller using HMAC signed ticket or synthetic session token.
    Returns (student_id, error_tuple) where error_tuple is (status_code, error_dict) if auth fails.
    """
    # 1. Try signed ticket (?ticket=... or X-Feedback-Ticket header)
    ticket = params.get("ticket", [None])[0] or headers.get("X-Feedback-Ticket")
    if ticket:
        auth_student = verify_signed_ticket(ticket, job_id=job_id)
        if auth_student:
            return auth_student, None
        return None, (401, {"error": "Invalid, expired, or mismatched feedback ticket."})

    # 2. Try session token (Authorization: Bearer <token> or X-Synthetic-Session)
    auth_header = headers.get("Authorization", "")
    session_token = None
    if auth_header.startswith("Bearer "):
        session_token = auth_header[7:].strip()
    elif headers.get("X-Synthetic-Session"):
        session_token = headers.get("X-Synthetic-Session").strip()

    if session_token:
        auth_student = verify_signed_session_token(session_token)
        if auth_student:
            return auth_student, None
        return None, (401, {"error": "Invalid or expired session token."})

    # 3. Neither ticket nor session token provided. Never accept unverified student_id!
    return None, (
        401,
        {
            "error": (
                "Authentication required. Access requires a signed feedback ticket (?ticket=...) "
                "or a valid synthetic session token (Authorization: Bearer <token>). "
                "Production PrairieLearn/SSO authentication remains an institutional requirement."
            )
        },
    )


def feedback_page(job_id, headers, params):
    if not job_id:
        return shell(
            "Feedback delivery",
            "<section><h2>Learner feedback delivery</h2>"
            "<p class='muted'>Access to AI feedback requires a signed ticket generated upon assessment grading.</p>"
            "<p>Please access feedback via the link provided in your PrairieLearn grading receipt.</p></section>",
        ), 200

    repo = get_jobs_repo()
    job = repo.get(job_id)
    if not job:
        return shell(
            "Feedback not found",
            f"<section><h2>Feedback not found</h2><p>No feedback record was found for job <code>{esc(job_id)}</code>.</p></section>",
        ), 404

    auth_student, auth_error = authenticate_feedback_request(headers, params, job_id)
    if auth_error:
        code, err_data = auth_error
        return shell(
            "Authentication required",
            f"<section><h2>401 Unauthorized</h2><p>{esc(err_data['error'])}</p></section>",
        ), code

    if job.student_id != auth_student:
        return shell(
            "Access denied",
            "<section><h2 style='color:#991b1b;'>403 Forbidden: Access Denied</h2>"
            "<p>Access Denied: You do not have permission to view feedback for this job.</p></section>",
        ), 403

    learner_view = job.to_learner_dict()
    status = learner_view["status"]
    status_badge_color = {
        "completed": "#2e7d32",
        "processing": "#f57c00",
        "pending": "#1976d2",
        "failed": "#d32f2f",
    }.get(status, "#555")

    body = f"""
    <section>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2>Personalized AI feedback</h2>
        <div>
          <span class="badge" style="background:#e0f2fe;color:#0369a1;">Learner: {esc(auth_student)}</span>
          <span class="badge" style="background:{status_badge_color};color:white;margin-left:8px;">{esc(status.upper())}</span>
        </div>
      </div>
      <p><strong>Question:</strong> {esc(learner_view["question_id"])} &middot; <strong>Job ID:</strong> <code>{esc(learner_view["job_id"])}</code></p>
      <h3>Submitted SQL</h3>
      <pre style="background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0;">{esc(learner_view["submitted_sql"])}</pre>
      <p><strong>Deterministic grading:</strong> Score: {learner_view["grading"].get("score")} &middot; Status: {esc(learner_view["grading"].get("status"))} &middot; Observation: {esc(learner_view["grading"].get("observation"))}</p>
    </section>
    """

    if status == "completed" and learner_view.get("feedback"):
        fb = learner_view["feedback"]
        hist_note = ""
        if fb.get("personalized"):
            hist_note = f"<p><small class='badge' style='background:#e8f5e9;color:#1b5e20;'>Historical personalization: Active ({esc(fb.get('history_provenance', 'prior_submissions'))})</small></p>"
        else:
            hist_note = "<p><small class='badge' style='background:#f3f4f6;color:#374151;'>Historical personalization: None (first attempt or no prior history)</small></p>"

        body += f"""
        <section style="border-left:4px solid #087674;">
          <h3>Pedagogical guidance</h3>
          {hist_note}
          <p style="font-size:17px;line-height:1.6;">{esc(fb.get("feedback_text", "No guidance generated."))}</p>
          <h4>Possible concept gaps</h4>
          <p>{esc(", ".join(fb.get("candidate_concepts", [])) or "None identified")}</p>
          <h4>Lecture grounding references</h4>
          <p>{esc(", ".join(fb.get("evidence_references", [])) or "None cited")}</p>
        </section>
        """
        if learner_view.get("provenance"):
            prov = learner_view["provenance"]
            body += f"""
            <section>
              <h3>Provenance & evaluation grounding</h3>
              {
                table(
                    ["Property", "Value"],
                    [
                        ["Model identifier", esc(prov.get("model_identifier") or "unknown")],
                        ["Prompt version", esc(prov.get("prompt_version") or "unknown")],
                        ["Knowledge graph digest", esc(prov.get("graph_version") or "unknown")],
                        [
                            "Inference latency",
                            f"{prov['latency_ms']:.2f} ms" if prov.get("latency_ms") else "N/A",
                        ],
                        ["Created timestamp", esc(learner_view["created_at"])],
                        ["Completed timestamp", esc(learner_view.get("completed_at") or "N/A")],
                    ],
                )
            }
            </section>
            """
    elif status in ("pending", "processing"):
        body += f"""
        <section style="background:#fffbeb;border:1px solid #fde68a;">
          <h3>Inference in progress</h3>
          <p>This feedback job is currently being processed by the background GPU worker.</p>
          <p>Status: <strong>{esc(status)}</strong> &middot; Created at: {esc(learner_view["created_at"])}</p>
          <p><small>Refresh this page or check back shortly to view the grounded AI explanation.</small></p>
        </section>
        """
    elif status == "failed":
        body += f"""
        <section style="background:#fef2f2;border:1px solid #fecaca;">
          <h3 style="color:#991b1b;">Inference failure</h3>
          <p>{esc(learner_view.get("error") or "Feedback generation unavailable.")}</p>
          <p>Deterministic baseline feedback was safely retained in PrairieLearn.</p>
        </section>
        """

    return shell(f"Feedback · {auth_student}", body), 200


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # BaseHTTPRequestHandler logs raw request URLs; query parameters can contain SQL.
        return

    def send(self, body, status=200, content="text/html; charset=utf-8"):
        event(
            "http_request",
            correlation_id=self.correlation,
            method=self.command,
            path=urlparse(self.path).path,
            http_status=status,
        )
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.send_header("Content-Type", content)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", self.correlation)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(encoded)

    def trusted(self):
        self.correlation = str(uuid.uuid4())
        allowed = {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
            f"host.docker.internal:{self.server.server_port}",
            "127.0.0.1",
            "localhost",
            "host.docker.internal",
        }
        if self.headers.get("Host") not in allowed:
            self.send("Forbidden host", 403)
            return False
        return True

    def do_GET(self):
        if not self.trusted():
            return
        parsed = urlparse(self.path)
        if len(self.path) > 20000:
            return self.send("Request too large", 414)
        params = parse_qs(parsed.query)
        repo = self.server.repository
        try:
            if parsed.path == "/":
                self.send(overview(repo))
            elif parsed.path == "/students":
                self.send(students(repo, params.get("id", [None])[0]))
            elif parsed.path == "/graph":
                self.send(graph_page())
            elif parsed.path == "/compare":
                self.send(compare(params))
            elif parsed.path == "/feedback":
                job_id = params.get("job_id", [None])[0]
                html_body, code = feedback_page(job_id, self.headers, params)
                self.send(html_body, code)
            elif parsed.path == "/api/feedback":
                job_id = params.get("job_id", [None])[0]
                if not job_id:
                    self.send(
                        json.dumps({"error": "Missing job_id"}),
                        400,
                        content="application/json",
                    )
                    return
                repo_jobs = get_jobs_repo()
                job = repo_jobs.get(job_id)
                if not job:
                    self.send(
                        json.dumps({"error": "Feedback job not found"}),
                        404,
                        content="application/json",
                    )
                    return
                auth_student, auth_error = authenticate_feedback_request(
                    self.headers, params, job_id
                )
                if auth_error:
                    code, err_data = auth_error
                    self.send(
                        json.dumps(err_data),
                        code,
                        content="application/json",
                    )
                    return
                if job.student_id != auth_student:
                    self.send(
                        json.dumps(
                            {
                                "error": "Forbidden: You do not have permission to view this feedback job."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                self.send(json.dumps(job.to_learner_dict()), 200, content="application/json")
            elif parsed.path == "/api/analytics":
                self.send(json.dumps(repo.analytics()), content="application/json")
            elif parsed.path == "/health":
                with closing(repo.connect()) as db:
                    db.execute("SELECT 1").fetchone()
                try:
                    existing, _ = load_graphs()
                    graph_status = (
                        "available" if existing.records and not existing.errors else "degraded"
                    )
                except (OSError, ValueError, TypeError):
                    graph_status = "unavailable"
                self.send(
                    json.dumps(
                        {
                            "status": "ok",
                            "service": "siip-analytics",
                            "synthetic": True,
                            "storage": "available",
                            "kg": graph_status,
                            "llm": "not_probed",
                            "provider": os.getenv("SIIP_FEEDBACK_PROVIDER", "deterministic"),
                        }
                    ),
                    content="application/json",
                )
            else:
                self.send("Not found", 404)
        except (ValueError, KeyError):
            self.send("Invalid input", 400)
        except Exception as exc:
            event("request_failed", correlation_id=self.correlation, error_type=type(exc).__name__)
            self.send("Service unavailable; see correlation ID", 503)

    def do_POST(self):
        if not self.trusted():
            return
        allowed = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
            f"http://host.docker.internal:{self.server.server_port}",
        }
        origin = self.headers.get("Origin")
        if origin is not None and origin not in allowed:
            return self.send("Forbidden origin", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.send("Forbidden origin", 403)
        if self.path not in {
            "/attempt",
            "/api/attempts",
            "/api/auth/synthetic-session",
            "/api/queue/enqueue",
            "/api/queue/reconcile",
        }:
            return self.send("Not found", 404)
        if "Content-Length" not in self.headers:
            return self.send("Content length required", 411)
        try:
            size = int(self.headers["Content-Length"])
            if size < 0:
                raise ValueError("Negative length")
            if size > 16000:
                return self.send("Request too large", 413)
            if self.headers.get("Transfer-Encoding"):
                return self.send("Unsupported transfer encoding", 400)
            self.connection.settimeout(5)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Incomplete payload")
            text = raw.decode("utf-8")

            # Route 1: Synthetic local authentication session endpoint
            if self.path == "/api/auth/synthetic-session":
                is_dev_mode = (
                    os.environ.get("SIIP_ENV") == "development"
                    or os.environ.get("SIIP_ALLOW_SYNTHETIC_AUTH") == "1"
                )
                if not is_dev_mode:
                    self.send(
                        json.dumps(
                            {
                                "error": "Synthetic session issuance is disabled outside isolated development mode. "
                                "Institutional SSO authentication required."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                client_ip = self.client_address[0]
                is_loopback = client_ip in ("127.0.0.1", "::1", "localhost")
                if not is_loopback and not verify_service_request(self.headers):
                    self.send(
                        json.dumps(
                            {
                                "error": "Synthetic session issuance is restricted to local loopback or authorized service callers."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                if self.headers.get_content_type() != "application/json":
                    return self.send("JSON required", 415)
                payload = json.loads(text)
                sid = payload.get("student_id")
                if not sid or sid not in STUDENTS:
                    self.send(
                        json.dumps({"error": "Invalid or unknown synthetic student principal"}),
                        400,
                        content="application/json",
                    )
                    return
                token = create_signed_session_token(sid)
                self.send(
                    json.dumps(
                        {
                            "token": token,
                            "student_id": sid,
                            "token_type": "Bearer",  # nosec B105
                            "expires_in": 86400,
                        }
                    ),
                    200,
                    content="application/json",
                )
                return

            # Route 2: Durable host-owned queue enqueue endpoint
            if self.path == "/api/queue/enqueue":
                if not verify_service_request(self.headers):
                    self.send(
                        json.dumps(
                            {"error": "Service authentication required for queue mutations."}
                        ),
                        401,
                        content="application/json",
                    )
                    return
                if self.headers.get_content_type() != "application/json":
                    return self.send("JSON required", 415)
                payload = json.loads(text)
                sid = payload.get("student_id")
                qid = payload.get("question_id")
                sql = payload.get("submitted_sql", "")
                grading = payload.get("grading")
                mode = payload.get("feedback_mode", "kg")
                attempt_id = payload.get("attempt_id")
                attempt_kind = payload.get(
                    "attempt_kind", "authoritative" if attempt_id else "provisional"
                )

                if not sid or sid not in STUDENTS:
                    self.send(
                        json.dumps({"error": "Invalid student principal"}),
                        400,
                        content="application/json",
                    )
                    return
                if not qid or qid not in QUESTIONS:
                    self.send(
                        json.dumps({"error": "Invalid question_id"}),
                        400,
                        content="application/json",
                    )
                    return
                if not isinstance(grading, dict):
                    self.send(
                        json.dumps({"error": "Invalid grading payload"}),
                        400,
                        content="application/json",
                    )
                    return

                if not attempt_id:
                    event_id = uuid.uuid4().hex[:12]
                    attempt_id = f"prov-{sid}-{qid}-{event_id}"
                    attempt_kind = "provisional"

                repo_jobs = get_jobs_repo()
                try:
                    job = repo_jobs.enqueue(
                        attempt_id=attempt_id,
                        student_id=sid,
                        question_id=qid,
                        submitted_sql=sql,
                        grading=grading,
                        mode=mode,
                        attempt_kind=attempt_kind,
                    )
                except JobQueueFullError as exc:
                    self.send(
                        json.dumps({"error": "Queue full", "detail": str(exc)}),
                        503,
                        content="application/json",
                    )
                    return
                except AttemptConflictError as exc:
                    self.send(
                        json.dumps({"error": "Attempt conflict", "detail": str(exc)}),
                        409,
                        content="application/json",
                    )
                    return

                ticket = create_signed_ticket(sid, job.job_id)
                self.send(
                    json.dumps(
                        {
                            "job_id": job.job_id,
                            "attempt_id": job.attempt_id,
                            "status": job.status,
                            "ticket": ticket,
                            "feedback_url": f"/feedback?job_id={job.job_id}&ticket={ticket}",
                        }
                    ),
                    201 if job.version == 0 else 200,
                    content="application/json",
                )
                return

            # Route 3: Reconcile provisional attempt to authoritative ID
            if self.path == "/api/queue/reconcile":
                if not verify_service_request(self.headers):
                    self.send(
                        json.dumps(
                            {"error": "Service authentication required for queue reconciliation."}
                        ),
                        401,
                        content="application/json",
                    )
                    return
                if self.headers.get_content_type() != "application/json":
                    return self.send("JSON required", 415)
                payload = json.loads(text)
                prov_id = payload.get("provisional_attempt_id")
                auth_id = payload.get("authoritative_attempt_id")
                sid = payload.get("student_id")
                qid = payload.get("question_id")
                sub_time = payload.get("submission_time")
                if not prov_id or not auth_id:
                    self.send(
                        json.dumps({"error": "Missing attempt IDs"}),
                        400,
                        content="application/json",
                    )
                    return
                repo_jobs = get_jobs_repo()
                try:
                    reconciled = repo_jobs.reconcile(
                        prov_id,
                        auth_id,
                        student_id=sid,
                        question_id=qid,
                        submission_time=sub_time,
                    )
                except AttemptConflictError as exc:
                    self.send(
                        json.dumps(
                            {"error": f"Reconciliation conflict: {str(exc)}", "detail": str(exc)}
                        ),
                        409,
                        content="application/json",
                    )
                    return
                if not reconciled:
                    self.send(
                        json.dumps({"error": "Provisional attempt not found"}),
                        404,
                        content="application/json",
                    )
                    return
                self.send(
                    json.dumps(
                        {
                            "status": "reconciled",
                            "job_id": reconciled.job_id,
                            "attempt_id": reconciled.attempt_id,
                            "attempt_kind": reconciled.attempt_kind,
                            "reconciled_from": reconciled.reconciled_from,
                        }
                    ),
                    200,
                    content="application/json",
                )
                return

            # Route 4: Analytics submission attempts
            if self.path == "/api/attempts":
                if self.headers.get_content_type() != "application/json":
                    return self.send("JSON required", 415)
                payload = json.loads(text)
                if not isinstance(payload, dict) or set(payload) != {
                    "student_id",
                    "question_id",
                    "sql",
                }:
                    raise ValueError("Invalid schema")
            else:
                params = parse_qs(text, strict_parsing=True)
                if set(params) != {"student_id", "question_id", "sql"} or any(
                    len(v) != 1 for v in params.values()
                ):
                    raise ValueError("Invalid form")
                payload = {key: value[0] for key, value in params.items()}
            key = self.headers.get("Idempotency-Key")
            if key is not None and (
                not 1 <= len(key) <= 100 or not all(c.isalnum() or c in "-_" for c in key)
            ):
                raise ValueError("Invalid idempotency key")
            aid = "http-" + key if key else "demo-" + str(uuid.uuid4())
            repo = self.server.repository
            with self.server.ingestion_lock:
                previous = (
                    next((a for a in repo.records() if a["attempt_id"] == aid), None)
                    if key
                    else None
                )
                timestamp = (
                    previous["timestamp"] if previous else datetime.now(timezone.utc).isoformat()
                )
                result = repo.process(
                    {
                        "student_id": payload["student_id"],
                        "question_id": payload["question_id"],
                        "submitted_sql": payload["sql"],
                        "timestamp": timestamp,
                        "attempt_id": aid,
                        "source": "synthetic_fixture",
                    }
                )
            if self.path == "/api/attempts":
                self.send(
                    json.dumps(
                        {
                            "attempt_id": result["attempt_id"],
                            "grading_status": result["grading"]["status"],
                            "score": result["grading"]["score"],
                            "feedback_status": result["feedback"]["inference_status"],
                            "persistence_status": "committed",
                            "correlation_id": self.correlation,
                        }
                    ),
                    201,
                    content="application/json",
                )
            else:
                sid = payload["student_id"]
                self.send(
                    shell(
                        "Attempt recorded",
                        "<section><h2>"
                        + esc(result["grading"]["status"])
                        + "</h2><p>"
                        + esc(result["feedback"]["feedback_text"])
                        + '</p><p><a href="/students?id='
                        + esc(sid)
                        + '">View updated synthetic profile</a></p></section>',
                    )
                )
        except (UnicodeError, ValueError, KeyError, TypeError):
            self.send("Invalid input", 400)
        except Exception as exc:
            event("request_failed", correlation_id=self.correlation, error_type=type(exc).__name__)
            self.send("Service unavailable; see correlation ID", 503)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, repository, port=8080, host=None):
        self.repository = repository
        self.ingestion_lock = threading.Lock()
        bind_host = host if host is not None else os.environ.get("SIIP_DASHBOARD_HOST", "127.0.0.1")
        super().__init__((bind_host, port), Handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo = SubmissionRepository(
        Path((os.environ.get("SIIP_DB_PATH") or ROOT / "artifacts/synthetic.sqlite3"))
    )
    port = int(os.environ.get("SIIP_DASHBOARD_PORT", "8080"))
    bind_host = os.environ.get("SIIP_DASHBOARD_HOST", "127.0.0.1")
    print(f"Synthetic analytics: http://{bind_host}:{port}", flush=True)
    import signal

    server = DashboardServer(repo, port, host=bind_host)
    signal.signal(
        signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start()
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
