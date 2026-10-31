"""Persistent research records. SQLite repository can be replaced by PostgreSQL."""

import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .feedback import diagnosis, generate_feedback, load_graphs
from .grader import QUESTIONS, grade

STUDENTS = ["S001", "S002", "S003", "S004", "S005"]
_ALL_COURSES = object()


def utc_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO8601 string")
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Timestamp requires a timezone")
    return timestamp.astimezone(timezone.utc).isoformat()


class SubmissionRepository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES(1);
                CREATE TABLE IF NOT EXISTS attempts(
                    attempt_id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
                    question_id TEXT NOT NULL, timestamp TEXT NOT NULL, source TEXT NOT NULL,
                    assessment_id TEXT NOT NULL, record TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_student_time ON attempts(student_id,timestamp);""")
            db.executescript("""CREATE TABLE IF NOT EXISTS sync_checkpoints(
                scope TEXT PRIMARY KEY, state TEXT NOT NULL);
                INSERT OR IGNORE INTO schema_version VALUES(2);""")
            db.commit()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @staticmethod
    def normalize(record):
        if not isinstance(record, dict):
            raise ValueError("Submission must be an object")
        allowed = {
            "attempt_id",
            "student_id",
            "question_id",
            "timestamp",
            "submitted_sql",
            "source",
            "assessment_id",
            "external_links",
            "external_score",
            "course_id",
        }
        required = {"attempt_id", "student_id", "question_id", "timestamp", "submitted_sql"}
        if set(record) - allowed or not required <= set(record):
            raise ValueError("Unsupported or missing submission fields")
        sid, qid = record["student_id"], record["question_id"]
        if (
            not isinstance(sid, str)
            or sid not in STUDENTS
            or not isinstance(qid, str)
            or qid not in QUESTIONS
        ):
            raise ValueError("Unknown synthetic identity or question")
        aid, sql = record["attempt_id"], record["submitted_sql"]
        if not isinstance(aid, str) or not 1 <= len(aid) <= 160:
            raise ValueError("Invalid attempt ID")
        if not isinstance(sql, str) or len(sql) > 12000:
            raise ValueError("Invalid SQL payload")
        source = record.get("source", "synthetic_fixture")
        if source not in {
            "synthetic_fixture",
            "local_prairielearn_export",
            "authorized_prairielearn_api",
        }:
            raise ValueError("Unknown submission source")
        timestamp = utc_timestamp(record["timestamp"])
        assessment = record.get("assessment_id", "sql-sandbox")
        if not isinstance(assessment, str) or not 1 <= len(assessment) <= 160:
            raise ValueError("Invalid assessment ID")
        if "course_id" in record:
            from .demo_authoring import _validate_id

            _validate_id(record["course_id"], "course_id")
        output = {key: record[key] for key in required}
        if "course_id" in record:
            output["course_id"] = record["course_id"]
        output.update(timestamp=timestamp, source=source, assessment_id=assessment)
        if "external_score" in record:
            score = record["external_score"]
            if (
                isinstance(score, bool)
                or not isinstance(score, (float, int))
                or score not in {0, 1}
            ):
                raise ValueError("Expected completed binary external grade")
            output["external_score"] = score
        if "external_links" in record:
            links = record["external_links"]
            allowed_links = {
                "submission_id",
                "variant_id",
                "assessment_instance_id",
                "assessment_instance_number",
                "variant_number",
            }
            if (
                not isinstance(links, dict)
                or set(links) - allowed_links
                or any(not isinstance(v, str) or not v.isdigit() for v in links.values())
            ):
                raise ValueError("Unsupported external identifier mapping")
            output["external_links"] = links
        return output

    @staticmethod
    def check_same(saved, record):
        for key in [
            "student_id",
            "question_id",
            "submitted_sql",
            "timestamp",
            "source",
            "assessment_id",
            "external_links",
            "external_score",
            "course_id",
        ]:
            if saved.get(key) != record.get(key):
                raise ValueError("Attempt ID collision")

    def process(self, record, mode="kg", provider=None):
        return self.process_many([record], mode, provider)[0]

    def process_many(
        self, records, mode="kg", provider=None, *, sync_checkpoint=None, include_commit_stats=False
    ):
        from time import monotonic

        from .observability import event

        normalized = [self.normalize(record) for record in records]
        if sync_checkpoint is not None:
            if (
                set(sync_checkpoint) != {"scope", "previous", "state"}
                or not isinstance(sync_checkpoint["scope"], str)
                or not isinstance(sync_checkpoint["state"], dict)
            ):
                raise ValueError("Invalid synchronization checkpoint")
        prepared = {}
        prepared_by_id = {}
        for index, record in sorted(
            enumerate(normalized), key=lambda item: (item[1]["timestamp"], item[0])
        ):
            aid, sid, qid = record["attempt_id"], record["student_id"], record["question_id"]
            prior_duplicate = prepared_by_id.get(aid)
            if prior_duplicate is not None:
                self.check_same(prior_duplicate, record)
                prepared[index] = prior_duplicate
                continue
            with closing(self.connect()) as db:
                existing = db.execute(
                    "SELECT record FROM attempts WHERE attempt_id=?", (aid,)
                ).fetchone()
            if existing:
                saved = json.loads(existing[0])
                self.check_same(saved, record)
                prepared[index] = saved
                prepared_by_id[aid] = saved
                continue
            started = monotonic()
            result = grade(qid, record["submitted_sql"])
            grading_latency_ms = round((monotonic() - started) * 1000, 3)
            if "external_score" in record and result["score"] != record["external_score"]:
                raise ValueError("Recomputed score differs from external score; nothing imported")
            event(
                "grade_completed",
                correlation_id=aid,
                question_id=qid,
                status=result["status"],
                score=result["score"],
                latency_ms=grading_latency_ms,
            )
            course_id = record.get("course_id")
            history_records = self.records(
                sid, record["timestamp"], before=True, course_id=course_id
            )
            known_ids = {row["attempt_id"] for row in history_records}
            history_records.extend(
                row
                for row in prepared_by_id.values()
                if row["attempt_id"] not in known_ids
                and row["student_id"] == sid
                and row.get("course_id") == course_id
                and row["timestamp"] < record["timestamp"]
            )
            history_records.sort(key=lambda row: (row["timestamp"], row["attempt_id"]))
            history = self._profile_from_records(sid, history_records)
            feedback = generate_feedback(
                qid,
                record["submitted_sql"],
                result,
                mode,
                history["concepts"],
                provider,
                prior_records=history_records,
                history_scope={
                    "student_id": sid,
                    "course_id": course_id,
                    "cutoff": record["timestamp"],
                },
            )
            output = {
                **record,
                "grading": result,
                "diagnosis": diagnosis(qid, result),
                "concepts": QUESTIONS[qid]["concepts"],
                "feedback_mode": mode,
                "feedback": feedback,
                "feedback_origin": "local_analytics_recomputed",
                "dataset_version": "employees-departments-v1",
                "profile_version": "beta-heuristic-v1",
                "grading_latency_ms": grading_latency_ms,
            }
            prepared[index] = output
            prepared_by_id[aid] = output
        saved_records = []
        inserted_count = 0
        with closing(self.connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                if sync_checkpoint is not None:
                    saved = db.execute(
                        "SELECT state FROM sync_checkpoints WHERE scope=?",
                        (sync_checkpoint["scope"],),
                    ).fetchone()
                    previous = json.loads(saved[0]) if saved else None
                    if previous != sync_checkpoint["previous"]:
                        raise ValueError("Synchronization checkpoint changed; retry poll")
                for output in (prepared[index] for index in range(len(normalized))):
                    existing = db.execute(
                        "SELECT record FROM attempts WHERE attempt_id=?", (output["attempt_id"],)
                    ).fetchone()
                    if existing:
                        saved = json.loads(existing[0])
                        self.check_same(saved, output)
                        saved_records.append(saved)
                    else:
                        db.execute(
                            "INSERT INTO attempts VALUES(?,?,?,?,?,?,?)",
                            (
                                output["attempt_id"],
                                output["student_id"],
                                output["question_id"],
                                output["timestamp"],
                                output["source"],
                                output["assessment_id"],
                                json.dumps(output),
                            ),
                        )
                        saved_records.append(output)
                        inserted_count += 1
                if sync_checkpoint is not None:
                    db.execute(
                        "INSERT INTO sync_checkpoints VALUES(?,?) "
                        "ON CONFLICT(scope) DO UPDATE SET state=excluded.state",
                        (
                            sync_checkpoint["scope"],
                            json.dumps(sync_checkpoint["state"], sort_keys=True),
                        ),
                    )
                db.commit()
            except Exception:
                db.rollback()
                event("persistence_failed", error_type="transaction_rollback")
                raise
        event("persistence_completed", record_count=len(saved_records), status="committed")
        return (
            {"records": saved_records, "inserted_count": inserted_count}
            if include_commit_stats
            else saved_records
        )

    def checkpoint_state(self, scope):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT state FROM sync_checkpoints WHERE scope=?", (scope,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def attempt_for_student(self, attempt_id, student_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT record FROM attempts WHERE attempt_id=? AND student_id=?",
                (attempt_id, student_id),
            ).fetchone()
        if row is None:
            raise PermissionError("Feedback access denied")
        return json.loads(row[0])

    def records(self, student_id=None, as_of=None, *, before=False, course_id=_ALL_COURSES):
        if as_of is not None:
            as_of = utc_timestamp(as_of)
        with closing(self.connect()) as db:
            if student_id is None:
                rows = db.execute(
                    "SELECT record FROM attempts ORDER BY timestamp,attempt_id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT record FROM attempts WHERE student_id=? ORDER BY timestamp,attempt_id",
                    (student_id,),
                ).fetchall()
        records = [json.loads(row[0]) for row in rows]
        return [
            r
            for r in records
            if (course_id is _ALL_COURSES or r.get("course_id") == course_id)
            and (as_of is None or (r["timestamp"] < as_of if before else r["timestamp"] <= as_of))
        ]

    def profile(self, student_id, as_of=None, *, before=False, course_id=_ALL_COURSES):
        if student_id not in STUDENTS:
            raise ValueError("Unknown student")
        records = self.records(student_id, as_of, before=before, course_id=course_id)
        return self._profile_from_records(student_id, records)

    def _profile_from_records(self, student_id, records):
        grouped = defaultdict(list)
        for record in records:
            for concept in record["concepts"]:
                grouped[concept].append(record)
        try:
            _, provisional = load_graphs()
        except (OSError, ValueError, TypeError):
            provisional = None
        concepts = {}
        for concept, attempts in sorted(grouped.items()):
            correct = sum(a["grading"]["score"] for a in attempts)
            # Each question contributes its latest attempt, preventing retry volume dominance.
            latest = {
                a["question_id"]: a
                for a in attempts
                if a["grading"]["status"] in {"correct", "semantic_error"}
            }
            latest_correct = sum(a["grading"]["score"] for a in latest.values())
            estimate = (1 + latest_correct) / (2 + len(latest))
            errors = Counter(
                a["diagnosis"]["observed_error"] for a in attempts if not a["grading"]["score"]
            )
            concepts[concept] = {
                "attempt_count": len(attempts),
                "correct_count": correct,
                "incorrect_count": len(attempts) - correct,
                "last_attempt": attempts[-1]["timestamp"],
                "questions": sorted({a["question_id"] for a in attempts}),
                "observed_errors": dict(errors),
                "mastery_estimate": estimate,
                "denominator": len(latest),
                "prerequisites": (
                    provisional.prerequisites(concept, 2, True) if provisional else []
                ),
                "trajectory": [
                    {
                        "timestamp": a["timestamp"],
                        "question_id": a["question_id"],
                        "score": a["grading"]["score"],
                    }
                    for a in attempts
                ],
            }
        for concept, profile in concepts.items():
            profile["prerequisite_context"] = [
                {
                    "concept": prerequisite,
                    "mastery_estimate": concepts.get(prerequisite, {}).get("mastery_estimate"),
                    "status": "possible_gap"
                    if concepts.get(prerequisite, {}).get("mastery_estimate", 1) < 0.5
                    else ("observed" if prerequisite in concepts else "unobserved"),
                }
                for prerequisite in profile["prerequisites"]
            ]
        return {
            "student_id": student_id,
            "synthetic": True,
            "graph_status": "available" if provisional else "unavailable",
            "attempt_count": len(records),
            "concepts": concepts,
            "history": records,
            "model": "Beta(1,1) smoothing on latest result per linked question; unvalidated heuristic",
        }

    def analytics(self, *, course_id=_ALL_COURSES):
        records = self.records(course_id=course_id)
        questions = {}
        for qid in QUESTIONS:
            rows = [a for a in records if a["question_id"] == qid]
            questions[qid] = {
                "attempts": len(rows),
                "correct": sum(a["grading"]["score"] for a in rows),
            }
        errors = Counter(
            c
            for a in records
            if not a["grading"]["score"]
            for c in a["diagnosis"]["candidate_concepts"]
        )
        concept_profiles = defaultdict(list)
        for sid in STUDENTS:
            for c, p in self.profile(sid, course_id=course_id)["concepts"].items():
                concept_profiles[c].append(p["mastery_estimate"])
        result = {
            "synthetic": True,
            "student_count": len(STUDENTS),
            "attempt_count": len(records),
            "correct": sum(a["grading"]["score"] for a in records),
            "questions": questions,
            "associated_error_concepts": dict(errors.most_common()),
            "mean_mastery": {c: sum(v) / len(v) for c, v in concept_profiles.items()},
            "sources": dict(Counter(a["source"] for a in records)),
        }
        if course_id is not _ALL_COURSES:
            result["course_id"] = course_id
            result["student_count"] = len({a["student_id"] for a in records})
            result["attempt_ids"] = [a["attempt_id"] for a in records]
            error_evidence = defaultdict(list)
            sequences = defaultdict(list)
            for a in records:
                if not a["grading"]["score"]:
                    error_evidence[a["diagnosis"]["observed_error"]].append(a["attempt_id"])
                sequences[(a["student_id"], a["assessment_id"], a["question_id"])].append(a)
            result["observed_errors"] = dict(sorted(error_evidence.items()))
            result["improvements"] = [
                {
                    "student_id": key[0],
                    "assignment_id": key[1],
                    "question_id": key[2],
                    "from_attempt_id": previous["attempt_id"],
                    "to_attempt_id": current["attempt_id"],
                }
                for key, attempts in sorted(sequences.items())
                for previous, current in zip(attempts, attempts[1:])
                if not previous["grading"]["score"] and current["grading"]["score"]
            ]
        return result
