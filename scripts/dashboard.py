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
from siip.em_models import EMDimension, EMReviewStatus
from siip.em_repository import EMRepository
from siip.feedback import generate_feedback, load_graphs
from siip.grader import QUESTIONS, grade
from siip.identity import (
    create_signed_session_token,
    create_signed_ticket,
    is_instructor_principal,
    is_student_principal,
    verify_service_request,
    verify_signed_session_token,
    verify_signed_session_token_role,
    verify_signed_ticket,
)
from siip.jobs import AttemptConflictError, FeedbackJobRepository, JobQueueFullError
from siip.observability import event
from siip.project_generator import ProjectRepository, generate_personalized_project
from siip.project_models import STUDENT_INTEREST_PROFILES
from siip.recommender import recommend_next_activity
from siip.store import STUDENTS, SubmissionRepository
from siip.survey_instruments import get_evaluation_instruments

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
        + '</style><header><span class="badge">SYNTHETIC DATA · LOCAL RESEARCH</span><h1>SQL learning observatory</h1><p>PrairieLearn × InstructKG · JOINs and NULL semantics</p><nav><a href="/">Overview</a><a href="/students">Students</a><a href="/em-review">EM review</a><a href="/projects">Projects</a><a href="/instruments">Instruments</a><a href="/graph">Graph review</a><a href="/compare">Feedback lab</a><a href="http://localhost:3000/pl">PrairieLearn</a></nav></header><main>'
        + body
        + "</main></html>"
    )


def overview(repo):
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
      <p class="muted">Validated measurement instruments covering Student Cognitive &amp; Affective Perceptions, Instructor Pedagogical Quality, and Triple-Blinded Comparative Review.</p>

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


