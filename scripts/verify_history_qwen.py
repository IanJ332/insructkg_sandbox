"""Phase 4 matched-history Qwen acceptance against reviewed synthetic assignments.

Run only in an isolated launcher output after stopping its recorded background
worker. This process exercises the existing durable worker while retaining its
actual model inputs/outputs for independent review. It never approves a graph,
downloads a model, changes inference parameters, or publishes to PrairieLearn.
"""

import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def session(base, principal, role):
    client = requests.Session()
    client.trust_env = False
    response = client.post(
        base + "/api/auth/synthetic-session",
        json={"principal": principal, "role": role}
        if role == "instructor"
        else {"student_id": principal},
        timeout=10,
    )
    response.raise_for_status()
    credentials = response.json()
    client.headers["Authorization"] = "Bearer " + credentials["token"]
    client.headers["X-CSRF-Token"] = credentials["csrf_token"]
    return client


def get(client, base, path, **params):
    response = client.get(base + path, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-receipt", type=Path, required=True)
    parser.add_argument("--course", required=True)
    parser.add_argument("--foundation-assignment", required=True)
    parser.add_argument("--later-assignment", required=True)
    parser.add_argument("--followup-assignment", required=True)
    parser.add_argument(
        "--count-assignment", help="Also evaluate observed history across q02/q04 before q03"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ack-isolated-synthetic-local", action="store_true")
    parser.add_argument("--verify-restart", action="store_true")
    args = parser.parse_args()
    if not args.ack_isolated_synthetic_local:
        parser.error("Explicit isolated synthetic-local acknowledgement required")
    receipt = json.loads(args.launch_receipt.read_text(encoding="utf-8-sig"))
    if Path(receipt["repository"]).resolve() != ROOT:
        parser.error("Launch receipt belongs to another checkout")
    base = receipt["url"]
    if urlparse(base).hostname not in {"127.0.0.1", "localhost"}:
        parser.error("Only loopback sandbox URLs are allowed")
    os.environ.update(receipt["environment"])
    # The existing launcher sets 500; its credential filter omits TOKEN names.
    os.environ["SIIP_LLM_MAX_TOKENS"] = "500"
    if (
        os.environ.get("SIIP_LLM_MODEL") != "qwen3:8b"
        or os.environ.get("SIIP_FEEDBACK_PROVIDER") != "local"
        or os.environ.get("SIIP_LLM_TRANSPORT") != "ollama"
        or os.environ.get("SIIP_LLM_BASE_URL") != "http://127.0.0.1:11434/v1"
    ):
        parser.error("Existing local Qwen/Ollama launcher configuration required")

    from siip.assignment_grounding import resolve_grounding
    from siip.demo_authoring import DemoAuthoringRegistry
    from siip.demo_kg import DemoKGRepository
    from siip.demo_student import _attempt_id
    from siip.feedback import OllamaProvider, configured_provider
    from siip.grader import QUESTIONS
    from siip.jobs import AttemptConflictError, FeedbackJobRepository, FeedbackWorker
    from siip.store import SubmissionRepository

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "live_acceptance.json"
    instructor = session(base, "instructor_alawini", "instructor")
    students = {sid: session(base, sid, "student") for sid in ("S001", "S002", "S003")}
    if args.verify_restart:
        report = json.loads(report_path.read_text())
        for case in report["cases"]:
            learner = get(
                students[case["student_id"]], base, "/api/feedback", job_id=case["job_id"]
            )
            teacher = get(
                instructor,
                base,
                "/api/instructor/feedback",
                course_id=args.course,
                attempt_id=case["attempt_id"],
            )
            assert learner == case["learner_response"] == teacher["job"]
        assert (
            get(instructor, base, "/api/instructor/analytics", course_id=args.course)
            == report["analytics"]
        )
        snapshot = Path(report["graph_snapshot_path"])
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == report["graph_snapshot_sha256"]
        write_json(
            output / "restart_verification.json",
            {
                "status": "PASS",
                "attempts": len(report["cases"]),
                "feedback_identical": True,
                "analytics_identical": True,
                "graph_identical": True,
            },
        )
        print(
            "Restart: identical feedback, analytics and graph for", len(report["cases"]), "attempts"
        )
        return
    if report_path.exists():
        parser.error("Evidence already exists; use --verify-restart or a fresh isolated run")
    runtime = Path(receipt["runtime"])
    submissions = SubmissionRepository(runtime / "synthetic.sqlite3")
    jobs = FeedbackJobRepository(runtime / "feedback_jobs.sqlite3")
    assert not submissions.records(course_id=args.course), "Fresh synthetic course required"
    from contextlib import closing

    with closing(jobs.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM feedback_jobs").fetchone()[0] == 0, (
            "Fresh job store required"
        )
    registry = DemoAuthoringRegistry(runtime / "demo-state/authoring")
    assignment_ids = [args.foundation_assignment, args.later_assignment, args.followup_assignment]
    expected_questions = [["sql_join_01"], ["sql_join_02"], ["sql_join_03"]]
    if args.count_assignment:
        assignment_ids.append(args.count_assignment)
        expected_questions.append(["sql_join_04"])
    assignments = [registry.get_assignment(aid) for aid in assignment_ids]
    assert [list(a.question_ids) for a in assignments] == expected_questions
    assert all(
        a.course_id == args.course and a.publication_status == "PUBLISHED_LOCAL_DEMO"
        for a in assignments
    )
    later = assignments[1]
    graph = DemoKGRepository(runtime / "demo-state/knowledge_graph").retrieve(
        later.graph_id, later.graph_version
    )
    assert (
        graph["extraction_mode"] == "LOCAL_LLM_ASSISTED_EXTRACTION" and not graph["fallback_reason"]
    )
    assert any(
        e["review_state"] == "APPROVED"
        and e["source"] == "LEFT_OUTER_JOIN"
        and e["relation"] == "depends_on"
        for e in graph["edges"]
    )
    tags = requests.get("http://127.0.0.1:11434/api/tags", timeout=5).json()
    model = next(m for m in tags["models"] if m["name"] == "qwen3:8b")
    assert model["digest"] == os.environ.get("SIIP_LLM_MODEL_DIGEST")
    backend = configured_provider()
    assert isinstance(backend, OllamaProvider)
    captures = []

    class CapturedOllamaProvider(OllamaProvider):
        def generate(self, context):
            call = {"context": context}
            captures.append(call)
            write_json(output / "model_calls.json", captures)
            try:
                raw, usage = super().generate(context)
            except Exception as exc:
                call["provider_error_type"] = type(exc).__name__
                write_json(output / "model_calls.json", captures)
                raise
            call.update(
                raw_qwen_output=raw,
                usage=usage,
                effective_model=self.last_model,
                request_payload=self.last_request_payload,
            )
            write_json(output / "model_calls.json", captures)
            return raw, usage

    provider = CapturedOllamaProvider(
        os.environ["SIIP_LLM_BASE_URL"],
        backend.model,
        timeout=backend.timeout,
        max_tokens=backend.max_tokens,
    )
    worker = FeedbackWorker(jobs, worker_id="isolated-live-validation", submission_repo=submissions)
    bad_foundation = "SELECT e.name, d.department_name FROM Employees e CROSS JOIN Departments d;"
    bad_later = QUESTIONS["sql_join_01"]["reference_sql"]
    scenarios = [
        ("weak-foundation-1", "S001", 0, bad_foundation, 0),
        ("strong-foundation-1", "S002", 0, QUESTIONS["sql_join_01"]["reference_sql"], 1),
        ("weak-foundation-2", "S001", 0, bad_foundation, 0),
        ("strong-foundation-2", "S002", 0, QUESTIONS["sql_join_01"]["reference_sql"], 1),
        ("longitudinal", "S001", 1, bad_later, 0),
        ("contrasting-later", "S002", 1, bad_later, 0),
        ("no-history", "S003", 1, bad_later, 0),
        ("weak-followup", "S001", 2, bad_later, 0),
        ("strong-followup", "S002", 2, bad_later, 0),
        ("absent-prerequisite-followup", "S003", 2, bad_later, 0),
        ("improvement", "S001", 1, QUESTIONS["sql_join_02"]["reference_sql"], 1),
        ("syntax", "S003", 1, "SELEC name FROM Employees;", 0),
    ]
    if args.count_assignment:
        bad_count = (
            QUESTIONS["sql_join_04"]["reference_sql"]
            .replace("LEFT OUTER JOIN", "INNER JOIN")
            .replace("LEFT JOIN", "INNER JOIN")
        )
        scenarios = [
            ("weak-foundation-1", "S001", 0, bad_foundation, 0),
            ("strong-foundation-1", "S002", 0, QUESTIONS["sql_join_01"]["reference_sql"], 1),
            ("longitudinal", "S001", 1, bad_later, 0),
            ("contrasting-later", "S002", 1, bad_later, 0),
            ("no-history", "S003", 1, bad_later, 0),
            ("related-error", "S001", 3, bad_count, 0),
            ("prior-later-correct", "S002", 1, QUESTIONS["sql_join_02"]["reference_sql"], 1),
            ("related-correct", "S002", 3, QUESTIONS["sql_join_04"]["reference_sql"], 1),
            ("related-sequence", "S003", 3, QUESTIONS["sql_join_04"]["reference_sql"], 1),
            ("weak-followup", "S001", 2, bad_later, 0),
            ("strong-followup", "S002", 2, bad_later, 0),
            ("absent-prerequisite-followup", "S003", 2, bad_later, 0),
            ("improvement", "S001", 1, QUESTIONS["sql_join_02"]["reference_sql"], 1),
            ("syntax", "S003", 1, "SELEC name FROM Employees;", 0),
        ]
    report = {
        "model": model,
        "provider": "CapturedOllamaProvider (native OllamaProvider capture subclass)",
        "cases": [],
        "errors": [],
        "synthetic": True,
        "history_acceptance_policy": "Same advice is valid for sparse evidence; distinct prose alone never proves adaptation. Richer histories are separately reviewed against actual observed outcomes.",
        "feedback_source_sha256": hashlib.sha256(
            (ROOT / "prairielearn-course/serverFilesCourse/siip/feedback.py").read_bytes()
        ).hexdigest(),
        "settings": {
            "model": "qwen3:8b",
            "temperature": 0.1,
            "num_predict": 500,
            "num_ctx": 8192,
            "think": False,
            "timeout_seconds": 60,
        },
        "acceptance_scope": "Transport, validation and delivery only; independent output-quality review is required. Context presence does not prove feedback adaptation.",
    }
    for label, sid, stage, sql, score in scenarios:
        assignment = assignments[stage]
        qid = assignment.question_ids[0]
        key = "live-" + label
        response = students[sid].post(
            base + "/practice",
            data={
                "assignment_id": assignment.assignment_id,
                "question_id": qid,
                "sql": sql,
                "submission_key": key,
            },
            timeout=20,
        )
        response.raise_for_status()
        aid = _attempt_id(assignment.assignment_id, sid, qid, key)
        record = submissions.attempt_for_student(aid, sid)
        queued = jobs.get_by_attempt(aid)
        assert queued.status == "pending", (
            "Stop only the recorded isolated background worker before testing"
        )
        assert record["grading"]["score"] == score
        capture_index = len(captures)
        job = worker.process_one(provider=provider)
        assert job.job_id == queued.job_id
        prior = submissions.records(sid, record["timestamp"], before=True, course_id=args.course)
        learner = get(students[sid], base, "/api/feedback", job_id=job.job_id)
        teacher = get(
            instructor, base, "/api/instructor/feedback", course_id=args.course, attempt_id=aid
        )
        assert learner == teacher["job"]
        page = students[sid].get(base + "/feedback", params={"job_id": job.job_id}, timeout=10)
        page.raise_for_status()
        assert html.escape(learner["feedback"]["feedback_text"]) in page.text
        (output / (label + "-learner.html")).write_text(page.text, encoding="utf-8")
        case = {
            "scenario": label,
            "student_id": sid,
            "attempt_id": aid,
            "job_id": job.job_id,
            "assignment_id": assignment.assignment_id,
            "timestamp": record["timestamp"],
            "prior_attempt_ids": [a["attempt_id"] for a in prior],
            "learner_response": learner,
            "worker_result": job.result,
            "model_call_index": capture_index if len(captures) > capture_index else None,
        }
        report["cases"].append(case)
        semantic = record["grading"]["status"] == "semantic_error"
        case["expected_route"] = "actual_qwen" if semantic else "deterministic_nonsemantic"
        if semantic:
            accepted = (
                job.status == "completed"
                and job.result.get("inference_status") == "live_success"
                and job.model_identifier == "qwen3:8b"
                and job.result.get("context_status") == "available"
                and case["model_call_index"] is not None
            )
        else:
            accepted = (
                job.status == "completed"
                and job.result.get("provider_routing") == "bypassed_nonsemantic"
                and job.result.get("inference_status") == "provider_bypassed_nonsemantic"
                and case["model_call_index"] is None
                and not learner["feedback"]["candidate_concepts"]
            )
        if not accepted:
            report["errors"].append({"scenario": label, "status": job.status, "result": job.result})
        write_json(report_path, report)
        print(label, "grade", score, job.result.get("inference_status"), flush=True)

    by_label = {case["scenario"]: case for case in report["cases"]}

    def context(label):
        return captures[by_label[label]["model_call_index"]]["context"]

    assert not context("weak-foundation-1").get("student_mastery")
    assert not context("no-history").get("student_mastery")
    report["matched_groups"] = []
    for labels in (
        ("longitudinal", "contrasting-later", "no-history"),
        ("weak-followup", "strong-followup", "absent-prerequisite-followup"),
    ):
        weak, strong, absent = [context(label) for label in labels]
        assert (
            weak["prerequisites"]
            == strong["prerequisites"]
            == absent["prerequisites"]
            == ["JOIN_CONDITION"]
        )
        if not args.count_assignment:
            assert weak["student_mastery"]["JOIN_CONDITION"]["mastery_estimate"] < 0.5
            assert strong["student_mastery"]["JOIN_CONDITION"]["mastery_estimate"] > 0.5
        assert "JOIN_CONDITION" not in absent.get("student_mastery", {})
        for key in (
            "question",
            "student_sql",
            "grade",
            "grounding_provenance",
            "reviewed_relationships",
            "lecture_evidence",
        ):
            assert weak[key] == strong[key] == absent[key], key
        group = {
            "scenarios": labels,
            "same_question_sql_grade_graph": True,
            "quality_status": "INDEPENDENT_REVIEW_REQUIRED",
        }
        if args.count_assignment:
            group["legacy_scenario_names_are_not_mastery_claims"] = True
            group["prior_observation_windows"] = [
                ctx.get("prior_observations", {}) for ctx in (weak, strong, absent)
            ]
            group["interpretation"] = (
                "Sparse prerequisite evidence can justify the same advice. Later cases include target-concept history across different tasks; absent prerequisite does not mean absent history."
            )
        else:
            group["prerequisite_estimates"] = [
                weak["student_mastery"]["JOIN_CONDITION"]["mastery_estimate"],
                strong["student_mastery"]["JOIN_CONDITION"]["mastery_estimate"],
                None,
            ]
        report["matched_groups"].append(group)
    if args.count_assignment:
        for label in ("weak-followup", "strong-followup", "absent-prerequisite-followup"):
            server = context(label)
            assert server["prior_observations"]["question_count"] >= 2
            call = captures[by_label[label]["model_call_index"]]
            wire = json.loads(call["request_payload"]["messages"][1]["content"])
            assert wire["prior_observations"] == server["prior_observations"]
            assert "student_mastery" not in wire and "approved_prerequisite_history" not in wire
            provenance = by_label[label]["worker_result"]["prior_observation_provenance"][
                "attempt_ids"
            ]
            assert set(provenance) <= set(by_label[label]["prior_attempt_ids"])
    target = by_label["longitudinal"]
    assert (
        students["S002"]
        .get(base + "/api/feedback", params={"job_id": target["job_id"]}, timeout=10)
        .status_code
        == 403
    )
    assert (
        students["S001"]
        .get(base + "/api/instructor/analytics", params={"course_id": args.course}, timeout=10)
        .status_code
        == 403
    )
    assert (
        instructor.get(
            base + "/api/instructor/feedback",
            params={"course_id": "other-course", "attempt_id": target["attempt_id"]},
            timeout=10,
        ).status_code
        == 404
    )
    original = jobs.get(target["job_id"])
    try:
        jobs.enqueue(
            original.attempt_id,
            original.student_id,
            original.question_id,
            original.submitted_sql,
            original.grading,
            mode="baseline",
            grounding=original.grading["_grounding"],
        )
    except AttemptConflictError:
        pass
    else:
        raise AssertionError("Conflicting feedback mode accepted")
    try:
        resolve_grounding({**original.grading["_grounding"], "graph_version": 999})
    except ValueError:
        pass
    else:
        raise AssertionError("Wrong graph binding accepted")
    replay = students["S001"].post(
        base + "/practice",
        data={
            "assignment_id": args.later_assignment,
            "question_id": "sql_join_02",
            "sql": bad_later,
            "submission_key": "live-longitudinal",
        },
        timeout=20,
    )
    replay.raise_for_status()
    assert len(submissions.records(course_id=args.course)) == len(scenarios)
    assert jobs.get(target["job_id"]).to_learner_dict() == target["learner_response"]
    report["analytics"] = get(instructor, base, "/api/instructor/analytics", course_id=args.course)
    assert report["analytics"]["attempt_count"] == len(scenarios)
    assert report["analytics"]["improvements"]
    snapshot = (
        runtime
        / "demo-state/knowledge_graph"
        / graph["graph_id"]
        / "versions"
        / f"v{graph['version']:04d}.json"
    )
    report["graph_snapshot_path"] = str(snapshot)
    report["graph_snapshot_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (output / "saved_graph_snapshot.json").write_bytes(snapshot.read_bytes())
    report["isolation_and_replay"] = "PASS"
    report["actual_qwen_calls"] = len(captures)
    report["bypassed_cases"] = sum(case["model_call_index"] is None for case in report["cases"])
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    write_json(report_path, report)
    assert not report["errors"], (
        "Live inference acceptance failed; preserved actual outputs for review"
    )


if __name__ == "__main__":
    main()
