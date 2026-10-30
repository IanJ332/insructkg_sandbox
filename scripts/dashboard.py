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
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
import time

from siip.demo_authoring import LOCAL_PUBLICATION_LABEL, DemoAuthoringRegistry
from siip.demo_kg import SCIENTIFIC_BOUNDARY, DemoKGRepository
from siip.demo_lineage import build_entity_lineage, derive_enriched_events
from siip.demo_observability import DemoObservabilityRepository
from siip.demo_student import DemoStudentJourney
from siip.em_models import EMDimension, EMReviewStatus
from siip.em_repository import EMRepository
from siip.feedback import generate_feedback, load_graphs
from siip.grader import QUESTIONS, grade
from siip.identity import (
    create_signed_session_token,
    create_signed_ticket,
    extract_session_token,
    generate_csrf_token,
    is_instructor_principal,
    is_student_principal,
    synthetic_auth_enabled,
    validate_dashboard_auth,
    verify_csrf_token,
    verify_service_request,
    verify_signed_session_token_role,
    verify_signed_ticket,
)
from siip.jobs import AttemptConflictError, FeedbackJobRepository, JobQueueFullError
from siip.observability import event
from siip.pl_bridge import grade_question
from siip.project_generator import ProjectRepository, generate_personalized_project
from siip.project_models import STUDENT_INTEREST_PROFILES
from siip.recommender import recommend_next_activity
from siip.store import STUDENTS, SubmissionRepository
from siip.survey_instruments import get_evaluation_instruments


class RequestAuth:
    """Central authorization policy evaluator for dashboard endpoints."""

    def __init__(self, handler: BaseHTTPRequestHandler):
        self.handler = handler
        self.headers = handler.headers
        self.raw_token = extract_session_token(self.headers)
        self.principal: str | None = None
        self.role: str | None = None
        self.is_valid = False
        self.is_service = verify_service_request(self.headers)
        self.csrf_token: str | None = None

        if self.raw_token and synthetic_auth_enabled():
            p, r = verify_signed_session_token_role(self.raw_token)
            if p and r:
                if r == "student" and (is_student_principal(p) or p in STUDENTS):
                    self.principal = p
                    self.role = "student"
                    self.is_valid = True
                elif r == "instructor" and is_instructor_principal(p):
                    self.principal = p
                    self.role = "instructor"
                    self.is_valid = True
                if self.is_valid:
                    self.csrf_token = generate_csrf_token(self.raw_token)

    @property
    def has_credential(self) -> bool:
        return bool(self.raw_token or self.is_service)

    def require_instructor(self) -> tuple[bool, int, str]:
        if self.is_service:
            return True, 200, ""
        if not self.raw_token:
            return False, 401, "Authentication required. Missing session credentials."
        if not self.is_valid:
            return False, 401, "Invalid or expired session credentials."
        if self.role == "student":
            return False, 403, "Forbidden: Synthetic students cannot perform instructor actions."
        if self.role == "instructor":
            return True, 200, ""
        return False, 403, "Forbidden: Instructor authorization required."

    def require_student_or_instructor(
        self, target_student_id: str | None = None
    ) -> tuple[bool, int, str]:
        if self.is_service:
            return True, 200, ""
        if not self.raw_token:
            return False, 401, "Authentication required. Missing session credentials."
        if not self.is_valid:
            return False, 401, "Invalid or expired session credentials."
        if self.role == "instructor":
            return True, 200, ""
        if self.role == "student":
            if target_student_id and self.principal != target_student_id:
                return (
                    False,
                    403,
                    f"Forbidden: Student {self.principal} cannot access records for {target_student_id}.",
                )
            return True, 200, ""
        return False, 403, "Forbidden: Role not authorized."

    def verify_csrf(self, body_params: dict) -> tuple[bool, int, str]:
        supplied_csrf = (
            body_params.get("csrf_token", [None])[0]
            if isinstance(body_params.get("csrf_token"), list)
            else body_params.get("csrf_token")
        )
        if not supplied_csrf:
            supplied_csrf = self.headers.get("X-CSRF-Token")
        if (
            not self.csrf_token
            or not supplied_csrf
            or not verify_csrf_token(self.raw_token or "", str(supplied_csrf))
        ):
            return False, 403, "Forbidden: Invalid or missing CSRF token."
        return True, 200, ""


REPO = None
DEMO_AUTHORING = None
DEMO_KG = None
DEMO_OBSERVABILITY = None
STYLE = """body{margin:0;background:#f2f5f7;color:#172b3a;font:16px/1.55 system-ui}header{background:#132e40;color:white;padding:28px 6%}main{max-width:1150px;margin:30px auto;padding:0 24px}h1{margin:0}h2{font-size:22px}a{color:#087674}nav a{color:#b9eeee;margin-right:22px}section,.card{background:white;border:1px solid #dce4e8;border-radius:12px;padding:22px;margin-bottom:22px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{font-size:34px;font-weight:650}table{border-collapse:collapse;width:100%;text-align:left}td,th{padding:10px;border-bottom:1px solid #e4e9ec;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;color:#087674}textarea{width:98%;height:100px;font:14px monospace}button{background:#087674;color:white;border:0;border-radius:6px;padding:12px 20px;cursor:pointer}select{padding:9px}small,.muted{color:#526672}.badge{background:#fff0d4;color:#744800;padding:3px 10px;border-radius:20px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}@media(max-width:760px){.cards,.grid{grid-template-columns:1fr}td,th{padding:6px}}"""


def get_demo_state_dir():
    return Path(os.environ.get("SIIP_DEMO_STATE_DIR") or ROOT / "artifacts/demo_state")


def get_demo_authoring():
    global DEMO_AUTHORING
    if DEMO_AUTHORING is None:
        DEMO_AUTHORING = DemoAuthoringRegistry(get_demo_state_dir() / "authoring")
    return DEMO_AUTHORING


def get_demo_kg():
    global DEMO_KG
    if DEMO_KG is None:
        DEMO_KG = DemoKGRepository(get_demo_state_dir() / "knowledge_graph")
    return DEMO_KG


def get_demo_observability():
    global DEMO_OBSERVABILITY
    if DEMO_OBSERVABILITY is None:
        artifact_dir = Path(
            os.environ.get("SIIP_DEMO_ARTIFACT_DIR") or ROOT / "artifacts/demo_run/timeline"
        )
        DEMO_OBSERVABILITY = DemoObservabilityRepository(artifact_dir)
    return DEMO_OBSERVABILITY


def record_demo_event(
    *, actor_type, actor_id, phase, event_type, entity_id, artifact_path, source_type
):
    return get_demo_observability().record_event(
        actor_type=actor_type,
        actor_id=actor_id,
        phase=phase,
        event_type=event_type,
        entity_id=entity_id,
        correlation_id=os.environ.get("SIIP_DEMO_CORRELATION_ID", "siip-professor-demo"),
        status="completed",
        artifact_path=artifact_path,
        source_type=source_type,
    )


def entity_lineage(repository):
    return build_entity_lineage(
        get_demo_authoring(),
        get_demo_kg(),
        repository,
        get_jobs_repo(),
        get_em_repo(),
        get_project_repo(),
        os.environ.get("SIIP_DEMO_CORRELATION_ID", "siip-professor-demo"),
    )


def learner_project_payload(project):
    payload = project.to_dict()
    for milestone in payload.get("milestones", []):
        milestone.pop("reference_sql", None)
    if project.instructor_approval_status != "APPROVED":
        payload["milestones"] = []
        payload["schema_ddl"] = ""
        payload["learner_notice"] = (
            "Pending Instructor Approval: tasks remain locked until approved."
        )
    return payload


def parse_multipart_upload(content_type, raw):
    """Parse one small local browser upload without trusting client paths."""

    message = BytesParser(policy=email_policy).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode("ascii") + raw
    )
    fields = {}
    file_record = None
    if not message.is_multipart():
        raise ValueError("multipart/form-data required")
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            if file_record is not None or name != "lesson_file":
                raise ValueError("exactly one lesson_file is required")
            file_record = {"filename": Path(filename).name, "content": payload}
        elif name:
            fields[name] = payload.decode("utf-8")
    if file_record is None:
        raise ValueError("lesson_file is required")
    return fields, file_record


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
        + '</style><header><span class="badge">SYNTHETIC DATA · LOCAL RESEARCH</span><h1>SQL learning observatory</h1><p>PrairieLearn × InstructKG · JOINs and NULL semantics</p><nav><a href="/">Overview</a><a href="/authoring">Course authoring</a><a href="/assignments">Assignments</a><a href="/students">Students</a><a href="/em-review">EM review</a><a href="/projects">Projects</a><a href="/timeline">Data lineage</a><a href="/instruments">Instruments</a><a href="/graph">Graph review</a><a href="/compare">Feedback lab</a><a href="/practice">Practice</a><a href="/login">Demo login</a><a href="http://localhost:3000/pl">PrairieLearn</a></nav></header><main>'
        + body
        + "</main></html>"
    )


def login_page(auth=None, message=None, redirect_url="/"):
    error_banner = (
        f'<div style="background:#fee2e2;border-left:4px solid #dc2626;padding:12px;margin-bottom:16px;color:#991b1b;">{esc(message)}</div>'
        if message
        else ""
    )
    current_status = ""
    if auth and auth.is_valid:
        current_status = f"""
        <div style="background:#dcfce7;border-left:4px solid #16a34a;padding:12px;margin-bottom:16px;color:#166534;">
          Logged in as <strong>{esc(auth.principal)}</strong> (Role: <strong>{esc(auth.role)}</strong>).
          <form method="POST" action="/logout" style="margin-top:8px;">
            <button type="submit" style="background:#dc2626;padding:6px 12px;font-size:13px;">Log Out</button>
          </form>
        </div>
        """

    body = f"""
    <section style="max-width:540px;margin:40px auto;">
      <span class="badge" style="background:#fef3c7;color:#92400e;margin-bottom:12px;display:inline-block;">
        SYNTHETIC LOCAL DEMO AUTHENTICATION ONLY
      </span>
      <h2>Research Demo Login</h2>
      <p class="muted">
        Choose a synthetic principal to simulate local interactive flows; this session mechanism is strictly isolated within the demonstration environment.
      </p>
      {error_banner}
      {current_status}
      <form method="POST" action="/login">
        <input type="hidden" name="redirect" value="{esc(redirect_url)}">
        <div style="margin-bottom:14px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;">Select Synthetic Principal:</label>
          <select name="principal" style="width:100%;font-size:15px;padding:8px;">
            <optgroup label="Course Instructors">
              <option value="instructor_alawini">instructor_alawini (Lead PI / Instructor)</option>
              <option value="prof-alawini">prof-alawini (Co-Instructor)</option>
              <option value="instructor-admin">instructor-admin (Administrative Instructor)</option>
            </optgroup>
            <optgroup label="Synthetic Students (Track A)">
              <option value="S001">S001 (Alice · Clinical Healthcare Interest)</option>
              <option value="S002">S002 (Bob · Urban Transit &amp; Logistics Interest)</option>
              <option value="S003">S003 (Carol · Climate Science Interest)</option>
              <option value="S004">S004 (David · Fintech &amp; Fraud Interest)</option>
              <option value="S005">S005 (Eve · Gaming &amp; Interactive Graphics Interest)</option>
            </optgroup>
          </select>
        </div>
        <button type="submit" style="width:100%;padding:10px;font-weight:600;">Sign In to Demo Session</button>
      </form>
    </section>
    """
    return shell("Demo Login", body)


def authoring_page(csrf_token=None, notice=None, course_id=None):
    registry = get_demo_authoring()
    courses = registry.list_courses()
    course_id = course_id or (courses[0]["course_id"] if courses else "intro-relational-databases")
    modules = registry.list_modules(course_id=course_id)
    lessons = registry.list_lessons(course_id=course_id)
    course_options = "".join(
        f'<option value="{esc(item["course_id"])}" {"selected" if item["course_id"] == course_id else ""}>{esc(item["title"])}</option>'
        for item in courses
    )
    module_options = "".join(
        f'<option value="{esc(item["module_id"])}">{esc(item["title"])}</option>'
        for item in modules
    )
    notice_html = (
        f'<div data-testid="authoring-notice" style="background:#dcfce7;border-left:4px solid #16a34a;padding:12px;margin-bottom:16px;">{esc(notice)}</div>'
        if notice
        else ""
    )
    rows = []
    for lesson in lessons:
        rows.append(
            [
                esc(lesson.source_document_id),
                esc(lesson.original_filename),
                lesson.version,
                f"<code>{esc(lesson.sha256)}</code>",
                esc(lesson.processing_status),
                esc(lesson.upload_timestamp_utc),
                f'<a href="/materials?id={esc(lesson.source_document_id)}&version={lesson.version}">Open stored material</a>',
                f'''<form method="POST" action="/api/demo/kg/generate">
                  <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
                  <input type="hidden" name="source_document_id" value="{esc(lesson.source_document_id)}">
                  <input type="hidden" name="version" value="{lesson.version}">
                  <button type="submit">Generate Knowledge Graph</button>
                </form>''',
            ]
        )
    lesson_table = (
        table(
            [
                "Document ID",
                "Filename",
                "Version",
                "SHA-256",
                "Status",
                "Uploaded UTC",
                "Source",
                "Next step",
            ],
            rows,
        )
        if rows
        else '<p class="muted">No lesson has been uploaded in this isolated demo state.</p>'
    )
    body = f"""
    {notice_html}
    <section data-testid="course-authoring">
      <span class="badge">SYNTHETIC COURSE MATERIAL — LOCAL RESEARCH DEMONSTRATION</span>
      <h2>Introduction to Relational Databases — Personalized SQL Learning</h2>
      <p><strong>Module:</strong> SQL JOINs, NULL Semantics, and Real-World Data Analysis</p>
      <p class="muted">Local-only instructor workflow. No institutional course material or real learner data is used.</p>
    </section>
    <section>
      <h2>Course and module management</h2>
      <form method="GET" action="/authoring"><label>Course <select name="course_id">{course_options}</select></label> <button>Select course</button></form>
      <form method="POST" action="/api/demo/courses/create">
        <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
        <label>Course ID <input name="course_id" required></label>
        <label>Title <input name="title" required></label><button>Create course</button>
      </form>
      <form method="POST" action="/api/demo/modules/create">
        <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
        <input type="hidden" name="course_id" value="{esc(course_id)}">
        <label>Module ID <input name="module_id" required></label>
        <label>Title <input name="title" required></label><button>Create module</button>
      </form>
    </section>
    <section>
      <h2>Upload instructor-authored lesson</h2>
      <form method="POST" enctype="multipart/form-data" action="/api/demo/lessons/upload">
        <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
        <input type="hidden" name="course_id" value="{esc(course_id)}">
        <label>Module <select name="module_id" required>{module_options}</select></label><br><br>
        <label>Source document ID <input name="source_document_id" value="lesson-sql-joins" required></label><br><br>
        <label>Lesson document <input data-testid="lesson-file" type="file" name="lesson_file" accept=".md,.txt" required></label><br><br>
        <button data-testid="upload-lesson" type="submit">Upload lesson</button>
      </form>
    </section>
    <section data-testid="lesson-registry">
      <h2>Source registry and provenance</h2>
      {lesson_table}
    </section>
    """
    return shell("Course authoring", body)


