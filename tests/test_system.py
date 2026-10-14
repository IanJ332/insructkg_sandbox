import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.feedback import (
    CompatibleProvider,
    build_context,
    diagnosis,
    generate_feedback,
    valid_output,
)
from siip.grader import QUESTIONS, bag, grade, public_grade, run_query
from siip.graph import ConceptGraph
from siip.sources import AuthorizedPrairieLearnAPISource, normalize_pl, pseudonym
from siip.store import STUDENTS, SubmissionRepository, utc_timestamp


class SQLTests(unittest.TestCase):
    def test_references_on_both_datasets(self):
        for qid, q in QUESTIONS.items():
            with self.subTest(qid=qid):
                self.assertEqual(grade(qid, q["reference_sql"])["status"], "correct")

    def test_initialization_and_edges(self):
        self.assertEqual(len(run_query("SELECT * FROM Employees", "A")["rows"]), 4)
        self.assertEqual(len(run_query("SELECT * FROM Employees", "B")["rows"]), 7)
        self.assertEqual(
            run_query("SELECT department_id FROM Employees WHERE name='Gina'", "B")["rows"], [[99]]
        )

    def test_expected_outputs_match(self):
        expected = json.loads((ROOT / "datasets/questions/expected_outputs.json").read_text())
        for qid, q in QUESTIONS.items():
            for dataset in ["A", "B"]:
                self.assertEqual(
                    run_query(q["reference_sql"], dataset)["rows"], expected[qid][dataset]
                )

    def test_wrong_join_type(self):
        self.assertEqual(
            grade("sql_join_02", QUESTIONS["sql_join_01"]["reference_sql"])["observation"],
            "missing_unmatched_rows",
        )
        self.assertEqual(
            grade("sql_join_01", QUESTIONS["sql_join_02"]["reference_sql"])["status"],
            "semantic_error",
        )

    def test_missing_join_condition(self):
        self.assertEqual(
            grade("sql_join_01", "SELECT e.name,d.department_name FROM Employees e, Departments d")[
                "status"
            ],
            "semantic_error",
        )

    def test_incorrect_column(self):
        self.assertEqual(
            grade(
                "sql_join_01",
                "SELECT e.name,d.department_name FROM Employees e JOIN Departments d ON e.employee_id=d.department_id",
            )["status"],
            "semantic_error",
        )

    def test_null_equality(self):
        self.assertEqual(
            grade("sql_join_03", "SELECT name FROM Employees WHERE department_id = NULL")["status"],
            "semantic_error",
        )

    def test_null_fk_only_catches_dataset_b(self):
        r = grade("sql_join_03", "SELECT name FROM Employees WHERE department_id IS NULL")
        self.assertTrue(r["datasets"][0]["correct"])
        self.assertFalse(r["datasets"][1]["correct"])
        self.assertEqual(r["observation"], "missing_nonnull_unmatched_reference")

    def test_not_exists_alternative(self):
        self.assertEqual(
            grade(
                "sql_join_03",
                "SELECT e.name FROM Employees e WHERE NOT EXISTS (SELECT 1 FROM Departments d WHERE d.department_id=e.department_id)",
            )["status"],
            "correct",
        )

    def test_syntax_distinct_from_runtime(self):
        self.assertEqual(
            grade("sql_join_01", "SELECT FROM Employees")["status"], "compilation_error"
        )
        self.assertEqual(
            grade("sql_join_01", "SELECT nope FROM Employees")["status"], "execution_error"
        )
        self.assertEqual(grade("sql_join_01", "SELECT * FROM absent")["status"], "execution_error")

    def test_duplicate_bag(self):
        self.assertNotEqual(bag([[1], [1]]), bag([[1]]))
        q = QUESTIONS["sql_join_01"]["reference_sql"].rstrip(";")
        self.assertEqual(grade("sql_join_01", q + " UNION ALL " + q)["status"], "semantic_error")

    def test_row_order_ignored(self):
        q = QUESTIONS["sql_join_01"]["reference_sql"].rstrip(";") + " ORDER BY e.name DESC"
        self.assertEqual(grade("sql_join_01", q)["status"], "correct")

    def test_unsafe_rejected(self):
        for sql in [
            "DROP TABLE Employees",
            "DELETE FROM Employees",
            "ATTACH DATABASE '/tmp/x' AS bad",
            "PRAGMA database_list",
            "SELECT 1; DROP TABLE Employees",
            "WITH x AS (SELECT 1) DELETE FROM Employees",
            "SELECT load_extension('/tmp/x')",
            "SELECT readfile('/etc/passwd')",
            "SELECT * FROM sqlite_master",
        ]:
            with self.subTest(sql=sql):
                self.assertEqual(run_query(sql, "A")["status"], "unsupported_query")

    def test_comments_and_quoted_semicolons(self):
        self.assertEqual(run_query("/* comment */ SELECT ';'", "A")["status"], "ok")

    def test_single_select_cte(self):
        self.assertEqual(
            run_query("WITH x AS (SELECT name FROM Employees) SELECT name FROM x", "A")["status"],
            "ok",
        )

    def test_resource_bound(self):
        q = "WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x) SELECT max(n) FROM x"
        r = run_query(q, "A", timeout=2, deadline_seconds=0.02)
        self.assertEqual(r["status"], "execution_error")

    def test_parent_deadline(self):
        self.assertEqual(run_query("SELECT 1", "A", timeout=0.000001)["status"], "execution_error")

    def test_row_cap_and_function_limit(self):
        q = "WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x WHERE n<2000) SELECT n FROM x"
        self.assertEqual(run_query(q, "A")["status"], "execution_error")
        self.assertEqual(
            run_query("SELECT randomblob(1000000000)", "A")["status"], "unsupported_query"
        )

    def test_clean_state(self):
        run_query("DELETE FROM Employees", "A")
        self.assertEqual(len(run_query("SELECT * FROM Employees", "A")["rows"]), 4)

    def test_public_evidence_hides_answers(self):
        r = public_grade(grade("sql_join_02", QUESTIONS["sql_join_01"]["reference_sql"]))
        self.assertEqual(set(r), {"status", "score", "observation"})