def projects_page(project_id=None, is_learner=False):
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

    gen_forms = "".join(
        f"""
        <div class="card">
          <h4>{esc(sid)}</h4>
          <p class="muted">{esc(STUDENT_INTEREST_PROFILES.get(sid, {}).get("label", "General"))}</p>
          <form method="POST" action="/api/projects/generate">
            <input type="hidden" name="student_id" value="{esc(sid)}">
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
      <h3>Quick Project Generator</h3>
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


def em_review_page(filter_status=None):
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
        try:
            if parsed.path == "/":
                self.send(overview(repo))
            elif parsed.path == "/students":
                self.send(students(repo, params.get("id", [None])[0]))
            elif parsed.path == "/graph":
                self.send(graph_page())
            elif parsed.path == "/em-review":
                status_filter = params.get("status", [None])[0]
                self.send(em_review_page(status_filter))
            elif parsed.path == "/projects":
                project_id = params.get("id", [None])[0]
                view_mode = params.get("view", [None])[0]
                is_learner = view_mode == "learner"
                auth_hdr = self.headers.get("Authorization", "")
                if auth_hdr.startswith("Bearer "):
                    tok = auth_hdr[7:].strip()
                    p, r = verify_signed_session_token_role(tok)
                    if r == "student" or is_student_principal(p):
                        is_learner = True
                self.send(projects_page(project_id, is_learner=is_learner))
            elif parsed.path == "/api/recommendation":
                sid = params.get("student_id", [None])[0]
                if not sid or sid not in STUDENTS:
                    self.send(
                        json.dumps({"error": "Invalid or missing student_id"}),
                        400,
                        content="application/json",
                    )
                    return
                st_profile = repo.profile(sid)
                rec = recommend_next_activity(sid, st_profile)
                self.send(json.dumps(rec), 200, content="application/json")
            elif parsed.path == "/api/projects":
                project_repo = get_project_repo()
                project_id = params.get("id", [None])[0]
                view_mode = params.get("view", [None])[0]
                is_learner = view_mode == "learner"
                auth_hdr = self.headers.get("Authorization", "")
                if auth_hdr.startswith("Bearer "):
                    tok = auth_hdr[7:].strip()
                    p, r = verify_signed_session_token_role(tok)
                    if r == "student" or is_student_principal(p):
                        is_learner = True

                if project_id:
                    proj = project_repo.get_project(project_id)
                    if not proj:
                        self.send(
                            json.dumps({"error": "Project not found"}),
                            404,
                            content="application/json",
                        )
                        return
                    proj_dict = proj.to_dict()
                    if is_learner:
                        for m in proj_dict.get("milestones", []):
                            m.pop("reference_sql", None)
                        if proj.instructor_approval_status != "APPROVED":
                            proj_dict["learner_notice"] = (
                                "Pending Instructor Approval: Reference solutions and final milestone submissions remain locked until approved."
                            )
                    self.send(json.dumps(proj_dict), 200, content="application/json")
                else:
                    sid = params.get("student_id", [None])[0]
                    if sid:
                        projs = project_repo.list_projects_for_student(sid)
                    else:
                        projs = project_repo.list_all_projects()
                    proj_dicts = [p.to_dict() for p in projs]
                    if is_learner:
                        for pd in proj_dicts:
                            for m in pd.get("milestones", []):
                                m.pop("reference_sql", None)
                    self.send(
                        json.dumps(proj_dicts),
                        200,
                        content="application/json",
                    )
            elif parsed.path == "/instruments":
                self.send(instruments_page())
            elif parsed.path == "/api/instruments":
                self.send(
                    json.dumps(get_evaluation_instruments()),
                    200,
                    content="application/json",
                )
            elif parsed.path == "/api/cohort-analytics":
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
                if not sid:
                    self.send(
                        json.dumps({"error": "Missing student_id"}),
                        400,
                        content="application/json",
                    )
                    return
                em_repo = get_em_repo()
                self.send(
                    json.dumps(em_repo.student_em_summary(sid)),
                    200,
                    content="application/json",
                )
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
            "/api/em/reflection",
            "/api/em/review",
            "/api/projects/generate",
            "/api/projects/review",
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
                    self.send(
                        json.dumps(
                            {
                                "token": token,
                                "student_id": sid,
                                "principal": sid,
                                "role": "student",
                                "token_type": "Bearer",  # nosec B105
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
                    self.send(
                        json.dumps(
                            {
                                "token": token,
                                "instructor_id": principal,
                                "principal": principal,
                                "role": "instructor",
                                "token_type": "Bearer",  # nosec B105
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

                resp = em_repo.record_response(
                    student_id=sid,
                    question_id=qid,
                    prompt_id=pid,
                    attempt_id=aid,
                    response_text=refl_text.strip(),
                )
                prompt_obj = em_repo.get_prompt_for_question(qid)
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
                    reviewer = payload.get("reviewer_id", "instructor-admin")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    ev_id = params.get("evidence_id", [None])[0]
                    review_status = params.get("review_status", [None])[0]
                    notes = params.get("instructor_notes", [None])[0]
                    reviewer = params.get("reviewer_id", ["instructor-admin"])[0]

                # --- Strict Server-Side Role Separation ---
                auth_header = self.headers.get("Authorization", "")
                session_tok = None
                if auth_header.startswith("Bearer "):
                    session_tok = auth_header[7:].strip()
                elif self.headers.get("X-Synthetic-Session"):
                    session_tok = self.headers.get("X-Synthetic-Session").strip()

                if session_tok:
                    tok_principal, tok_role = verify_signed_session_token_role(session_tok)
                    if tok_role == "student" or is_student_principal(tok_principal):
                        msg = "Forbidden: Synthetic students cannot approve, reject, or edit EM evidence."
                        return (
                            self.send(json.dumps({"error": msg}), 403, content="application/json")
                            if is_json
                            else self.send(msg, 403)
                        )
                    if tok_role == "instructor" and is_instructor_principal(tok_principal):
                        reviewer = tok_principal

                if is_student_principal(reviewer) or reviewer in STUDENTS:
                    msg = "Forbidden: Synthetic students cannot act as instructor reviewers."
                    return (
                        self.send(json.dumps({"error": msg}), 403, content="application/json")
                        if is_json
                        else self.send(msg, 403)
                    )

                if not is_instructor_principal(reviewer) and not verify_service_request(
                    self.headers
                ):
                    msg = "Forbidden: Instructor authorization required to review EM evidence."
                    return (
                        self.send(json.dumps({"error": msg}), 403, content="application/json")
                        if is_json
                        else self.send(msg, 403)
                    )

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

                repo = self.server.repository
                st_profile = repo.profile(sid)
                project = generate_personalized_project(
                    student_id=sid, interest=domain, profile=st_profile
                )
                project_repo.save_project(project)

                if is_json:
                    self.send(
                        json.dumps(project.to_dict()),
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
                    reviewer = payload.get("reviewer_id", "instructor-admin")
                else:
                    params = parse_qs(text, strict_parsing=True)
                    proj_id = params.get("project_id", [None])[0]
                    status_val = params.get("status", [None])[0]
                    notes = params.get("notes", [None])[0]
                    reviewer = params.get("reviewer_id", ["instructor-admin"])[0]

                # --- Strict Server-Side Role Separation ---
                auth_header = self.headers.get("Authorization", "")
                session_tok = None
                if auth_header.startswith("Bearer "):
                    session_tok = auth_header[7:].strip()
                elif self.headers.get("X-Synthetic-Session"):
                    session_tok = self.headers.get("X-Synthetic-Session").strip()

                if session_tok:
                    tok_principal, tok_role = verify_signed_session_token_role(session_tok)
                    if tok_role == "student" or is_student_principal(tok_principal):
                        msg = "Forbidden: Synthetic students cannot approve or review dynamic projects."
                        return (
                            self.send(json.dumps({"error": msg}), 403, content="application/json")
                            if is_json
                            else self.send(msg, 403)
                        )
                    if tok_role == "instructor" and is_instructor_principal(tok_principal):
                        reviewer = tok_principal

                if is_student_principal(reviewer) or reviewer in STUDENTS:
                    msg = "Forbidden: Synthetic students cannot approve or review dynamic projects."
                    return (
                        self.send(json.dumps({"error": msg}), 403, content="application/json")
                        if is_json
                        else self.send(msg, 403)
                    )

                if not is_instructor_principal(reviewer) and not verify_service_request(
                    self.headers
                ):
                    msg = "Forbidden: Instructor authorization required to approve projects."
                    return (
                        self.send(json.dumps({"error": msg}), 403, content="application/json")
                        if is_json
                        else self.send(msg, 403)
                    )

                if not proj_id or not status_val:
                    return self.send("Missing project_id or status", 400)

                proj = project_repo.get_project(proj_id)
                if not proj:
                    return self.send("Project not found", 404)

                proj.instructor_approval_status = status_val
                proj.instructor_notes = notes
                project_repo.save_project(proj)

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