def demo_graph_page(graph_id=None, csrf_token=None, notice=None):
    repo = get_demo_kg()
    available = repo.list_graphs()
    if graph_id is None and available:
        graph_id = available[-1]["graph_id"]
    if graph_id is None:
        return shell(
            "Demo knowledge graph",
            '<section><h2>No generated demonstration graph</h2><p><a href="/authoring">Upload a lesson and request extraction first.</a></p></section>',
        )
    graph = repo.retrieve(graph_id)
    notice_html = f'<p class="badge" data-testid="graph-notice">{esc(notice)}</p>' if notice else ""
    nodes = "".join(
        f'<div class="card" data-testid="kg-node"><strong>{esc(node["label"])}</strong><br><code>{esc(node["id"])}</code><br><small>{esc(node["source_document_id"])}</small></div>'
        for node in graph["nodes"]
    )
    edge_rows = []
    for edge in graph["edges"]:
        review = f'''<form method="POST" action="/api/demo/kg/review" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
          <input type="hidden" name="graph_id" value="{esc(graph_id)}">
          <input type="hidden" name="edge_id" value="{esc(edge["edge_id"])}">
          <input name="notes" value="Reviewed for the synthetic professor demonstration" aria-label="Review notes">
          <button name="decision" value="APPROVE" type="submit">Approve</button>
          <button name="decision" value="REJECT" type="submit" style="background:#b42318">Reject</button>
          <button name="decision" value="NEEDS_REVISION" type="submit" style="background:#92400e">Needs revision</button>
        </form>'''
        edge_rows.append(
            [
                f"<code>{esc(edge['source'])}</code> → <strong>{esc(edge['relation'])}</strong> → <code>{esc(edge['target'])}</code>",
                esc(edge["evidence_excerpt"]),
                f"{edge['confidence']:.2f}",
                esc(edge["review_state"]),
                review,
            ]
        )
    versions = repo.list_versions(graph_id)
    body = f"""
    {notice_html}
    <section data-testid="demo-kg-boundary">
      <span class="badge">{esc(graph.get("scientific_boundary", SCIENTIFIC_BOUNDARY))}</span>
      <h2>Candidate concept graph</h2>
      <p>Graph <code>{esc(graph_id)}</code> · source <code>{esc(graph["source_document_id"])}</code> · pipeline <code>{esc(graph["pipeline_version"])}</code></p>
      <p class="muted">Mode: {esc(graph.get("extraction_mode", graph.get("extraction_method", "synthetic_fixture")))}. This local adapter is separate from original InstructKG. Review each evidence-backed directed relation before use.</p>
    </section>
    <section><h2>Extracted candidate concepts</h2><div class="grid">{nodes}</div></section>
    <section data-testid="kg-edges"><h2>Directed relations and source evidence</h2>{table(["Directed edge", "Evidence excerpt", "Confidence", "Review state", "Instructor decision"], edge_rows)}</section>
    <section>
      <h2>Save reviewed graph version</h2>
      <form method="POST" action="/api/demo/kg/save">
        <input type="hidden" name="csrf_token" value="{esc(csrf_token or "")}">
        <input type="hidden" name="graph_id" value="{esc(graph_id)}">
        <button data-testid="save-graph" type="submit">Save approved local graph version</button>
      </form>
      <p>{len(versions)} immutable version(s) saved.</p>
    </section>
    """
    return shell("Demo knowledge graph", body)


def assignments_page(auth, notice=None):
    registry = get_demo_authoring()
    records = registry.list_assignments()
    notice_html = (
        f'<p class="badge" data-testid="assignment-notice">{esc(notice)}</p>' if notice else ""
    )
    rows = []
    for item in records:
        action = ""
        if auth.role == "instructor" and item.publication_status == "DRAFT":
            action = f'''<form method="POST" action="/api/demo/assignments/publish">
              <input type="hidden" name="csrf_token" value="{esc(auth.csrf_token or "")}">
              <input type="hidden" name="assignment_id" value="{esc(item.assignment_id)}">
              <button type="submit">Publish assignment</button>
            </form>'''
        elif item.publication_status == "PUBLISHED_LOCAL_DEMO":
            action = f'<a data-testid="open-published-assignment" href="/practice?id={esc(item.question_ids[0])}&assignment_id={esc(item.assignment_id)}">Open student activity</a>'
        rows.append(
            [
                esc(item.assignment_id),
                esc(", ".join(item.question_ids)),
                esc(", ".join(item.kg_node_ids)),
                esc(item.publication_status),
                esc(item.publication_timestamp_utc or "—"),
                action,
            ]
        )
    if auth.role == "student":
        records = [
            record for record in records if record.publication_status == "PUBLISHED_LOCAL_DEMO"
        ]
        rows = [row for row in rows if row[3] == "PUBLISHED_LOCAL_DEMO"]
    listing = (
        table(
            [
                "Assignment ID",
                "Question",
                "Reviewed KG concepts",
                "Status",
                "Published UTC",
                "Action",
            ],
            rows,
        )
        if rows
        else '<p class="muted">No assignments are available yet.</p>'
    )
    create = ""
    if auth.role == "instructor":
        graphs = get_demo_kg().list_graphs()
        graph_options = "".join(
            f'<option value="{esc(item["graph_id"])}">{esc(item["source_document_id"])} · {esc(item["graph_id"])}</option>'
            for item in graphs
            if get_demo_kg().list_versions(item["graph_id"])
        )
        available_concepts = set()
        for item in graphs:
            versions = get_demo_kg().list_versions(item["graph_id"])
            if versions:
                saved = get_demo_kg().retrieve(item["graph_id"], versions[-1]["version"])
                available_concepts.update(node["id"] for node in saved["nodes"])
        concept_options = "".join(
            f'<label><input type="checkbox" name="kg_node_id" value="{esc(concept)}" {"checked" if concept in {"LEFT_OUTER_JOIN", "NULL_SEMANTICS", "MISSING_MATCHING_ROWS"} else ""}> {esc(concept)}</label> '
            for concept in sorted(available_concepts)
        )
        question_options = "".join(
            f'<option value="{qid}">{esc(QUESTIONS[qid]["title"])}</option>'
            for qid in ["sql_join_04", *[q for q in QUESTIONS if q != "sql_join_04"]]
        )
        create = f'''
        <section data-testid="assignment-authoring">
          <span class="badge">{esc(LOCAL_PUBLICATION_LABEL)}</span>
          <h2>Create assignment from reviewed concepts</h2>
          <form method="POST" action="/api/demo/assignments/create">
            <input type="hidden" name="csrf_token" value="{esc(auth.csrf_token or "")}">
            <label>Reviewed source graph <select name="graph_id" required>{graph_options}</select></label><br><br>
            <label>Assignment ID <input name="assignment_id" value="assignment-left-join-demo" required></label><br><br>
            <label>SQL exercise <select name="question_id">{question_options}</select></label>
            <fieldset><legend>Reviewed target concepts</legend>
              {concept_options}
            </fieldset><br>
            <details><summary>Optional instructor-reviewed concept mapping</summary>
              <p>Use only when the source supports an equivalence for this assignment.</p>
              <label>Graph concept ID <input name="mapping_source"></label>
              <label>Question concept tag <input name="mapping_target"></label>
              <label>Evidence and review notes <textarea name="mapping_notes"></textarea></label>
            </details><br>
            <button data-testid="create-assignment" type="submit">Create local assignment draft</button>
          </form>
        </section>'''
    body = f"""
    {notice_html}
    <section><h2>Introduction to Relational Databases — Personalized SQL Learning</h2><p><strong>Assignment:</strong> Find All Departments, Including Those Without Employees</p><p class="muted">Preview: use the tested department-headcount activity. The deterministic grader expects a LEFT OUTER JOIN and retains departments with zero employees.</p></section>
    {create}
    <section data-testid="assignment-registry"><h2>{"Course assignments" if auth.role == "instructor" else "Published learning activities"}</h2>{listing}</section>
    """
    return shell("Assignments", body)


def overview(repo):
    assignments = get_demo_authoring().list_assignments()
    records = repo.records()
    assignment_rows = []
    for assignment in assignments:
        attempts = [
            record for record in records if record.get("assessment_id") == assignment.assignment_id
        ]
        assignment_rows.append(
            [
                esc(assignment.assignment_id),
                esc(assignment.publication_status),
                len(attempts),
                sum(record["grading"].get("score", 0) for record in attempts),
            ]
        )
    error_groups = {}
    for record in records:
        if record["grading"].get("score") == 0:
            for concept in record.get("concepts", []):
                error_groups.setdefault(concept, []).append(record)
    ambiguity_rows = []
    for concept, evidence in error_groups.items():
        learners = {record["student_id"] for record in evidence}
        if len(learners) >= 2:
            ambiguity_rows.append(
                [
                    esc(concept),
                    "CANDIDATE_INSTRUCTIONAL_AMBIGUITY",
                    len(learners),
                    "<br>".join(
                        f'<a href="/students?id={esc(record["student_id"])}">{esc(record["attempt_id"])}</a>'
                        for record in evidence
                    ),
                ]
            )
    authoring_summary = (
        "<section><h2>Assignment activity and feedback status</h2>"
        + table(["Assignment", "Publication", "Attempts", "Correct outcomes"], assignment_rows)
        + f"<p>Durable feedback jobs: {pretty(get_jobs_repo().stats())}</p></section>"
    )
    ambiguity_summary = (
        "<section><h2>Candidate curriculum ambiguities</h2><p>Shared error patterns are candidates for instructor review. They do not establish that instructional material is defective.</p>"
        + (
            table(
                ["Concept", "Candidate", "Distinct learners", "Persisted attempt evidence"],
                ambiguity_rows,
            )
            if ambiguity_rows
            else "<p>No shared error pattern across two learners is currently supported.</p>"
        )
        + "</section>"
    )
    data = repo.analytics()
    em_repo = get_em_repo()
    all_evidence = em_repo.list_all_evidence()
    accepted_em = sum(1 for e in all_evidence if e.review_status == EMReviewStatus.ACCEPTED)

    proj_repo = get_project_repo()
    all_projects = proj_repo.list_all_projects()
    approved_proj = sum(1 for p in all_projects if p.instructor_approval_status == "APPROVED")

    cards = "".join(
        '<div class="card"><div class="metric">' + str(v) + "</div>" + esc(k) + "</div>"
        for k, v in [
            ("Synthetic students", data["student_count"]),
            ("Submissions", data["attempt_count"]),
            ("EM reflections", f"{len(all_evidence)} ({accepted_em} accepted)"),
            ("Dynamic projects", f"{len(all_projects)} ({approved_proj} approved)"),
        ]
    )

    # Bottlenecks analysis
    bottlenecks = [
        [
            esc(c),
            n,
            round(data["mean_mastery"].get(c, 0), 3),
            (
                "<span class='badge' style='background:#fee2e2;color:#991b1b;'>High Friction</span>"
                if data["mean_mastery"].get(c, 0) < 0.60
                else "<span class='badge' style='background:#dcfce7;color:#166534;'>Progressing</span>"
            ),
        ]
        for c, n in data["associated_error_concepts"].items()
    ]
    bottleneck_table = (
        table(
            [
                "Relational Concept",
                "Associated Errors",
                "Cohort Mean Mastery",
                "Curricular Status",
            ],
            bottlenecks,
        )
        if bottlenecks
        else "<p class='muted'>No error associations recorded yet.</p>"
    )

    body = f"""
    <div class="cards">{cards}</div>
    {authoring_summary}
    {ambiguity_summary}
    <section>
      <h2>Curricular Concept Bottlenecks &amp; Cohort Mastery</h2>
      <p class="muted">Continuous diagnostic tracking of concept gaps across synthetic cohort. Concepts with mean mastery below 0.60 trigger adaptive remediation recommendations.</p>
      {bottleneck_table}
    </section>
    <section>
      <h2>Question Performance</h2>
      {table(["Question", "Attempts", "Correct"], [[esc(q), v["attempts"], v["correct"]] for q, v in data["questions"].items()])}
    </section>
    <section>
      <h2>Multi-Stakeholder Research Framework</h2>
      <div style="display:flex;gap:12px;align-items:center;">
        <a href="/instruments" style="background:#087674;color:white;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600;">View Research Survey &amp; Review Rubrics &rarr;</a>
        <a href="/api/cohort-analytics" target="_blank" style="background:#132e40;color:white;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600;">Export Cohort Analytics JSON &rarr;</a>
      </div>
    </section>
    <section>
      <h2>Source Boundaries</h2>
      {pretty(data["sources"])}
      <p>PrairieLearn owns its real assessment history. Offline fixture attempts are labeled separately. Import only authorized local sandbox exports. No production data connection is active.</p>
    </section>
    """
    return shell("Overview", body)


