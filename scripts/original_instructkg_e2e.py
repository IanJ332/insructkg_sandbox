import json
import os
import sys
from pathlib import Path

import requests

root = Path(__file__).resolve().parents[1]
launch = json.loads((root / "artifacts/original-integration/live/runtime/launch.json").read_text())
os.environ.update(launch["environment"])
os.environ["SIIP_LLM_MAX_TOKENS"] = "500"
sys.path.insert(0, str(root / "prairielearn-course/serverFilesCourse"))
from siip.demo_kg import DemoKGRepository
from siip.feedback import configured_provider
from siip.grader import QUESTIONS
from siip.jobs import FeedbackJobRepository, FeedbackWorker
from siip.store import SubmissionRepository

base = launch["url"]
out = root / "artifacts/original-integration/e2e"
out.mkdir(parents=True, exist_ok=True)


def save(name, data):
    (out / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def session(principal):
    s = requests.Session()
    r = s.post(
        base + "/login",
        data={"principal": principal, "redirect": "/"},
        allow_redirects=False,
        timeout=30,
    )
    r.raise_for_status()
    assert r.status_code == 303
    return s


def post(s, path, values):
    r = s.post(
        base + path,
        data={"csrf_token": s.cookies["siip_csrf"], **values},
        allow_redirects=False,
        timeout=60,
    )
    if r.status_code != 303:
        raise RuntimeError(f"{path}: HTTP {r.status_code} {r.text[:800]}")
    return {"status": r.status_code, "location": r.headers.get("Location")}


graph = json.loads((root / "artifacts/original-integration/candidate_graph.json").read_text())
review = json.loads(
    (root / "docs/release/evidence/original_chunk_integration/kg_quality_review.json").read_text()
)
if sys.argv[1] == "prepare":
    s = session("instructor_alawini")
    recommendations = {(e["source"], e["relation"], e["target"]): e for e in review["edges"]}
    actions = []
    for edge in graph["edges"]:
        rec = recommendations[(edge["source"], edge["relation"], edge["target"])]
        decision = "APPROVE" if rec["recommendation"] == "APPROVE" else "REJECT"
        response = post(
            s,
            "/api/demo/kg/review",
            {
                "graph_id": graph["graph_id"],
                "edge_id": edge["edge_id"],
                "decision": decision,
                "notes": "Synthetic instructor simulation; independent review: " + rec["rationale"],
            },
        )
        actions.append(
            {
                "edge_id": edge["edge_id"],
                "decision": decision,
                "independent_recommendation": rec["recommendation"],
                "response": response,
            }
        )
    response = post(s, "/api/demo/kg/save", {"graph_id": graph["graph_id"]})
    repo = DemoKGRepository(Path(launch["environment"]["SIIP_DEMO_STATE_DIR"]) / "knowledge_graph")
    version = repo.list_versions(graph["graph_id"])[-1]["version"]
    saved = repo.retrieve(graph["graph_id"], version)
    assert sum(e["review_state"] == "APPROVED" for e in saved["edges"]) == 4
    assignments = []
    for i in range(1, 5):
        aid = f"original-e2e-q{i}"
        node = "JOIN_PREDICATE" if i == 1 else "LEFT_OUTER_JOIN"
        mapping = {
            "mapping_source": "JOIN_PREDICATE",
            "mapping_target": "JOIN_CONDITION",
            "mapping_notes": "Synthetic instructor reviewed the source join predicate as the assessment join condition.",
        }
        a = post(
            s,
            "/api/demo/assignments/create",
            {
                "assignment_id": aid,
                "question_id": f"sql_join_0{i}",
                "kg_node_id": node,
                "graph_id": graph["graph_id"],
                **mapping,
            },
        )
        p = post(s, "/api/demo/assignments/publish", {"assignment_id": aid})
        assignments.append({"assignment_id": aid, "create": a, "publish": p})
    save(
        "review_and_assignments.json",
        {
            "graph_id": graph["graph_id"],
            "version": version,
            "review_actor": "synthetic instructor_alawini; no faculty endorsement",
            "actions": actions,
            "save": response,
            "assignments": assignments,
        },
    )
    print("Prepared reviewed graph version", version, "and four assignments", flush=True)
if sys.argv[1] == "submit":
    import copy

    from siip.demo_student import _attempt_id

    repo = SubmissionRepository(launch["environment"]["SIIP_DB_PATH"])
    jobs = FeedbackJobRepository(launch["environment"]["SIIP_FEEDBACK_JOBS_DB"])
    worker = FeedbackWorker(jobs, worker_id="original-e2e-capture", submission_repo=repo)
    provider = configured_provider()
    assert provider is not None and provider.max_tokens == 500
    captures = []
    original_generate = provider.generate

    def capture(context):
        item = {"context": copy.deepcopy(context)}
        captures.append(item)
        try:
            result = original_generate(context)
            item["raw_return"] = result
            item["request"] = getattr(provider, "last_request_payload", None)
            item["actual_model"] = getattr(provider, "last_model", None)
            return result
        except Exception as exc:
            item["error"] = str(exc)
            item["request"] = getattr(provider, "last_request_payload", None)
            raise

    provider.generate = capture
    # An isolated historical record in another course proves the course filter.
    repo.process(
        {
            "attempt_id": "original-e2e-other-course",
            "student_id": "S001",
            "question_id": "sql_join_01",
            "submitted_sql": "SELECT 1",
            "timestamp": "2025-01-01T00:00:00Z",
            "source": "synthetic_fixture",
            "assessment_id": "other-course-assignment",
            "course_id": "isolated-other-course",
        },
        mode="baseline",
    )
    sessions = {p: session(p) for p in ("S001", "S002")}
    instructor = session("instructor_alawini")
    q4_inner = "SELECT d.department_name, COUNT(e.employee_id) AS employee_count FROM Departments d INNER JOIN Employees e ON d.department_id=e.department_id GROUP BY d.department_id,d.department_name ORDER BY d.department_name;"
    q4_countstar = "SELECT d.department_name, COUNT(*) AS employee_count FROM Departments d LEFT JOIN Employees e ON d.department_id=e.department_id GROUP BY d.department_id,d.department_name ORDER BY d.department_name;"
    q4_no_group = "SELECT d.department_name, COUNT(e.employee_id) AS employee_count FROM Departments d LEFT JOIN Employees e ON d.department_id=e.department_id ORDER BY d.department_name;"
    cases = [
        ("S001", 1, "SELECT 1", "prior-q1-first", False),
        ("S001", 1, "SELECT 2", "prior-q1-repeat", False),
        ("S001", 2, "SELECT 1", "prior-q2", True),
        ("S001", 3, "SELECT 1", "prior-q3", True),
        ("S001", 4, q4_inner, "inner-count-id", True),
        ("S001", 4, q4_countstar, "left-count-star", True),
        ("S001", 4, q4_no_group, "missing-group-by", True),
        ("S001", 4, QUESTIONS["sql_join_04"]["reference_sql"], "correct", True),
        ("S001", 4, "SELEC nonsense", "execution-error", True),
        ("S002", 4, q4_inner, "sparse-inner-count-id", True),
    ]
    receipts = []
    for principal, i, sql, key, use_model in cases:
        aid = f"original-e2e-q{i}"
        qid = f"sql_join_0{i}"
        s = sessions[principal]
        r = s.post(
            base + "/practice",
            data={
                "csrf_token": s.cookies["siip_csrf"],
                "question_id": qid,
                "assignment_id": aid,
                "sql": sql,
                "submission_key": key,
            },
            timeout=90,
        )
        if r.status_code != 200:
            raise RuntimeError(f"submission {key}: HTTP {r.status_code} {r.text[:1000]}")
        attempt_id = _attempt_id(aid, principal, qid, key)
        job = jobs.get_by_attempt(attempt_id)
        if not job:
            raise RuntimeError(f"No queued feedback for {key}: {r.text[:500]}")
        result = worker.process_one(provider=provider if use_model else None)
        if not result or result.job_id != job.job_id:
            raise RuntimeError(f"Unexpected queued job for {key}")
        learner = s.get(base + "/api/feedback", params={"job_id": job.job_id}, timeout=30)
        teacher = instructor.get(
            base + "/api/instructor/feedback",
            params={"course_id": graph["course_id"], "attempt_id": attempt_id},
            timeout=30,
        )
        cross = sessions["S002" if principal == "S001" else "S001"].get(
            base + "/api/feedback", params={"job_id": job.job_id}, timeout=30
        )
        if learner.status_code != 200 or teacher.status_code != 200:
            raise RuntimeError(
                f"Feedback access {key}: {learner.status_code}, {teacher.status_code} {teacher.text[:500]}"
            )
        learner_data = learner.json()
        teacher_data = teacher.json()
        assert learner_data == teacher_data["job"]
        assert cross.status_code == 403
        attempt = repo.attempt_for_student(attempt_id, principal)
        receipts.append(
            {
                "case": key,
                "student_id": principal,
                "assignment_id": aid,
                "attempt": attempt,
                "learner_job": learner_data,
                "instructor": teacher_data,
                "cross_student_status": cross.status_code,
                "used_model": use_model,
            }
        )
        save("receipts.json", receipts)
        save("provider_calls.json", captures)
        print(
            key,
            "grade",
            attempt["grading"]["status"],
            "feedback",
            result.status,
            "model",
            use_model,
            flush=True,
        )
    analytics = instructor.get(
        base + "/api/instructor/analytics", params={"course_id": graph["course_id"]}, timeout=30
    )
    analytics.raise_for_status()
    wrong = instructor.get(
        base + "/api/instructor/feedback",
        params={
            "course_id": "isolated-other-course",
            "attempt_id": receipts[-1]["attempt"]["attempt_id"],
        },
        timeout=30,
    )
    profiles = {sid: repo.profile(sid, course_id=graph["course_id"]) for sid in ("S001", "S002")}
    save(
        "analytics_profiles.json",
        {
            "analytics": analytics.json(),
            "profiles": profiles,
            "cross_course_status": wrong.status_code,
            "provider_calls": len(captures),
        },
    )
    assert len(captures) == 6 and wrong.status_code in (403, 404)
    print("Completed", len(receipts), "student cases and", len(captures), "model calls", flush=True)