class GraphTests(unittest.TestCase):
    def fixture(self, records, reviews=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        p = Path(directory.name) / "g.jsonl"
        p.write_text("\n".join(json.dumps(r) if not isinstance(r, str) else r for r in records))
        return ConceptGraph(p, reviews=reviews)

    def rec(self, a="A", b="B", rel="depends_on"):
        return {
            "A": {"name": a, "role": "Definition"},
            "B": {"name": b, "role": "NA"},
            "relation": rel,
            "evidence_chunks": [{"chunk_id": "x", "text": "evidence"}],
            "justification": "test",
        }

    def test_normalization_and_nulls(self):
        g = self.fixture([self.rec(rel="Depends On"), self.rec(rel=None), self.rec(rel="None")])
        self.assertEqual(g.records[0]["relation"], "depends_on")
        self.assertIsNone(g.records[1]["relation"])

    def test_invalid_missing_and_duplicates(self):
        g = self.fixture([self.rec(), self.rec(), self.rec(a=""), "{oops", self.rec(rel="made_up")])
        self.assertEqual(len(g.errors), 3)
        self.assertEqual(len(g.nodes), 2)
        self.assertEqual(len(g.duplicates), 1)
        self.assertEqual(len(g.edges(True)), 1)

    def test_bad_inference_not_edge(self):
        r = self.rec()
        r["_meta"] = {"_error": "bad output"}
        self.assertEqual(self.fixture([r]).edges(True), [])

    def test_review_overlay(self):
        g = self.fixture([self.rec()])
        rid = g.records[0]["id"]
        reviews = {rid: {"status": "accepted", "reviewer": "test"}}
        g = ConceptGraph(g.path, reviews=reviews)
        self.assertEqual(len(g.edges()), 1)
        g = ConceptGraph(g.path, reviews={rid: {"status": "rejected"}})
        self.assertEqual(g.edges(True), [])
        g = ConceptGraph(
            g.path,
            reviews={
                rid: {
                    "status": "modified",
                    "source": "B",
                    "target": "A",
                    "relation": "part_of",
                    "reviewer": "test",
                    "reason": "fix",
                }
            },
        )
        self.assertEqual(g.edges()[0]["source"], "B")
        self.assertEqual(g.records[0]["original_direction"], ["A", "B"])

    def test_bounded_cycle_traversal(self):
        g = self.fixture([self.rec(), self.rec("B", "C"), self.rec("C", "A")])
        self.assertEqual(g.prerequisites("A", 1, True), ["B"])
        self.assertEqual(g.prerequisites("A", 4, True), ["B", "C"])
        self.assertEqual(g.prerequisites("missing", 2, True), [])
        with self.assertRaises(ValueError):
            g.prerequisites("A", 9)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.qid = "sql_join_02"
        self.sql = QUESTIONS["sql_join_01"]["reference_sql"]
        self.result = grade(self.qid, self.sql)

    def test_distinct_contexts(self):
        a, b, c = [
            build_context(self.qid, self.sql, self.result, m) for m in ["baseline", "rag", "kg"]
        ]
        self.assertNotIn("lecture_evidence", a)
        self.assertNotIn("target_concepts", a)
        self.assertIn("lecture_evidence", b)
        self.assertNotIn("development_relationships", b)
        self.assertIn("existing_research_judgments", c)
        self.assertIn("prerequisites", c)
        self.assertTrue(
            all(
                e.get("source_pdf", "").endswith(".pdf")
                or e.get("source_kind") == "synthetic_contract_fixture"
                for e in b["lecture_evidence"]
            )
        )
        for ctx in [a, b, c]:
            self.assertNotIn("expected", json.dumps(ctx))
            self.assertNotIn("Gina", json.dumps(ctx))

    def test_fallback_structured_and_model_logging(self):
        f = generate_feedback(self.qid, self.sql, self.result)
        self.assertEqual(f["inference_status"], "deterministic_fallback")
        self.assertEqual(f["model_identifier"], "deterministic-rules-v1")
        self.assertEqual(f["non_revealing_validation"], "passed_rule_filter")
        self.assertNotIn("SELECT", f["feedback_text"])
        self.assertIsNone(f["token_usage"])

    def test_invalid_or_leaking_provider(self):
        class Bad:
            model = "test"

            def generate(self, context):
                return {
                    "feedback_text": "SELECT e.name FROM Employees e",
                    "candidate_concepts": [],
                    "evidence_references": [],
                }, None

        f = generate_feedback(self.qid, self.sql, self.result, provider=Bad())
        self.assertEqual(f["inference_status"], "provider_error_fallback")

    def test_provider_timeout(self):
        class Slow:
            model = "test"

            def generate(self, context):
                raise TimeoutError("secret text")

        f = generate_feedback(self.qid, self.sql, self.result, provider=Slow())
        self.assertEqual(f["error_details"], "TimeoutError")
        self.assertNotIn("secret", json.dumps(f))
        self.assertEqual(self.result["score"], 0)

    def test_invalid_schema_fake_citation_and_concepts(self):
        ctx = build_context(self.qid, self.sql, self.result, "kg")
        for obj in [
            {},
            {
                "feedback_text": "Try reasoning about preserved rows.",
                "candidate_concepts": [],
                "evidence_references": ["fake:page"],
            },
            {
                "feedback_text": "Try reasoning about preserved rows.",
                "candidate_concepts": ["FAKE"],
                "evidence_references": [],
            },
        ]:
            with self.assertRaises(ValueError):
                valid_output(obj, ctx, self.qid)

    def test_no_paid_use_by_default(self):
        with self.assertRaises(ValueError):
            CompatibleProvider("https://api.example.com/v1", "model")

    def test_diagnosis_not_calibrated(self):
        d = diagnosis(self.qid, self.result)
        self.assertIsNone(d["diagnosis_confidence"])
        self.assertIn("Possible", d["interpretation"])


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = SubmissionRepository(Path(self.tmp.name) / "db.sqlite3")

    def attempt(self, aid="a", sid="S003", sql=None, timestamp="2026-10-13T10:00:00-05:00"):
        return {
            "attempt_id": aid,
            "student_id": sid,
            "question_id": "sql_join_02",
            "timestamp": timestamp,
            "submitted_sql": sql or QUESTIONS["sql_join_01"]["reference_sql"],
            "source": "synthetic_fixture",
        }

    def test_multi_attempts_improve_latest_mastery(self):
        self.repo.process(self.attempt())
        before = self.repo.profile("S003")["concepts"]["LEFT_OUTER_JOIN"]["mastery_estimate"]
        self.repo.process(
            self.attempt(
                "b", sql=QUESTIONS["sql_join_02"]["reference_sql"], timestamp="2026-10-13T16:00:00Z"
            )
        )
        p = self.repo.profile("S003")["concepts"]["LEFT_OUTER_JOIN"]
        self.assertEqual(p["attempt_count"], 2)
        self.assertEqual(p["correct_count"], 1)
        self.assertEqual(p["denominator"], 1)
        self.assertGreater(p["mastery_estimate"], before)
        self.assertEqual(self.repo.profile("S001")["history"], [])

    def test_persistence_idempotence_collision(self):
        a = self.attempt()
        self.repo.process(a)
        self.repo.process(a)
        self.assertEqual(SubmissionRepository(self.repo.path).analytics()["attempt_count"], 1)
        with self.assertRaises(ValueError):
            self.repo.process({**a, "student_id": "S002"})

    def test_timestamp_and_identity_validation(self):
        self.assertEqual(utc_timestamp("2026-10-13T10:00:00-05:00"), "2026-10-13T15:00:00+00:00")
        with self.assertRaises(ValueError):
            utc_timestamp("2026-10-13T10:00:00")
        with self.assertRaises(ValueError):
            self.repo.process(self.attempt(sid="real-person"))

    def test_fixture_data_integrity(self):
        fixtures = json.loads((ROOT / "datasets/synthetic-submissions/attempts.json").read_text())
        self.assertGreaterEqual(len(fixtures), 18)
        self.assertEqual(len({a["attempt_id"] for a in fixtures}), len(fixtures))
        for a in fixtures:
            self.assertIn(a["question_id"], QUESTIONS)
            self.assertIn(a["student_id"], STUDENTS)
            utc_timestamp(a["timestamp"])
        for qid in QUESTIONS:
            self.assertTrue((ROOT / "prairielearn-course/questions" / qid / "info.json").exists())

    def test_api_mapping_minimizes_identifiers(self):
        row = {
            "user_id": "1",
            "question_name": "sql_join_02",
            "submitted_answer": {"sql": "SELECT 1"},
            "submission_id": "5",
            "date": "2026-10-13T10:00:00Z",
            "assessment_id": "1",
            "assessment_instance_id": "2",
            "variant_id": "3",
            "user_name": "Do not store",
            "user_uid": "hidden",
            "user_uin": "hidden",
            "score": 0,
        }
        result = normalize_pl(row, {"1": "S003"})
        self.assertNotIn("user_name", result)
        self.assertNotIn("user_uid", result)
        with self.assertRaises(ValueError):
            normalize_pl(row, {})
        with self.assertRaises(PermissionError):
            AuthorizedPrairieLearnAPISource("http://localhost:3000", "", 1, 1, {})
        self.assertEqual(pseudonym(1, b"x" * 32), pseudonym(1, b"x" * 32))


class PrairieLearnHookTests(unittest.TestCase):
    def test_actual_question_hooks_share_engine(self):
        for qid, q in QUESTIONS.items():
            spec = importlib.util.spec_from_file_location(
                qid, ROOT / "prairielearn-course/questions" / qid / "server.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            data = {
                "params": {},
                "correct_answers": {},
                "submitted_answers": {"sql": q["reference_sql"]},
                "partial_scores": {},
                "feedback": {},
            }
            mod.generate(data)
            self.assertNotIn("SELECT", json.dumps(data["params"]))
            mod.grade(data)
            self.assertEqual(data["score"], 1)
            self.assertIn("guidance", data["feedback"])
            data["submitted_answers"]["sql"] = "SELECT 1"
            mod.grade(data)
            self.assertEqual(data["score"], 0)


class AdditionalBoundaryTests(unittest.TestCase):
    def test_compile_error_does_not_assert_join_gap(self):
        result = grade("sql_join_02", "SELECT FROM Employees")
        self.assertEqual(diagnosis("sql_join_02", result)["candidate_concepts"], [])

    def test_concept_gap_claim_rejected_for_correct_answer(self):
        result = grade("sql_join_02", QUESTIONS["sql_join_02"]["reference_sql"])
        ctx = build_context("sql_join_02", QUESTIONS["sql_join_02"]["reference_sql"], result, "kg")
        with self.assertRaises(ValueError):
            valid_output(
                {
                    "feedback_text": "Revisit the preservation of employee rows.",
                    "candidate_concepts": ["LEFT_OUTER_JOIN"],
                    "evidence_references": [],
                },
                ctx,
                "sql_join_02",
            )

    def test_syntax_failure_excluded_from_mastery_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SubmissionRepository(Path(tmp) / "p.sqlite3")
            repo.process(
                {
                    "attempt_id": "x",
                    "student_id": "S005",
                    "question_id": "sql_join_01",
                    "timestamp": "2026-10-14T10:00:00Z",
                    "submitted_sql": "SELECT FROM Employees",
                }
            )
            p = repo.profile("S005")["concepts"]["INNER_JOIN"]
            self.assertEqual(p["denominator"], 0)
            self.assertEqual(p["mastery_estimate"], 0.5)