def instruments_page():
    inst = get_evaluation_instruments()
    survey = inst["student_perception_survey"]
    rubric = inst["instructor_review_rubric"]
    protocol = inst["blind_review_protocol"]

    survey_rows = [
        [
            esc(q["question_id"]),
            esc(q["category"]),
            esc(q["prompt"]),
            f"{esc(q['min_label'])} (1) &harr; {esc(q['max_label'])} (5)",
        ]
        for q in survey
    ]
    survey_table = table(
        ["ID", "Dimension", "Survey Prompt (5-Point Likert)", "Scale Anchors"],
        survey_rows,
    )

    rubric_rows = [
        [
            f"<strong>{esc(r['name'])}</strong><br><small class='muted'>{esc(r['description'])}</small>",
            f"{int(r['weight'] * 100)}%",
            "<ul style='margin:0;padding-left:18px;font-size:13px;'>"
            + "".join(
                f"<li><strong>Score {lvl}:</strong> {esc(desc)}</li>"
                for lvl, desc in sorted(r["scoring_levels"].items())
            )
            + "</ul>",
        ]
        for r in rubric
    ]
    rubric_table = table(["Rubric Criterion", "Weight", "Scoring Levels (1–3)"], rubric_rows)

    tasks_html = "".join(f"<li>{esc(t)}</li>" for t in protocol["evaluation_tasks"])

    body = f"""
    <section>
      <h2>Multi-Stakeholder Research Evaluation Instruments</h2>
      <p class="muted">Draft evaluation instruments covering student perceptions, instructor feedback quality, and blinded comparisons. Psychometric validation and authorized human-subject evaluation remain future work.</p>

      <h3>1. Student Perception &amp; Affective Survey</h3>
      <p>Administered following completion of the assessment and optional reflection activity.</p>
      {survey_table}

      <h3>2. Instructor Pedagogical &amp; Alignment Rubric</h3>
      <p>Used by course instructors and pedagogical domain experts to audit generated explanations and projects.</p>
      {rubric_table}

      <h3>3. Triple-Blinded Evaluation Protocol</h3>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;">
        <p><strong>Protocol Name:</strong> {esc(protocol["protocol_name"])} &middot; <strong>Version:</strong> {esc(protocol["version"])}</p>
        <p><strong>Blinding Mechanism:</strong> {esc(protocol["blinding_procedure"])}</p>
        <h4>Evaluation Tasks:</h4>
        <ol>{tasks_html}</ol>
      </div>
      <p style="margin-top:16px;"><a href="/api/instruments" target="_blank">Export JSON Instruments Specification &rarr;</a></p>
    </section>
    """
    return shell("Research Instruments", body)


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

    em_repo = get_em_repo()
    em_summary = em_repo.student_em_summary(sid)
    em_status_badge = (
        '<span class="badge" style="background:#fee2e2;color:#991b1b;">INSUFFICIENT_EVIDENCE</span>'
        if em_summary["has_insufficient_evidence"]
        else '<span class="badge" style="background:#dcfce7;color:#166534;">OBSERVED_EVIDENCE_RECORDED</span>'
    )
    em_rows = [
        [
            esc(r["created_at"][:19].replace("T", " ")),
            esc(r["question_id"]),
            f"<strong>{esc(r['dimension'])}</strong>",
            esc(r["evidence_excerpt"][:90] + ("..." if len(r["evidence_excerpt"]) > 90 else "")),
            f"<span class='badge' style='background:{'#dcfce7' if r['review_status'] == 'ACCEPTED' else '#fef3c7'};color:{'#166534' if r['review_status'] == 'ACCEPTED' else '#92400e'};'>{esc(r['review_status'])}</span>",
            esc(r.get("reviewer_id") or "Pending Review"),
        ]
        for r in em_summary["records"]
    ]
    em_table_html = (
        table(["Date (UTC)", "Question", "Dim", "Excerpt", "Status", "Reviewer"], em_rows)
        if em_rows
        else "<p class='muted'>No EM reflection responses recorded for this student yet.</p>"
    )

    body += f"""
    <section>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2>Entrepreneurial Mindset (EM) Behavioral Evidence</h2>
        {em_status_badge}
      </div>
      <p class="muted"><strong>Methodological Boundary:</strong> {esc(em_summary["disclaimer"])}</p>
      <div class="cards" style="margin-bottom:16px;">
        <div class="card"><div class="metric">{em_summary["total_observations"]}</div>Total observations</div>
        <div class="card"><div class="metric">{em_summary["accepted_by_dimension"]["C"]}</div>Curiosity (C) accepted</div>
        <div class="card"><div class="metric">{em_summary["accepted_by_dimension"]["X"]}</div>Connections (X) accepted</div>
        <div class="card"><div class="metric">{em_summary["accepted_by_dimension"]["V"]}</div>Creating Value (V) accepted</div>
      </div>
      {em_table_html}
    </section>
    """

    # Adaptive Next-Activity Recommendation
    rec = recommend_next_activity(sid, profile)
    body += f"""
    <section style="border-left:4px solid #0284c7;background:#f0f9ff;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="color:#0369a1;margin:0 0 6px 0;">Adaptive Next-Activity Recommendation</h2>
        <span class="badge" style="background:#0284c7;color:white;font-weight:600;">{esc(rec["recommended_question_id"])}</span>
      </div>
      <p style="font-size:17px;font-weight:600;margin:6px 0;">{esc(rec["question_title"])}</p>
      <p><strong>Pedagogical Rationale:</strong> {esc(rec["rationale"])}</p>
      <p><strong>Target concepts:</strong> {esc(", ".join(rec["target_concepts"]))} &middot; <strong>Triggered policy:</strong> <code>{esc(rec["rule_id"])}</code></p>
      <div style="display:flex;gap:12px;align-items:center;margin-top:10px;">
        <a href="http://localhost:3000/pl/course_instance/1/assessment/1" style="display:inline-block;background:#087674;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;font-weight:600;">Launch in PrairieLearn &rarr;</a>
      </div>
    </section>
    """

    # Dynamic Personalized Project
    proj_repo = get_project_repo()
    student_projects = proj_repo.list_projects_for_student(sid)
    interest_info = STUDENT_INTEREST_PROFILES.get(sid, {})
    interest_label = interest_info.get("label", "General Relational Applications")
    interest_context = interest_info.get("context", "")

    proj_rows = [
        [
            f"<a href='/projects?id={esc(p.project_id)}'><code>{esc(p.project_id)}</code></a>",
            esc(p.title),
            f"<span class='badge' style='background:{'#dcfce7' if p.instructor_approval_status == 'APPROVED' else '#fef3c7'};color:{'#166534' if p.instructor_approval_status == 'APPROVED' else '#92400e'};'>{esc(p.instructor_approval_status)}</span>",
            f"<a href='/projects?id={esc(p.project_id)}'>View Project Brief &rarr;</a>",
        ]
        for p in student_projects
    ]
    proj_table = (
        table(["Project ID", "Title", "Status", "Action"], proj_rows)
        if proj_rows
        else "<p class='muted'>No personalized projects generated for this student yet.</p>"
    )

    body += f"""
    <section>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2>Personalized Dynamic Project</h2>
        <span class="badge" style="background:#e0f2fe;color:#0369a1;">Domain: {esc(interest_label)}</span>
      </div>
      <p class="muted">{esc(interest_context)}</p>
      <form method="POST" action="/api/projects/generate" style="margin-bottom:16px;">
        <input type="hidden" name="student_id" value="{esc(sid)}">
        <button type="submit" style="background:#087674;color:white;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:600;">Generate Personalized Project for {esc(sid)}</button>
      </form>
      {proj_table}
    </section>
    """

    body += (
        '<section><h2>Add a synthetic attempt</h2><p>This form exercises the shared engine and updates this synthetic profile. Use the PrairieLearn link for actual platform submissions.</p><form method="post" action="/attempt"><input type="hidden" name="student_id" value="'
        + esc(sid)
        + '"><label>Question <select name="question_id">'
        + "".join("<option>" + q + "</option>" for q in QUESTIONS)
        + '</select></label><p><label>SQL query<textarea name="sql" required maxlength="12000"></textarea></label></p><button>Evaluate and update synthetic profile</button></form></section>'
    )
    return shell("Student " + sid, body)


def projects_page(project_id=None, is_learner=False, csrf_token=None, learner_sid=None):
    csrf = csrf_token or ""
    project_repo = get_project_repo()
    if project_id:
        proj = project_repo.get_project(project_id)
        if not proj:
            return shell(
                "Project Not Found",
                "<section><h2>404 Not Found</h2><p>Project not found.</p></section>",
            )

        milestones_html = ""
        for m in proj.milestones:
            rank_label = {1: "Foundational", 2: "Intermediate", 3: "Advanced"}.get(
                m.difficulty_rank, "Core"
            )
            rank_color = {1: "#0369a1", 2: "#d97706", 3: "#b91c1c"}.get(
                m.difficulty_rank, "#087674"
            )
            rank_bg = {1: "#e0f2fe", 2: "#fef3c7", 3: "#fee2e2"}.get(m.difficulty_rank, "#f0fdf4")

            # Answer key concealment: never show reference SQL solution in learner view
            solution_html = ""
            if not is_learner:
                solution_html = f"""
                <details style="margin-top:8px;">
                  <summary>Reference SQL Solution (Grading Ground Truth)</summary>
                  <pre style="background:#1e293b;color:#f8fafc;padding:12px;border-radius:6px;margin-top:6px;">{esc(m.reference_sql)}</pre>
                </details>
                """

            milestones_html += f"""
            <div style="border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:16px;background:#f8fafc;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <h4 style="margin:0 0 6px 0;">Milestone {m.milestone_index}: {esc(m.title)}</h4>
                <span class="badge" style="background:{rank_bg};color:{rank_color};font-weight:600;">Rank {m.difficulty_rank} ({rank_label}) &middot; Depth {m.concept_depth}</span>
              </div>
              <p><strong>Task:</strong> {esc(m.task_description)}</p>
              <p><strong>Target concepts:</strong> {esc(", ".join(m.target_concepts))}</p>
              <p class="muted"><strong>Rubric:</strong> {esc(m.evaluation_rubric)}</p>
              {solution_html}
            </div>
            """

        status_color = "#166534" if proj.instructor_approval_status == "APPROVED" else "#92400e"
        status_bg = "#dcfce7" if proj.instructor_approval_status == "APPROVED" else "#fef3c7"

        # Pending approval notice for unapproved projects in learner view
        pending_notice = ""
        if is_learner and proj.instructor_approval_status != "APPROVED":
            milestones_html = "<p>Scaffolded activities unlock after instructor approval.</p>"
            pending_notice = """
            <div style="background:#fef3c7;border-left:4px solid #d97706;padding:14px;border-radius:6px;margin-bottom:18px;color:#92400e;">
              <strong>Pending Instructor Approval:</strong> This personalized project has not yet been approved by course instructors. Reference solutions and official milestone submissions remain locked until approved.
            </div>
            """

        # Instructor review form is strictly withheld from learner view
        review_controls_html = ""
        if not is_learner:
            review_controls_html = f"""
            <h3>Instructor Review & Approval</h3>
            <form method="POST" action="/api/projects/review" style="display:flex;gap:10px;align-items:center;">
              <input type="hidden" name="project_id" value="{esc(proj.project_id)}">
              <input type="hidden" name="csrf_token" value="{esc(csrf)}">
              <input type="text" name="notes" placeholder="Instructor feedback notes..." value="{esc(proj.instructor_notes or "")}" style="padding:8px;width:300px;border:1px solid #cbd5e1;border-radius:6px;">
              <button type="submit" name="status" value="APPROVED" style="background:#16a34a;">Approve Project</button>
              <button type="submit" name="status" value="REVISED" style="background:#d97706;">Request Revision</button>
            </form>
            """
        else:
            review_controls_html = "<p class='muted'>Learner view &middot; Reference solutions and review controls are withheld.</p>"

        body = f"""
        <section>
          {pending_notice}
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <h2>{esc(proj.title)}</h2>
            <span class="badge" style="background:{status_bg};color:{status_color};font-size:14px;">Status: {esc(proj.instructor_approval_status)}</span>
          </div>
          <p><span class="badge" style="background:#e0f2fe;color:#0369a1;">Domain: {esc(proj.domain_interest)}</span> &middot; <span class="badge" style="background:#f1f5f9;color:#334155;">Learner: <a href="/students?id={esc(proj.student_id)}">{esc(proj.student_id)}</a></span> &middot; <span class="badge" style="background:#fef3c7;color:#92400e;">SYNTHETIC_COURSE_MATERIAL</span></p>
          <h3>Scenario Narrative</h3>
          <p style="font-size:17px;line-height:1.6;background:#f8fafc;padding:14px;border-left:4px solid #087674;border-radius:4px;">{esc(proj.scenario_narrative)}</p>

          <h3>Relational Database Schema (SQLite DDL)</h3>
          <pre style="background:#1e293b;color:#f8fafc;padding:14px;border-radius:8px;font-size:13px;">{esc(proj.schema_ddl)}</pre>

          <h3>Milestones & Task Decomposition</h3>
          {milestones_html}

          {review_controls_html}
          <p style="margin-top:16px;"><a href="/projects">&larr; Back to all projects</a></p>
        </section>
        """
        return shell(f"Project · {proj.title}", body)

    # All projects list view
    if is_learner:
        all_projects = project_repo.list_projects_for_student(learner_sid) if learner_sid else []
    else:
        all_projects = project_repo.list_all_projects()
    rows = []
    for p in all_projects:
        st_color = "#166534" if p.instructor_approval_status == "APPROVED" else "#92400e"
        st_bg = "#dcfce7" if p.instructor_approval_status == "APPROVED" else "#fef3c7"
        rows.append(
            [
                f"<a href='/projects?id={esc(p.project_id)}'><code>{esc(p.project_id)}</code></a>",
                f"<a href='/students?id={esc(p.student_id)}'>{esc(p.student_id)}</a>",
                f"<span class='badge' style='background:#e0f2fe;color:#0369a1;'>{esc(p.domain_interest)}</span>",
                esc(p.title),
                f"<span class='badge' style='background:{st_bg};color:{st_color};'>{esc(p.instructor_approval_status)}</span>",
                f"<a href='/projects?id={esc(p.project_id)}'>View Brief &amp; Tasks &rarr;</a>",
            ]
        )

    table_html = (
        table(["Project ID", "Learner", "Domain", "Title", "Status", "Action"], rows)
        if rows
        else "<p class='muted'>No dynamic projects generated yet.</p>"
    )

    if is_learner and learner_sid:
        gen_forms = f"""
        <div class="card">
          <h4>{esc(learner_sid)}</h4>
          <p class="muted">{esc(STUDENT_INTEREST_PROFILES.get(learner_sid, {}).get("label", "General"))}</p>
          <form method="POST" action="/api/projects/generate">
            <input type="hidden" name="student_id" value="{esc(learner_sid)}">
            <input type="hidden" name="csrf_token" value="{esc(csrf)}">
            <label>1. Choose your interest <select name="interest"><option value="healthcare">Healthcare</option><option value="public_transit">Public transit</option><option value="gaming">Gaming</option><option value="climate">Climate</option><option value="fintech">Digital payments</option></select></label><br><br>
            <button type="submit" style="padding:6px 12px;font-size:13px;">Generate My Project</button>
          </form>
        </div>
        """
    else:
        gen_forms = "".join(
            f"""
            <div class="card">
              <h4>{esc(sid)}</h4>
              <p class="muted">{esc(STUDENT_INTEREST_PROFILES.get(sid, {}).get("label", "General"))}</p>
              <form method="POST" action="/api/projects/generate">
                <input type="hidden" name="student_id" value="{esc(sid)}">
                <input type="hidden" name="csrf_token" value="{esc(csrf)}">
                <button type="submit" style="padding:6px 12px;font-size:13px;">Generate Project</button>
              </form>
            </div>
            """
            for sid in STUDENTS
        )

    body = f"""
    <section>
      <h2>Personalized Dynamic SQL Projects</h2>
      <p class="muted">Grounded, open-ended multi-table projects tailored to student domain interests and diagnosed concept gaps. All specifications include verified SQLite schemas and deterministic grading rubrics.</p>
      <h3>1. Interest collection → 2. Candidate construction → 3. Scaffolded ranking</h3>
      <div class="cards" style="margin-bottom:24px;">
        {gen_forms}
      </div>
      <h3>Generated Project Registry</h3>
      {table_html}
    </section>
    """
    return shell("Dynamic Projects", body)


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


def em_review_page(filter_status=None, csrf_token=None):
    csrf = csrf_token or ""
    em_repo = get_em_repo()
    all_evidence = em_repo.list_all_evidence()

    proposed_count = sum(1 for e in all_evidence if e.review_status == EMReviewStatus.PROPOSED)
    accepted_count = sum(1 for e in all_evidence if e.review_status == EMReviewStatus.ACCEPTED)
    other_count = sum(
        1
        for e in all_evidence
        if e.review_status in (EMReviewStatus.REJECTED, EMReviewStatus.NEEDS_REVISION)
    )

    filtered = [
        e for e in all_evidence if filter_status is None or e.review_status.value == filter_status
    ]

    rows = []
    for ev in filtered:
        st = ev.review_status.value
        status_color = (
            "#166534" if st == "ACCEPTED" else ("#b91c1c" if st == "REJECTED" else "#92400e")
        )
        status_bg = (
            "#dcfce7" if st == "ACCEPTED" else ("#fee2e2" if st == "REJECTED" else "#fef3c7")
        )
        action_form = f"""
        <form method="POST" action="/api/em/review" style="display:flex;gap:6px;align-items:center;">
          <input type="hidden" name="evidence_id" value="{esc(ev.evidence_id)}">
          <input type="hidden" name="csrf_token" value="{esc(csrf)}">
          <input type="text" name="instructor_notes" placeholder="Notes..." value="{esc(ev.instructor_notes or "")}" style="padding:4px;font-size:12px;width:120px;border:1px solid #cbd5e1;border-radius:4px;">
          <button type="submit" name="review_status" value="ACCEPTED" style="background:#16a34a;padding:5px 9px;font-size:12px;">Accept</button>
          <button type="submit" name="review_status" value="REJECTED" style="background:#dc2626;padding:5px 9px;font-size:12px;">Reject</button>
          <button type="submit" name="review_status" value="NEEDS_REVISION" style="background:#d97706;padding:5px 9px;font-size:12px;">Revise</button>
        </form>
        """
        rows.append(
            [
                f"<a href='/students?id={esc(ev.student_id)}'>{esc(ev.student_id)}</a>",
                esc(ev.question_id),
                f"<strong>{esc(ev.dimension.value)}</strong>",
                f"<span title='{esc(ev.evidence_excerpt)}'>{esc(ev.evidence_excerpt[:90] + ('...' if len(ev.evidence_excerpt) > 90 else ''))}</span>",
                f"<small>{esc(ev.classification_method)} ({ev.confidence:.2f})</small>",
                f"<span class='badge' style='background:{status_bg};color:{status_color};'>{esc(st)}</span>",
                action_form,
            ]
        )

    table_html = (
        table(
            [
                "Student",
                "Question",
                "Dim",
                "Evidence Excerpt",
                "Classification",
                "Status",
                "Actions",
            ],
            rows,
        )
        if rows
        else "<p class='muted'>No evidence records matching current filter.</p>"
    )

    body = f"""
    <section>
      <h2>Instructor Entrepreneurial Mindset (EM) Evidence Review</h2>
      <p class="muted">Review, validate, or revise behavioral EM reflection evidence submitted by synthetic learners. Model-proposed and rule-inferred observations remain provisional until accepted here.</p>
      <div class="cards" style="margin-bottom:20px;">
        <div class="card"><div class="metric">{len(all_evidence)}</div>Total records</div>
        <div class="card"><div class="metric" style="color:#d97706;">{proposed_count}</div>Pending review</div>
        <div class="card"><div class="metric" style="color:#16a34a;">{accepted_count}</div>Accepted</div>
        <div class="card"><div class="metric" style="color:#64748b;">{other_count}</div>Rejected / Revision</div>
      </div>
      <div style="margin-bottom:14px;">
        <strong>Filter:</strong>
        <a href="/em-review" style="margin:0 8px;font-weight:{"bold" if not filter_status else "normal"}">All</a> &middot;
        <a href="/em-review?status=PROPOSED" style="margin:0 8px;font-weight:{"bold" if filter_status == "PROPOSED" else "normal"}">Pending (PROPOSED)</a> &middot;
        <a href="/em-review?status=ACCEPTED" style="margin:0 8px;font-weight:{"bold" if filter_status == "ACCEPTED" else "normal"}">Accepted (ACCEPTED)</a> &middot;
        <a href="/em-review?status=REJECTED" style="margin:0 8px;font-weight:{"bold" if filter_status == "REJECTED" else "normal"}">Rejected (REJECTED)</a>
      </div>
      {table_html}
    </section>
    """
    return shell("EM Evidence Review", body)


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


def practice_page(
    qid="sql_join_04",
    grading_result=None,
    feedback_data=None,
    csrf_token=None,
    auth=None,
    assignment_id=None,
):
    csrf = csrf_token or ""
    if qid not in QUESTIONS:
        qid = "sql_join_04"
    q_info = QUESTIONS[qid]

    submission_receipt_html = ""
    if grading_result:
        score = grading_result.get("score", 0.0)
        status = grading_result.get("grading_status") or grading_result.get("status", "unknown")
        status_color = "#166534" if score == 1.0 or status == "correct" else "#b91c1c"
        status_bg = "#dcfce7" if score == 1.0 or status == "correct" else "#fee2e2"
        fb_url = feedback_data.get("feedback_url") if feedback_data else ""
        job_id = feedback_data.get("job_id") if feedback_data else ""

        fb_link_html = ""
        if fb_url:
            fb_link_html = f"""
            <div style="margin-top:14px;padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;">
              <strong>Async AI Feedback Available:</strong> Job <code>{esc(job_id)}</code> &middot;
              <a id="ai-feedback-link" href="{esc(fb_url)}" style="font-weight:600;color:#087674;">View Grounded AI Explanation &rarr;</a>
            </div>
            """

        submission_receipt_html = f"""
        <div style="background:#ffffff;border:2px solid {"#16a34a" if score == 1.0 or status == "correct" else "#dc2626"};border-radius:8px;padding:18px;margin-bottom:24px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h3 style="margin:0;">PrairieLearn Grading Receipt</h3>
            <span class="badge" style="background:{status_bg};color:{status_color};font-size:14px;font-weight:600;">{esc(status.upper())} &middot; Score: {int(score * 100)}%</span>
          </div>
          <p><strong>Guidance:</strong> {esc(grading_result.get("observation") or status)}</p>
          {fb_link_html}
        </div>
        """

    options_html = "".join(
        f"<option value='{q}' {'selected' if q == qid else ''}>{q} · {QUESTIONS[q]['statement'][:60]}...</option>"
        for q in QUESTIONS
    )

    body = f"""
    <section>
      <h2>PrairieLearn Interactive SQL Practice</h2>
      <p class="muted">Live browser submission exercising authentic PrairieLearn bridge grading, deterministic score calculation, and asynchronous grounded feedback dispatch.</p>
      {submission_receipt_html}
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:18px;margin-bottom:20px;">
        <h3>Question: <code>{esc(qid)}</code></h3>
        <p style="font-size:15px;line-height:1.5;"><strong>Prompt:</strong> {esc(q_info["statement"])}</p>
        <p class="muted"><strong>Schema:</strong> Employees(employee_id INTEGER, name TEXT, department_id INTEGER); Departments(department_id INTEGER, department_name TEXT).</p>
      </div>
      <form method="POST" action="/practice">
        <input type="hidden" name="submission_key" value="{uuid.uuid4().hex}">
        <input type="hidden" name="csrf_token" value="{esc(csrf)}">
        {f'<input type="hidden" name="assignment_id" value="{esc(assignment_id)}">' if assignment_id else ""}
        <div style="margin-bottom:12px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;">Select Problem:</label>
          <select name="question_id" onchange="window.location.href='/practice?id=' + this.value" style="padding:6px 10px;font-size:14px;">
            {options_html}
          </select>
        </div>
        <div style="margin-bottom:16px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;">Your SQL Query:</label>
          <textarea id="sql" name="sql" rows="6" style="width:100%;box-sizing:border-box;padding:10px;font-family:monospace;font-size:14px;border:1px solid #cbd5e1;border-radius:6px;" placeholder="-- Enter SQL query here"></textarea>
        </div>
        <button type="submit" id="submit-query" style="background:#087674;color:white;padding:10px 20px;font-weight:600;border:none;border-radius:6px;cursor:pointer;">Submit Query for Grading</button>
      </form>
    </section>
    """
    return shell(f"Practice · {qid}", body)


def get_jobs_repo():
    jobs_db = os.environ.get("SIIP_FEEDBACK_JOBS_DB") or str(
        ROOT / "artifacts/jobs/feedback_jobs.sqlite3"
    )
    return FeedbackJobRepository(jobs_db)


def get_em_repo():
    em_db = os.environ.get("SIIP_DB_PATH") or str(ROOT / "artifacts/synthetic.sqlite3")
    return EMRepository(em_db)


def get_project_repo():
    db_path = os.environ.get("SIIP_DB_PATH") or str(ROOT / "artifacts/synthetic.sqlite3")
    return ProjectRepository(db_path)


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

    # 2. Try session token (Authorization: Bearer <token>, X-Synthetic-Session, or Cookie)
    session_token = extract_session_token(headers)
    if session_token and synthetic_auth_enabled():
        p, r = verify_signed_session_token_role(session_token)
        if p and (r == "student" or is_student_principal(p) or is_instructor_principal(p)):
            return p, None
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


def feedback_page(job_id, headers, params, csrf_token=None):
    csrf = csrf_token or ""
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
        if fb.get("grounding_provenance"):
            body += f'<section data-testid="assignment-grounding"><h3>Uploaded lesson and reviewed graph used for feedback</h3>{pretty(fb["grounding_provenance"])}<p>Inference: {esc(fb.get("inference_status"))} · model digest: {esc(fb.get("model_digest") or "not applicable")}</p></section>'
        hist_note = ""
        if fb.get("personalized"):
            hist_note = f"<p><small class='badge' style='background:#e8f5e9;color:#1b5e20;'>Prior learning evidence included in context ({esc(fb.get('history_provenance', 'prior_submissions'))}); feedback adaptation is not established.</small></p>"
        else:
            hist_note = "<p><small class='badge' style='background:#f3f4f6;color:#374151;'>No relevant prior learning evidence was included in context.</small></p>"

        body += f"""
        <section style="border-left:4px solid #087674;">
          <h3>Pedagogical guidance</h3><p data-testid="feedback-quality">Feedback quality: {esc(fb.get("feedback_quality", "legacy_unreviewed"))}. Model guidance requires review; automated checks do not guarantee teaching correctness.</p>
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

        em_repo = get_em_repo()
        em_prompt = em_repo.get_prompt_for_question(learner_view["question_id"])
        if em_prompt:
            existing_resp = em_repo.get_response_for_student_question(
                auth_student, learner_view["question_id"]
            )
            ticket_val = params.get("ticket", [""])[0] if params else ""
            if existing_resp:
                ev_records = [
                    e
                    for e in em_repo.get_evidence_for_student(auth_student)
                    if e.question_id == learner_view["question_id"]
                ]
                latest_ev = ev_records[0] if ev_records else None
                status_str = latest_ev.review_status.value if latest_ev else "PROPOSED"
                status_color = "#166534" if status_str == "ACCEPTED" else "#92400e"
                status_bg = "#dcfce7" if status_str == "ACCEPTED" else "#fef3c7"
                body += f"""
                <section style="border-left:4px solid #f59e0b;background:#fefce8;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <h3>Entrepreneurial Mindset (EM) Reflection</h3>
                    <span class="badge" style="background:{status_bg};color:{status_color};">Status: {esc(status_str)}</span>
                  </div>
                  <p><strong>{esc(em_prompt.info_box_focus)}</strong></p>
                  <blockquote style="margin:8px 0;padding:8px 16px;background:#ffffff;border-left:3px solid #d97706;border-radius:4px;">
                    <em>"{esc(em_prompt.prompt_text)}"</em>
                  </blockquote>
                  <h4>Your submitted reflection</h4>
                  <pre style="background:#ffffff;padding:12px;border-radius:6px;border:1px solid #e2e8f0;font-family:system-ui,sans-serif;font-size:14px;white-space:pre-wrap;">{esc(existing_resp.response_text)}</pre>
                  <p class="muted" style="font-size:13px;">Submitted: {esc(existing_resp.submitted_at[:19].replace("T", " "))} UTC &middot; Reflection is recorded and queued for instructor review. It does not affect your grading score.</p>
                </section>
                """
            else:
                body += f"""
                <section style="border-left:4px solid #f59e0b;background:#fefce8;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <h3>Entrepreneurial Mindset (EM) Reflection (Optional)</h3>
                    <span class="badge" style="background:#fef3c7;color:#92400e;">Dimension: {esc(em_prompt.dimension.value)}</span>
                  </div>
                  <p><strong>{esc(em_prompt.info_box_focus)}</strong></p>
                  <p class="muted">{esc(em_prompt.why_it_matters)}</p>
                  <blockquote style="margin:8px 0;padding:8px 16px;background:#ffffff;border-left:3px solid #d97706;border-radius:4px;">
                    <em>"{esc(em_prompt.prompt_text)}"</em>
                  </blockquote>
                  <form method="POST" action="/api/em/reflection">
                    <input type="hidden" name="student_id" value="{esc(auth_student)}">
                    <input type="hidden" name="question_id" value="{esc(learner_view["question_id"])}">
                    <input type="hidden" name="prompt_id" value="{esc(em_prompt.prompt_id)}">
                    <input type="hidden" name="attempt_id" value="{esc(job.attempt_id)}">
                    <input type="hidden" name="job_id" value="{esc(job_id)}">
                    <input type="hidden" name="ticket" value="{esc(ticket_val)}">
                    <input type="hidden" name="csrf_token" value="{esc(csrf)}">
                    <p><label for="reflection_text"><strong>Your Reflection:</strong></label></p>
                    <textarea id="reflection_text" name="reflection_text" rows="4" style="width:100%;box-sizing:border-box;margin:6px 0 12px 0;padding:10px;font:14px system-ui;border:1px solid #cbd5e1;border-radius:6px;" placeholder="Share your perspective on how this query connects to broader organizational decisions or systems..." required></textarea>
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                      <span class="muted" style="font-size:13px;">Voluntary reflection for research. Does not affect your PrairieLearn grade.</span>
                      <button type="submit" style="background:#087674;color:white;padding:9px 18px;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Submit Reflection</button>
                    </div>
                  </form>
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
        auth = RequestAuth(self)
        try:
            if parsed.path == "/":
                if auth.is_valid and auth.role == "instructor":
                    self.send(overview(repo))
                elif auth.is_valid and auth.role == "student":
                    self.send(assignments_page(auth))
                else:
                    self.send(login_page())
            elif parsed.path == "/authoring":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(err, code)
                    return
                self.send(
                    authoring_page(
                        csrf_token=auth.csrf_token,
                        notice=params.get("notice", [None])[0],
                        course_id=params.get("course_id", [None])[0],
                    )
                )
            elif parsed.path == "/materials":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(err, code)
                    return
                document_id = params.get("id", [None])[0]
                version_text = params.get("version", [None])[0]
                if not document_id:
                    self.send("Missing document id", 400)
                    return
                version = int(version_text) if version_text else None
                lesson = get_demo_authoring().get_lesson(document_id, version)
                if lesson is None:
                    self.send("Lesson not found", 404)
                    return
                content = (
                    get_demo_authoring().read_lesson_bytes(document_id, version).decode("utf-8")
                )
                self.send(
                    shell(
                        "Stored lesson",
                        f'<section data-testid="stored-lesson"><span class="badge">{esc(lesson.synthetic_provenance_label)}</span><h2>{esc(lesson.original_filename)}</h2><p>Document ID <code>{esc(lesson.source_document_id)}</code> · version {lesson.version} · SHA-256 <code>{esc(lesson.sha256)}</code></p><pre>{esc(content)}</pre></section>',
                    )
                )
            elif parsed.path == "/demo-graph":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(err, code)
                    return
                self.send(
                    demo_graph_page(
                        params.get("graph_id", [None])[0],
                        auth.csrf_token,
                        params.get("notice", [None])[0],
                    )
                )
            elif parsed.path == "/assignments":
                if not auth.has_credential or not auth.is_valid:
                    self.send_response(303)
                    self.send_header("Location", "/login?redirect=/assignments")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    return
                self.send(assignments_page(auth, params.get("notice", [None])[0]))
            elif parsed.path == "/api/demo/lessons":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(json.dumps({"error": err}), code, content="application/json")
                    return
                payload = [item.to_dict() for item in get_demo_authoring().list_lessons()]
                self.send(json.dumps(payload), content="application/json")
            elif parsed.path in {"/api/demo/courses", "/api/demo/modules"}:
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(json.dumps({"error": err}), code, content="application/json")
                registry = get_demo_authoring()
                payload = (
                    registry.list_courses()
                    if parsed.path.endswith("courses")
                    else registry.list_modules(course_id=params.get("course_id", [None])[0])
                )
                self.send(json.dumps(payload), content="application/json")
            elif parsed.path == "/api/demo/graphs":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(json.dumps({"error": err}), code, content="application/json")
                    return
                graph_id = params.get("graph_id", [None])[0]
                payload = (
                    get_demo_kg().retrieve(graph_id) if graph_id else get_demo_kg().list_graphs()
                )
                self.send(json.dumps(payload), content="application/json")
            elif parsed.path == "/api/demo/assignments":
                if not auth.has_credential or not auth.is_valid:
                    self.send(
                        json.dumps({"error": "Authentication required"}),
                        401,
                        content="application/json",
                    )
                    return
                records = get_demo_authoring().list_assignments(
                    published_only=auth.role == "student"
                )
                payload = [item.to_dict() for item in records]
                if auth.role == "student":
                    for item in payload:
                        config = item.get("grading_config", {})
                        item["grading_config"] = {
                            key: config[key]
                            for key in (
                                "engine",
                                "question_id",
                                "graph_id",
                                "graph_version",
                                "score_independent_of_feedback",
                            )
                            if key in config
                        }
                self.send(json.dumps(payload), content="application/json")
            elif parsed.path == "/api/demo/events":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(json.dumps({"error": err}), code, content="application/json")
                    return
                events = [item.to_dict() for item in get_demo_observability().list_events()]
                self.send(json.dumps(events), content="application/json")
            elif parsed.path == "/timeline":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(err, code)
                    return
                record_demo_event(
                    actor_type="instructor",
                    actor_id=auth.principal or "instructor-admin",
                    phase="analytics",
                    event_type="instructor_analytics_viewed",
                    entity_id="instructor-dashboard",
                    artifact_path="screenshots/08_instructor_dashboard.png",
                    source_type="actual_execution",
                )
                rendered = get_demo_observability().render_all()["timeline"]
                self.send(
                    rendered.read_text(encoding="utf-8").replace(
                        "<body>",
                        '<body><p><a href="/lineage">Inspect explicit entity lineage and source-to-attempt identifiers</a></p>',
                        1,
                    )
                )
            elif parsed.path in {"/lineage", "/api/demo/lineage", "/api/demo/enriched-events"}:
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                lineage = entity_lineage(repo)
                if parsed.path == "/api/demo/enriched-events":
                    payload = derive_enriched_events(
                        [item.to_dict() for item in get_demo_observability().list_events()], lineage
                    )
                    return self.send(json.dumps(payload), content="application/json")
                if parsed.path == "/api/demo/lineage":
                    return self.send(json.dumps(lineage), content="application/json")
                nodes = table(
                    ["Entity", "Stable ID / version", "Course", "Assignment", "Evidence kind"],
                    [
                        [
                            esc(node["entity_type"]),
                            esc(node["id"]),
                            esc(node.get("course_id") or "—"),
                            esc(node.get("assignment_id") or "—"),
                            "Persisted" if node["persisted"] else "Computed from history",
                        ]
                        for node in lineage["nodes"]
                    ],
                )
                edges = table(
                    ["Source", "Explicit relation", "Target"],
                    [
                        [esc(edge["source"]), esc(edge["relation"]), esc(edge["target"])]
                        for edge in lineage["edges"]
                    ],
                )
                self.send(
                    shell(
                        "Entity data lineage",
                        f'<section><h2>Source → reviewed graph → assignment → attempt → grade → feedback → review</h2><p>Only persisted identifiers and explicit associations create links. Profiles and recommendations are computed views. <a href="/timeline">Event timeline</a> · <a href="/api/demo/lineage">Export lineage JSON</a></p>{nodes}</section><section><h2>Traceable entity relationships</h2>{edges}<p>Unresolved references: {pretty(lineage["unresolved_references"])}</p></section>',
                    )
                )
            elif parsed.path == "/login":
                is_dev_mode = synthetic_auth_enabled()
                if not is_dev_mode:
                    self.send(
                        "Synthetic login is disabled outside isolated development mode. "
                        "Institutional SSO authentication required.",
                        403,
                    )
                    return
                redirect_url = params.get("redirect", ["/"])[0]
                self.send(login_page(auth=auth, redirect_url=redirect_url))
            elif parsed.path == "/logout":
                self.send_response(303)
                self.send_header("Set-Cookie", "siip_session=; Path=/; Max-Age=0")
                self.send_header("Set-Cookie", "siip_csrf=; Path=/; Max-Age=0")
                self.send_header("Location", "/login")
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
            elif parsed.path == "/students":
                sid = params.get("id", [None])[0]
                if sid is not None and sid not in STUDENTS:
                    self.send("Invalid student_id", 400)
                    return
                if not auth.has_credential:
                    self.send("Authentication required to view student records.", 401)
                    return
                if not auth.is_valid:
                    self.send("Invalid or expired session credentials.", 401)
                    return
                if auth.role == "student":
                    if sid is None:
                        sid = auth.principal
                    elif sid != auth.principal:
                        self.send(
                            f"Forbidden: Student {auth.principal} cannot access records for {sid}.",
                            403,
                        )
                        return
                    self.send(students(repo, sid))
                elif auth.role == "instructor":
                    self.send(students(repo, sid))
                else:
                    self.send("Forbidden", 403)
            elif parsed.path == "/graph":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                self.send(graph_page())
            elif parsed.path == "/em-review":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    self.send(err, code)
                    return
                status_filter = params.get("status", [None])[0]
                self.send(em_review_page(status_filter, csrf_token=auth.csrf_token))
            elif parsed.path == "/projects":
                if not auth.has_credential:
                    self.send("Authentication required. Please log in.", 401)
                    return
                if not auth.is_valid:
                    self.send("Invalid or expired session credentials.", 401)
                    return
                project_id = params.get("id", [None])[0]
                if auth.role == "student":
                    if project_id:
                        proj = get_project_repo().get_project(project_id)
                        if not proj:
                            self.send("Project not found", 404)
                            return
                        if proj.student_id != auth.principal:
                            self.send("Forbidden: Cannot view another student's project.", 403)
                            return
                    self.send(
                        projects_page(
                            project_id,
                            is_learner=True,
                            csrf_token=auth.csrf_token,
                            learner_sid=auth.principal,
                        )
                    )
                elif auth.role == "instructor":
                    self.send(
                        projects_page(project_id, is_learner=False, csrf_token=auth.csrf_token)
                    )
                else:
                    self.send("Forbidden", 403)
            elif parsed.path == "/api/recommendation":
                sid = params.get("student_id", [None])[0]
                if not sid or sid not in STUDENTS:
                    self.send(
                        json.dumps({"error": "Invalid or missing student_id"}),
                        400,
                        content="application/json",
                    )
                    return
                if not auth.has_credential and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Authentication required. Missing credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.has_credential and not auth.is_valid and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Invalid or expired session credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.role == "student" and auth.principal != sid:
                    self.send(
                        json.dumps(
                            {
                                "error": f"Forbidden: Student {auth.principal} cannot access recommendations for {sid}."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                st_profile = repo.profile(sid)
                rec = recommend_next_activity(sid, st_profile)
                self.send(json.dumps(rec), 200, content="application/json")
            elif parsed.path == "/api/projects":
                if not auth.has_credential and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Authentication required. Missing credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.has_credential and not auth.is_valid and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Invalid or expired session credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                project_repo = get_project_repo()
                project_id = params.get("id", [None])[0]
                if auth.role == "student":
                    if project_id:
                        proj = project_repo.get_project(project_id)
                        if not proj:
                            self.send(
                                json.dumps({"error": "Project not found"}),
                                404,
                                content="application/json",
                            )
                            return
                        if proj.student_id != auth.principal:
                            self.send(
                                json.dumps(
                                    {"error": "Forbidden: Cannot view another student's project"}
                                ),
                                403,
                                content="application/json",
                            )
                            return
                        proj_dict = learner_project_payload(proj)
                        self.send(json.dumps(proj_dict), 200, content="application/json")
                    else:
                        projs = project_repo.list_projects_for_student(auth.principal)
                        proj_dicts = [learner_project_payload(p) for p in projs]
                        self.send(
                            json.dumps(proj_dicts),
                            200,
                            content="application/json",
                        )
                elif auth.role == "instructor" or auth.is_service:
                    if project_id:
                        proj = project_repo.get_project(project_id)
                        if not proj:
                            self.send(
                                json.dumps({"error": "Project not found"}),
                                404,
                                content="application/json",
                            )
                            return
                        self.send(json.dumps(proj.to_dict()), 200, content="application/json")
                    else:
                        sid = params.get("student_id", [None])[0]
                        if sid:
                            projs = project_repo.list_projects_for_student(sid)
                        else:
                            projs = project_repo.list_all_projects()
                        proj_dicts = [p.to_dict() for p in projs]
                        self.send(
                            json.dumps(proj_dicts),
                            200,
                            content="application/json",
                        )
                else:
                    self.send(json.dumps({"error": "Forbidden"}), 403, content="application/json")
            elif parsed.path == "/instruments":
                self.send(instruments_page())
            elif parsed.path == "/api/instruments":
                self.send(
                    json.dumps(get_evaluation_instruments()),
                    200,
                    content="application/json",
                )
            elif parsed.path == "/api/cohort-analytics":
                if not auth.has_credential and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Authentication required. Missing credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.has_credential and not auth.is_valid and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Invalid or expired session credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.role == "student":
                    self.send(
                        json.dumps(
                            {
                                "error": "Forbidden: Synthetic students cannot access cohort analytics."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                c_data = repo.analytics()
                em_repo = get_em_repo()
                all_ev = em_repo.list_all_evidence()
                proj_repo = get_project_repo()
                all_projs = proj_repo.list_all_projects()
                cohort_summary = {
                    "cohort_size": c_data["student_count"],
                    "submission_count": c_data["attempt_count"],
                    "correct_count": c_data["correct"],
                    "mean_mastery": c_data["mean_mastery"],
                    "associated_error_concepts": c_data["associated_error_concepts"],
                    "em_reflection_summary": {
                        "total_reflections": len(all_ev),
                        "accepted_count": sum(
                            1 for e in all_ev if e.review_status == EMReviewStatus.ACCEPTED
                        ),
                        "proposed_count": sum(
                            1 for e in all_ev if e.review_status == EMReviewStatus.PROPOSED
                        ),
                    },
                    "project_summary": {
                        "total_generated": len(all_projs),
                        "approved_count": sum(
                            1 for p in all_projs if p.instructor_approval_status == "APPROVED"
                        ),
                        "domains": {
                            p.domain_interest: sum(
                                1 for x in all_projs if x.domain_interest == p.domain_interest
                            )
                            for p in all_projs
                        },
                    },
                    "provenance": "TRACK_A_SYNTHETIC_COHORT",
                }
                self.send(
                    json.dumps(cohort_summary),
                    200,
                    content="application/json",
                )
            elif parsed.path == "/api/em/summary":
                sid = params.get("student_id", [None])[0]
                if not sid or sid not in STUDENTS:
                    self.send(
                        json.dumps({"error": "Missing student_id"}),
                        400,
                        content="application/json",
                    )
                    return
                if not auth.has_credential and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Authentication required."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.has_credential and not auth.is_valid and not auth.is_service:
                    self.send(
                        json.dumps({"error": "Invalid or expired session credentials."}),
                        401,
                        content="application/json",
                    )
                    return
                if auth.role == "student" and auth.principal != sid:
                    self.send(
                        json.dumps(
                            {
                                "error": f"Forbidden: Student {auth.principal} cannot access summary for {sid}."
                            }
                        ),
                        403,
                        content="application/json",
                    )
                    return
                em_repo = get_em_repo()
                self.send(
                    json.dumps(em_repo.student_em_summary(sid)),
                    200,
                    content="application/json",
                )
            elif parsed.path == "/practice":
                if not auth.has_credential:
                    self.send_response(303)
                    self.send_header(
                        "Location",
                        f"/login?redirect=/practice?id={params.get('id', ['sql_join_04'])[0]}",
                    )
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    return
                if not auth.is_valid:
                    self.send("Invalid or expired session credentials.", 401)
                    return
                qid = params.get("id", ["sql_join_04"])[0]
                assignment_id = params.get("assignment_id", [None])[0]
                if assignment_id:
                    assignment = get_demo_authoring().get_assignment(assignment_id)
                    if (
                        assignment is None
                        or assignment.publication_status != "PUBLISHED_LOCAL_DEMO"
                        or qid not in assignment.question_ids
                    ):
                        self.send("Published assignment not found", 404)
                        return
                    record_demo_event(
                        actor_type="student",
                        actor_id=auth.principal or "synthetic-student",
                        phase="assignment",
                        event_type="assignment_opened",
                        entity_id=assignment_id,
                        artifact_path="screenshots/03_student_assignment_visible.png",
                        source_type="actual_execution",
                    )
                self.send(
                    practice_page(
                        qid=qid,
                        csrf_token=auth.csrf_token,
                        auth=auth,
                        assignment_id=assignment_id,
                    )
                )
            elif parsed.path == "/compare":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                self.send(compare(params))
            elif parsed.path == "/feedback":
                job_id = params.get("job_id", [None])[0]
                html_body, code = feedback_page(
                    job_id, self.headers, params, csrf_token=auth.csrf_token
                )
                if code == 200 and job_id:
                    job = get_jobs_repo().get(job_id)
                    if job and job.status == "completed":
                        prior = get_demo_observability().list_events()
                        if not any(
                            item.event_type == "feedback_generation_completed"
                            and item.entity_id == job_id
                            for item in prior
                        ):
                            record_demo_event(
                                actor_type="system",
                                actor_id="siip-feedback-worker",
                                phase="feedback",
                                event_type="feedback_generation_completed",
                                entity_id=job_id,
                                artifact_path="outputs/feedback/05_feedback_result.json",
                                source_type="actual_execution",
                            )
                        record_demo_event(
                            actor_type="student",
                            actor_id=job.student_id,
                            phase="feedback",
                            event_type="feedback_viewed",
                            entity_id=job_id,
                            artifact_path="screenshots/05_feedback_visible.png",
                            source_type="actual_execution",
                        )
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
            elif parsed.path in {"/api/instructor/feedback", "/api/instructor/analytics"}:
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(json.dumps({"error": err}), code, content="application/json")
                course_id = params.get("course_id", [None])[0]
                if not course_id:
                    return self.send(
                        json.dumps({"error": "Missing course_id"}), 400, content="application/json"
                    )
                registry = get_demo_authoring()
                # Assignments may be created by the local demo without a course record.
                assignments = registry.list_assignments(course_id=course_id)
                known_course = any(
                    c["course_id"] == course_id for c in registry.list_courses()
                ) or bool(assignments)
                if not known_course:
                    return self.send(
                        json.dumps({"error": "Course not found"}), 404, content="application/json"
                    )
                if parsed.path.endswith("analytics"):
                    return self.send(
                        json.dumps(repo.analytics(course_id=course_id)), content="application/json"
                    )
                attempt_id = params.get("attempt_id", [None])[0]
                if not attempt_id:
                    return self.send(
                        json.dumps({"error": "Missing attempt_id"}), 400, content="application/json"
                    )
                matches = [
                    a for a in repo.records(course_id=course_id) if a["attempt_id"] == attempt_id
                ]
                job = get_jobs_repo().get_by_attempt(attempt_id)
                if not matches or not job:
                    return self.send(
                        json.dumps({"error": "Feedback not found"}), 404, content="application/json"
                    )
                attempt = matches[0]
                assignment = registry.get_assignment(attempt["assessment_id"])
                grounding = job.grading.get("_grounding") or {}
                if (
                    assignment is None
                    or assignment.course_id != course_id
                    or attempt["question_id"] not in assignment.question_ids
                    or job.student_id != attempt["student_id"]
                    or job.question_id != attempt["question_id"]
                    or job.submitted_sql != attempt["submitted_sql"]
                    or grounding.get("course_id") != course_id
                    or grounding.get("assignment_id") != assignment.assignment_id
                ):
                    return self.send(
                        json.dumps({"error": "Feedback not found"}), 404, content="application/json"
                    )
                payload = {
                    "attempt_id": attempt_id,
                    "course_id": course_id,
                    "assignment_id": assignment.assignment_id,
                    "student_id": attempt["student_id"],
                    "question_id": attempt["question_id"],
                    "job": job.to_learner_dict(),
                }
                return self.send(json.dumps(payload), content="application/json")
            elif parsed.path == "/api/analytics":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(json.dumps({"error": err}), code, content="application/json")
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
            "/login",
            "/logout",
            "/practice",
            "/attempt",
            "/api/attempts",
            "/api/auth/synthetic-session",
            "/api/queue/enqueue",
            "/api/queue/reconcile",
            "/api/em/reflection",
            "/api/em/review",
            "/api/projects/generate",
            "/api/projects/review",
            "/api/demo/lessons/upload",
            "/api/demo/courses/create",
            "/api/demo/modules/create",
            "/api/demo/kg/generate",
            "/api/demo/kg/review",
            "/api/demo/kg/save",
            "/api/demo/assignments/create",
            "/api/demo/assignments/publish",
        }:
            return self.send("Not found", 404)
        if "Content-Length" not in self.headers:
            return self.send("Content length required", 411)
        try:
            size = int(self.headers["Content-Length"])
            if size < 0:
                raise ValueError("Negative length")
            max_request_size = 2 * 1024 * 1024 if self.path == "/api/demo/lessons/upload" else 16000
            if size > max_request_size:
                return self.send("Request too large", 413)
            if self.headers.get("Transfer-Encoding"):
                return self.send("Unsupported transfer encoding", 400)
            self.connection.settimeout(5)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Incomplete payload")
            text = raw.decode("utf-8")
            auth = RequestAuth(self)

            # Local-only professor demonstration upload and authoring lifecycle.
            if self.path in {"/api/demo/courses/create", "/api/demo/modules/create"}:
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                course_id = params["course_id"][0]
                if self.path.endswith("courses/create"):
                    get_demo_authoring().create_course(
                        course_id=course_id, title=params["title"][0]
                    )
                else:
                    get_demo_authoring().create_module(
                        course_id=course_id,
                        module_id=params["module_id"][0],
                        title=params["title"][0],
                    )
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/authoring?course_id={course_id}&notice=Saved+course+configuration",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return
            if self.path == "/api/demo/lessons/upload":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                fields, upload = parse_multipart_upload(self.headers.get("Content-Type", ""), raw)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(fields)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                record = get_demo_authoring().upload_lesson(
                    upload["content"],
                    source_document_id=fields.get("source_document_id", ""),
                    course_id=fields.get("course_id", ""),
                    module_id=fields.get("module_id") or None,
                    original_filename=upload["filename"],
                )
                record_demo_event(
                    actor_type="instructor",
                    actor_id=auth.principal or "instructor-admin",
                    phase="source",
                    event_type="instructor_uploaded_lesson",
                    entity_id=record.source_document_id,
                    artifact_path="outputs/lesson/01_uploaded_lesson.json",
                    source_type="actual_execution",
                )
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/authoring?notice=Uploaded+document+{record.source_document_id}+version+{record.version}",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            if self.path == "/api/demo/kg/generate":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                document_id = params["source_document_id"][0]
                version = int(params["version"][0])
                registry = get_demo_authoring()
                lesson = registry.get_lesson(document_id, version)
                if lesson is None:
                    return self.send("Lesson not found", 404)
                record_demo_event(
                    actor_type="instructor",
                    actor_id=auth.principal or "instructor-admin",
                    phase="knowledge_graph",
                    event_type="kg_extraction_requested",
                    entity_id=document_id,
                    artifact_path="outputs/knowledge_graph/02_extracted_kg.json",
                    source_type="actual_execution",
                )
                registry.set_lesson_processing_status(document_id, version, "PROCESSING")
                try:
                    graph = get_demo_kg().generate_candidates(
                        {
                            **lesson.to_dict(),
                            "content_hash": lesson.sha256,
                            "content": registry.read_lesson_bytes(document_id, version).decode(
                                "utf-8"
                            ),
                        }
                    )
                except Exception:
                    registry.set_lesson_processing_status(document_id, version, "FAILED")
                    raise
                registry.set_lesson_processing_status(document_id, version, "PROCESSED")
                record_demo_event(
                    actor_type="system",
                    actor_id="siip-demo-kg-fixture",
                    phase="knowledge_graph",
                    event_type="kg_extraction_completed",
                    entity_id=graph["graph_id"],
                    artifact_path="outputs/knowledge_graph/02_extracted_kg.json",
                    source_type="actual_execution"
                    if graph.get("extraction_mode") == "LOCAL_LLM_ASSISTED_EXTRACTION"
                    else "synthetic_fixture",
                )
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/demo-graph?graph_id={graph['graph_id']}&notice=Candidate+graph+generated",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            if self.path == "/api/demo/kg/review":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                graph_id = params["graph_id"][0]
                decision = params["decision"][0]
                get_demo_kg().review_edge(
                    graph_id,
                    params["edge_id"][0],
                    decision,
                    auth.principal or "instructor-admin",
                    params.get("notes", [""])[0],
                )
                record_demo_event(
                    actor_type="instructor",
                    actor_id=auth.principal or "instructor-admin",
                    phase="graph_review",
                    event_type="kg_reviewed",
                    entity_id=params["edge_id"][0],
                    artifact_path="outputs/knowledge_graph/02_instructor_approval.json",
                    source_type="synthetic_fixture",
                )
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/demo-graph?graph_id={graph_id}&notice=Relation+{decision.lower()}d+and+persisted",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            if self.path == "/api/demo/kg/save":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                graph_id = params["graph_id"][0]
                saved = get_demo_kg().save_version(graph_id)
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/demo-graph?graph_id={graph_id}&notice=Saved+reviewed+graph+version+{saved['version']}",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            if self.path == "/api/demo/assignments/create":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                question_id = params["question_id"][0]
                node_ids = params.get("kg_node_id", [])
                if question_id not in QUESTIONS or not node_ids:
                    return self.send("Invalid assignment configuration", 400)
                graphs = get_demo_kg().list_graphs()
                if not graphs:
                    return self.send("Generate and review a knowledge graph first", 409)
                graph_id = params.get("graph_id", [graphs[-1]["graph_id"]])[0]
                versions = get_demo_kg().list_versions(graph_id)
                if not versions:
                    return self.send(
                        "Save a reviewed graph version before assignment creation", 409
                    )
                graph = get_demo_kg().retrieve(graph_id, versions[-1]["version"])
                lesson = get_demo_authoring().get_lesson(
                    graph["source_document_id"], graph.get("source_version")
                )
                if lesson is None:
                    return self.send("Graph source not found", 409)
                available_nodes = {node["id"] for node in graph["nodes"]}
                if not set(node_ids).issubset(available_nodes) or not any(
                    edge["review_state"] == "APPROVED" for edge in graph["edges"]
                ):
                    return self.send(
                        "Assignment concepts require a saved graph with an approved relation", 409
                    )
                mapping = {}
                mapping_source = params.get("mapping_source", [""])[0]
                if mapping_source or params.get("mapping_target") or params.get("mapping_notes"):
                    from siip.assignment_grounding import reviewed_concept_mapping

                    mapping = {
                        mapping_source: {
                            "canonical_id": params.get("mapping_target", [""])[0],
                            "reviewed_by": auth.principal or "instructor-admin",
                            "notes": params.get("mapping_notes", [""])[0],
                        }
                    }
                    reviewed_concept_mapping({"concept_mapping": mapping}, graph)
                record = get_demo_authoring().create_assignment(
                    assignment_id=params["assignment_id"][0],
                    course_id=lesson.course_id,
                    module_id=lesson.module_id,
                    source_document_id=lesson.source_document_id,
                    source_version=lesson.version,
                    graph_id=graph_id,
                    graph_version=graph["version"],
                    question_ids=[question_id],
                    kg_node_ids=node_ids,
                    grading_config={
                        "engine": "siip_deterministic_sql_grader",
                        "question_id": question_id,
                        "graph_id": graph_id,
                        "graph_version": graph["version"],
                        "score_independent_of_feedback": True,
                        **({"concept_mapping": mapping} if mapping else {}),
                    },
                )
                self.send_response(303)
                self.send_header(
                    "Location", f"/assignments?notice=Created+draft+{record.assignment_id}"
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            if self.path == "/api/demo/assignments/publish":
                is_auth, code, err = auth.require_instructor()
                if not is_auth:
                    return self.send(err, code)
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    return self.send(csrf_err, csrf_code)
                record = get_demo_authoring().publish_assignment(params["assignment_id"][0])
                record_demo_event(
                    actor_type="instructor",
                    actor_id=auth.principal or "instructor-admin",
                    phase="assignment",
                    event_type="assignment_published",
                    entity_id=record.assignment_id,
                    artifact_path="outputs/assignments/03_published_assignment.json",
                    source_type="actual_execution",
                )
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/assignments?notice=Published+{record.assignment_id}+to+the+local+SIIP+demo",
                )
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            # Route 0a: Synthetic demo login form submission
            if self.path == "/login":
                is_dev_mode = synthetic_auth_enabled()
                if not is_dev_mode:
                    return self.send(
                        "Synthetic login is disabled outside isolated development mode. "
                        "Institutional SSO authentication required.",
                        403,
                    )
                params = parse_qs(text, strict_parsing=True)
                principal = params.get("principal", [None])[0]
                redirect_url = params.get("redirect", ["/"])[0]
                if not redirect_url.startswith("/") or redirect_url.startswith("//"):
                    redirect_url = "/"
                if not principal or (
                    principal not in STUDENTS
                    and not is_student_principal(principal)
                    and not is_instructor_principal(principal)
                ):
                    return self.send("Invalid synthetic principal", 400)
                role = "instructor" if is_instructor_principal(principal) else "student"
                token = create_signed_session_token(principal, role=role)
                csrf = generate_csrf_token(token)
                self.send_response(303)
                self.send_header(
                    "Set-Cookie",
                    f"siip_session={token}; Path=/; HttpOnly; SameSite=Lax",
                )
                self.send_header(
                    "Set-Cookie",
                    f"siip_csrf={csrf}; Path=/; SameSite=Lax",
                )
                self.send_header("Location", redirect_url)
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            # Route 0b: Synthetic demo logout form submission
            if self.path == "/logout":
                self.send_response(303)
                self.send_header("Set-Cookie", "siip_session=; Path=/; Max-Age=0")
                self.send_header("Set-Cookie", "siip_csrf=; Path=/; Max-Age=0")
                self.send_header("Location", "/login")
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return

            # Route 0c: PrairieLearn interactive practice query submission
            if self.path == "/practice":
                if not auth.has_credential:
                    self.send("Authentication required. Please log in.", 401)
                    return
                if not auth.is_valid:
                    self.send("Invalid or expired session credentials.", 401)
                    return
                params = parse_qs(text, strict_parsing=True)
                csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                if not csrf_ok:
                    self.send(csrf_err, csrf_code)
                    return
                qid = params.get("question_id", ["sql_join_04"])[0]
                sql = params.get("sql", [""])[0]
                assignment_id = params.get("assignment_id", [None])[0]
                if qid not in QUESTIONS or not sql.strip():
                    self.send("Invalid question or query", 400)
                    return

                repo = self.server.repository
                if assignment_id:
                    if auth.role != "student":
                        return self.send("Student session required for assignment submission", 403)
                    assignment = get_demo_authoring().get_assignment(assignment_id)
                    if (
                        assignment is None
                        or assignment.publication_status != "PUBLISHED_LOCAL_DEMO"
                        or qid not in assignment.question_ids
                    ):
                        return self.send("Published assignment not found", 404)
                    adapter_assignment = {
                        "assignment_id": assignment.assignment_id,
                        "course_id": assignment.course_id,
                        "question_id": qid,
                        "relevant_kg_node_ids": list(assignment.kg_node_ids),
                        "publication_timestamp": assignment.publication_timestamp_utc,
                        "grading_configuration": assignment.grading_config,
                        "publication_status": assignment.publication_status,
                        "native_prairielearn_publication": assignment.native_prairielearn_publication,
                        "feedback_grounding": {
                            "assignment_id": assignment.assignment_id,
                            "course_id": assignment.course_id,
                            "graph_id": assignment.graph_id,
                            "graph_version": assignment.graph_version,
                            "source_document_id": assignment.source_document_id,
                            "source_version": assignment.source_version,
                            "source_sha256": get_demo_authoring()
                            .get_lesson(assignment.source_document_id, assignment.source_version)
                            .sha256,
                        },
                    }
                    journey = DemoStudentJourney(
                        submission_store=repo,
                        feedback_jobs=get_jobs_repo(),
                        em_store=get_em_repo(),
                    )
                    with self.server.ingestion_lock:
                        result = journey.submit(
                            adapter_assignment,
                            auth.principal,
                            sql,
                            submission_key=params.get("submission_key", [uuid.uuid4().hex])[0],
                        )
                    job_id = result["feedback_job"]["job_id"]
                    ticket = create_signed_ticket(auth.principal, job_id)
                    fb_meta = {
                        "job_id": job_id,
                        "feedback_url": f"/feedback?job_id={job_id}&ticket={ticket}",
                    }
                    siip_meta = result["grading"]
                    siip_meta["attempt_id"] = result["attempt_id"]
                    siip_meta["candidate_concepts"] = result["concepts"]
                    for phase, event_type, entity_id, artifact_path in [
                        (
                            "submission",
                            "sql_submitted",
                            result["attempt_id"],
                            "outputs/submissions/04_student_submission.json",
                        ),
                        (
                            "grade",
                            "grading_completed",
                            result["attempt_id"],
                            "outputs/grading/04_grading_result.json",
                        ),
                        (
                            "diagnosis",
                            "concept_diagnosis_completed",
                            result["attempt_id"],
                            "outputs/grading/04_grading_result.json",
                        ),
                        (
                            "history",
                            "profile_updated",
                            auth.principal,
                            "outputs/student_profiles/06_student_a_profile.json",
                        ),
                        (
                            "feedback",
                            "feedback_job_queued",
                            job_id,
                            "outputs/feedback/05_feedback_job.json",
                        ),
                    ]:
                        record_demo_event(
                            actor_type="student" if phase == "submission" else "system",
                            actor_id=auth.principal if phase == "submission" else "siip-system",
                            phase=phase,
                            event_type=event_type,
                            entity_id=entity_id,
                            artifact_path=artifact_path,
                            source_type="actual_execution",
                        )
                else:
                    # Exercise the same bridge used by the actual PrairieLearn question hooks.
                    submission_data = {
                        "submitted_answers": {"sql": sql},
                        "options": {
                            "user": {"user_id": 101, "uid": f"{auth.principal}@illinois.edu"}
                        },
                        "submission_id": int(time.time() * 1000) % 1000000,
                        "partial_scores": {},
                        "feedback": {},
                    }
                    grade_question(submission_data, qid)
                    fb_meta = submission_data.get("feedback", {})
                    siip_meta = fb_meta.get("siip", {})
                    siip_meta["score"] = float(submission_data.get("score", 0.0))
                    att_id = siip_meta.get("attempt_id") or f"pl-{submission_data['submission_id']}"
                    with self.server.ingestion_lock:
                        repo.process(
                            {
                                "attempt_id": att_id,
                                "student_id": auth.principal,
                                "question_id": qid,
                                "submitted_sql": sql,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "source": "synthetic_fixture",
                            }
                        )

                self.send(
                    practice_page(
                        qid=qid,
                        grading_result=siip_meta,
                        feedback_data=fb_meta,
                        csrf_token=auth.csrf_token,
                        auth=auth,
                        assignment_id=assignment_id,
                    )
                )
                return

            # Route 1: Synthetic local authentication session endpoint
            if self.path == "/api/auth/synthetic-session":
                is_dev_mode = synthetic_auth_enabled()
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
                iid = payload.get("instructor_id") or payload.get("principal")
                role = payload.get("role")

                if sid:
                    if sid not in STUDENTS and not is_student_principal(sid):
                        self.send(
                            json.dumps({"error": "Invalid or unknown synthetic student principal"}),
                            400,
                            content="application/json",
                        )
                        return
                    token = create_signed_session_token(sid, role="student")
                    csrf = generate_csrf_token(token)
                    self.send(
                        json.dumps(
                            {
                                "token": token,
                                "student_id": sid,
                                "principal": sid,
                                "role": "student",
                                "token_type": "Bearer",  # nosec B105
                                "csrf_token": csrf,
                                "expires_in": 86400,
                            }
                        ),
                        200,
                        content="application/json",
                    )
                    return
                elif iid or role == "instructor":
                    principal = iid or "instructor-admin"
                    if not is_instructor_principal(principal):
                        self.send(
                            json.dumps({"error": "Invalid or unknown instructor principal"}),
                            400,
                            content="application/json",
                        )
                        return
                    token = create_signed_session_token(principal, role="instructor")
                    csrf = generate_csrf_token(token)
                    self.send(
                        json.dumps(
                            {
                                "token": token,
                                "instructor_id": principal,
                                "principal": principal,
                                "role": "instructor",
                                "token_type": "Bearer",  # nosec B105
                                "csrf_token": csrf,
                                "expires_in": 86400,
                            }
                        ),
                        200,
                        content="application/json",
                    )
                    return
                else:
                    self.send(
                        json.dumps({"error": "Missing student_id or instructor_id principal"}),
                        400,
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

            # Route 3b: Entrepreneurial Mindset reflection submission
            if self.path == "/api/em/reflection":
                em_repo = get_em_repo()
                is_json = self.headers.get_content_type() == "application/json"
                if is_json:
                    payload = json.loads(text)
                    sid = payload.get("student_id")
                    qid = payload.get("question_id")
                    pid = payload.get("prompt_id")
                    aid = payload.get("attempt_id")
                    refl_text = payload.get("reflection_text") or payload.get("response_text", "")
                    job_id = payload.get("job_id", "")
                    ticket = payload.get("ticket", "")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    sid = params.get("student_id", [None])[0]
                    qid = params.get("question_id", [None])[0]
                    pid = params.get("prompt_id", [None])[0]
                    aid = params.get("attempt_id", [None])[0]
                    refl_text = params.get("reflection_text", [None])[0] or ""
                    job_id = params.get("job_id", [""])[0]
                    ticket = params.get("ticket", [""])[0]

                if not sid or not qid or not pid or not aid or not refl_text.strip():
                    return self.send("Missing required fields for EM reflection", 400)

                # --- Authentication & Caller Verification ---
                if auth.has_credential:
                    if not auth.is_valid:
                        msg = "Invalid or expired session credentials."
                        return (
                            self.send(json.dumps({"error": msg}), 401, content="application/json")
                            if is_json
                            else self.send(msg, 401)
                        )
                    if auth.role == "student" and auth.principal != sid:
                        msg = f"Forbidden: Student {auth.principal} cannot submit reflection for {sid}."
                        return (
                            self.send(json.dumps({"error": msg}), 403, content="application/json")
                            if is_json
                            else self.send(msg, 403)
                        )
                    if not is_json:
                        csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                        if not csrf_ok:
                            return self.send(csrf_err, csrf_code)
                elif ticket:
                    auth_student = verify_signed_ticket(ticket, job_id=job_id) if job_id else None
                    if not auth_student:
                        msg = "Authentication required. Invalid or mismatched reflection ticket."
                        return (
                            self.send(json.dumps({"error": msg}), 401, content="application/json")
                            if is_json
                            else self.send(msg, 401)
                        )
                    if auth_student != sid:
                        msg = f"Forbidden: Feedback ticket is for {auth_student}, cannot submit for {sid}."
                        return (
                            self.send(json.dumps({"error": msg}), 403, content="application/json")
                            if is_json
                            else self.send(msg, 403)
                        )
                else:
                    msg = "Authentication required. Missing session credentials or feedback ticket."
                    return (
                        self.send(json.dumps({"error": msg}), 401, content="application/json")
                        if is_json
                        else self.send(msg, 401)
                    )

                # --- Verify Target Attempt Existence and Ownership ---
                target_attempt = None
                with closing(self.server.repository.connect()) as db:
                    row = db.execute(
                        "SELECT student_id, question_id FROM attempts WHERE attempt_id = ?",
                        (aid,),
                    ).fetchone()
                    if row:
                        target_attempt = {"student_id": row[0], "question_id": row[1]}

                if not target_attempt:
                    jobs_repo = get_jobs_repo()
                    job_obj = jobs_repo.get_by_attempt(aid)
                    if not job_obj and job_id:
                        job_obj = jobs_repo.get(job_id)
                    if job_obj and (job_obj.attempt_id == aid or not aid):
                        target_attempt = {
                            "student_id": job_obj.student_id,
                            "question_id": job_obj.question_id,
                        }

                if not target_attempt:
                    msg = f"Attempt '{aid}' not found."
                    return (
                        self.send(json.dumps({"error": msg}), 404, content="application/json")
                        if is_json
                        else self.send(msg, 404)
                    )

                if target_attempt["student_id"] != sid:
                    msg = f"Forbidden: Attempt '{aid}' belongs to {target_attempt['student_id']}, not {sid}."
                    return (
                        self.send(json.dumps({"error": msg}), 403, content="application/json")
                        if is_json
                        else self.send(msg, 403)
                    )

                if target_attempt["question_id"] != qid:
                    msg = f"Question mismatch: Attempt '{aid}' is for question '{target_attempt['question_id']}', not '{qid}'."
                    return (
                        self.send(json.dumps({"error": msg}), 400, content="application/json")
                        if is_json
                        else self.send(msg, 400)
                    )

                prompt_obj = em_repo.get_prompt_for_question(qid)
                if not prompt_obj or prompt_obj.prompt_id != pid:
                    msg = (
                        f"Prompt mismatch: Prompt '{pid}' does not match question activity '{qid}'."
                    )
                    return (
                        self.send(json.dumps({"error": msg}), 400, content="application/json")
                        if is_json
                        else self.send(msg, 400)
                    )

                # --- Idempotency Policy ---
                existing_resp = em_repo.get_response_for_attempt(sid, aid)
                if existing_resp:
                    existing_ev = em_repo.get_evidence_for_attempt(aid)
                    if is_json:
                        self.send(
                            json.dumps(
                                {
                                    "status": "recorded",
                                    "response_id": existing_resp.response_id,
                                    "evidence_id": existing_ev.evidence_id if existing_ev else "",
                                    "dimension": existing_ev.dimension.value if existing_ev else "",
                                    "review_status": existing_ev.review_status.value
                                    if existing_ev
                                    else "PROPOSED",
                                    "idempotent": True,
                                }
                            ),
                            200,
                            content="application/json",
                        )
                        return
                    else:
                        redirect_target = (
                            f"/feedback?job_id={job_id}&ticket={ticket}"
                            if job_id and ticket
                            else f"/students?id={sid}"
                        )
                        self.send_response(303)
                        self.send_header("Location", redirect_target)
                        self.send_header("Connection", "close")
                        self.close_connection = True
                        self.end_headers()
                        return

                resp = em_repo.record_response(
                    student_id=sid,
                    question_id=qid,
                    prompt_id=pid,
                    attempt_id=aid,
                    response_text=refl_text.strip(),
                )
                dim = prompt_obj.dimension if prompt_obj else EMDimension.CURIOSITY
                concepts = QUESTIONS.get(qid, {}).get("concepts", ["relational_queries"])

                ev = em_repo.create_evidence_record(
                    student_id=sid,
                    question_id=qid,
                    dimension=dim,
                    relevant_concepts=concepts,
                    evidence_excerpt=refl_text.strip(),
                    classification_method="student_reflection_provisional",
                    model_or_rubric_version=prompt_obj.rubric_version
                    if prompt_obj
                    else "rubric-keen-v1",
                    confidence=0.85,
                    response_id=resp.response_id,
                    attempt_id=aid,
                )
                record_demo_event(
                    actor_type="student",
                    actor_id=sid,
                    phase="em",
                    event_type="em_reflection_submitted",
                    entity_id=ev.evidence_id,
                    artifact_path="outputs/em/07_em_evidence.json",
                    source_type="actual_execution",
                )

                if is_json:
                    self.send(
                        json.dumps(
                            {
                                "status": "recorded",
                                "response_id": resp.response_id,
                                "evidence_id": ev.evidence_id,
                                "dimension": ev.dimension.value,
                                "review_status": ev.review_status.value,
                            }
                        ),
                        201,
                        content="application/json",
                    )
                    return
                else:
                    redirect_target = (
                        f"/feedback?job_id={job_id}&ticket={ticket}"
                        if job_id and ticket
                        else f"/students?id={sid}"
                    )
                    self.send_response(303)
                    self.send_header("Location", redirect_target)
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    return

            # Route 3c: Instructor review of EM evidence
            if self.path == "/api/em/review":
                em_repo = get_em_repo()
                is_json = self.headers.get_content_type() == "application/json"
                if is_json:
                    payload = json.loads(text)
                    ev_id = payload.get("evidence_id")
                    review_status = payload.get("review_status")
                    notes = payload.get("instructor_notes")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    ev_id = params.get("evidence_id", [None])[0]
                    review_status = params.get("review_status", [None])[0]
                    notes = params.get("instructor_notes", [None])[0]

                # Strict fail-closed instructor authorization
                auth_ok, code, err_msg = auth.require_instructor()
                if not auth_ok:
                    return (
                        self.send(json.dumps({"error": err_msg}), code, content="application/json")
                        if is_json
                        else self.send(err_msg, code)
                    )

                if not is_json:
                    csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                    if not csrf_ok:
                        return self.send(csrf_err, csrf_code)

                reviewer = auth.principal if auth.principal else "instructor-service"

                if not ev_id or not review_status:
                    return self.send("Missing evidence_id or review_status", 400)

                try:
                    status_enum = EMReviewStatus(review_status)
                except ValueError:
                    return self.send(f"Invalid review_status: {review_status}", 400)

                updated = em_repo.review_evidence(
                    evidence_id=ev_id,
                    status=status_enum,
                    notes=notes,
                    reviewer_id=reviewer,
                )
                if not updated:
                    return self.send("Evidence record not found", 404)
                record_demo_event(
                    actor_type="instructor",
                    actor_id=reviewer,
                    phase="em",
                    event_type="em_evidence_reviewed",
                    entity_id=updated.evidence_id,
                    artifact_path="outputs/em/08_em_review_decision.json",
                    source_type="actual_execution",
                )

                if is_json:
                    self.send(
                        json.dumps(updated.to_dict()),
                        200,
                        content="application/json",
                    )
                    return
                else:
                    self.send_response(303)
                    self.send_header("Location", "/em-review")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    return

            # Route 3d: Generate Personalized Dynamic Project
            if self.path == "/api/projects/generate":
                project_repo = get_project_repo()
                is_json = self.headers.get_content_type() == "application/json"
                if is_json:
                    payload = json.loads(text)
                    sid = payload.get("student_id")
                    domain = payload.get("interest")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    sid = params.get("student_id", [None])[0]
                    domain = params.get("interest", [None])[0]

                if not sid or sid not in STUDENTS:
                    return self.send("Invalid student_id", 400)

                auth_ok, code, err_msg = auth.require_student_or_instructor(target_student_id=sid)
                if not auth_ok:
                    return (
                        self.send(json.dumps({"error": err_msg}), code, content="application/json")
                        if is_json
                        else self.send(err_msg, code)
                    )

                if not is_json:
                    csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                    if not csrf_ok:
                        return self.send(csrf_err, csrf_code)

                repo = self.server.repository
                st_profile = repo.profile(sid)
                project_graph = None
                for attempt in reversed(repo.records(sid)):
                    if not attempt.get("assessment_id"):
                        continue
                    assignment = get_demo_authoring().get_assignment(attempt["assessment_id"])
                    if assignment and assignment.graph_id and assignment.graph_version:
                        project_graph = get_demo_kg().retrieve(
                            assignment.graph_id, assignment.graph_version
                        )
                        break
                project = generate_personalized_project(
                    student_id=sid, interest=domain, profile=st_profile, graph_context=project_graph
                )
                project_repo.save_project(project)
                record_demo_event(
                    actor_type="system",
                    actor_id="siip-project-generator",
                    phase="project",
                    event_type="personalized_project_generated",
                    entity_id=project.project_id,
                    artifact_path="outputs/projects/09_personalized_project.json",
                    source_type="actual_execution",
                )

                if is_json:
                    self.send(
                        json.dumps(
                            learner_project_payload(project)
                            if auth.role == "student"
                            else project.to_dict()
                        ),
                        201,
                        content="application/json",
                    )
                    return
                else:
                    self.send_response(303)
                    self.send_header("Location", f"/projects?id={project.project_id}")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    return

            # Route 3e: Review Personalized Dynamic Project
            if self.path == "/api/projects/review":
                project_repo = get_project_repo()
                is_json = self.headers.get_content_type() == "application/json"
                if is_json:
                    payload = json.loads(text)
                    proj_id = payload.get("project_id")
                    status_val = payload.get("status")
                    notes = payload.get("notes")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    proj_id = params.get("project_id", [None])[0]
                    status_val = params.get("status", [None])[0]
                    notes = params.get("notes", [None])[0]

                auth_ok, code, err_msg = auth.require_instructor()
                if not auth_ok:
                    return (
                        self.send(json.dumps({"error": err_msg}), code, content="application/json")
                        if is_json
                        else self.send(err_msg, code)
                    )

                if not is_json:
                    csrf_ok, csrf_code, csrf_err = auth.verify_csrf(params)
                    if not csrf_ok:
                        return self.send(csrf_err, csrf_code)

                reviewer = auth.principal if auth.principal else "instructor-service"

                if not proj_id or not status_val:
                    return self.send("Missing project_id or status", 400)

                proj = project_repo.get_project(proj_id)
                if not proj:
                    return self.send("Project not found", 404)

                proj = project_repo.review_project(proj_id, status_val, reviewer, notes)
                if status_val == "APPROVED":
                    record_demo_event(
                        actor_type="instructor",
                        actor_id=reviewer,
                        phase="project",
                        event_type="project_approved",
                        entity_id=proj.project_id,
                        artifact_path="outputs/projects/09_project_instructor_review.json",
                        source_type="actual_execution",
                    )

                if is_json:
                    self.send(
                        json.dumps(proj.to_dict()),
                        200,
                        content="application/json",
                    )
                    return
                else:
                    self.send_response(303)
                    self.send_header("Location", f"/projects?id={proj.project_id}")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
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
            if (
                payload.get("student_id") not in STUDENTS
                or payload.get("question_id") not in QUESTIONS
                or not isinstance(payload.get("sql"), str)
                or not payload["sql"].strip()
            ):
                raise ValueError("Invalid attempt fields")
            allowed, code, error = auth.require_student_or_instructor(payload["student_id"])
            if not allowed:
                return self.send(error, code)
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
        validate_dashboard_auth()
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
