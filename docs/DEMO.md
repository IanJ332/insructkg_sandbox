# Repeatable local demonstration

Run `make demo`. Open http://localhost:3000/pl, Load from disk, choose SIIP SQL → Fall 2026 Synthetic Sandbox → SQL Concept-Aware Feedback Sandbox. Choose Student view. Keep the separate analytics page at http://127.0.0.1:8080 open. All data are synthetic; feedback defaults to deterministic fallback.

## 1. Actual platform and correct SQL

Open the INNER JOIN question, enter the following **staff demo answer** and click Save & Grade after the text input settles:

```sql
SELECT e.name, d.department_name
FROM Employees e JOIN Departments d
ON e.department_id=d.department_id;
```

Verify a new submitted-answer panel and 100%. Merely typing or clicking without a new panel is not a successful test. Reference answers in this guide are for the developer demonstration, not shown by the student feedback.

## 2. Incorrect JOIN, diagnosis, evidence, feedback and retry

Open Keep every employee. Submit the INNER JOIN query above. Verify 0%, semantic_error and guidance about omitted unmatched employees. Inspect the possible concepts and lecture page citation; these do not imply a confirmed mental-state diagnosis.

In analytics Graph review, inspect LEFT_OUTER_JOIN/JOIN_OPERATION records and their original evidence/direction. The questioned composition stays unreviewed, and separate developer edges show provisional prerequisites. Return to PL, replace JOIN with LEFT JOIN, and submit again. Verify 100% and the retained first 0% attempt.

## 3. Missing matches beyond a NULL reference

Open the third question. Submit `SELECT name FROM Employees WHERE department_id IS NULL;`. Verify 0% and guidance distinguishing a missing foreign-key value from a missing department match. This query happens to pass A but fails B. The student feedback does not reveal hidden rows.

Retry with a correct anti-match approach, for example:

```sql
SELECT e.name FROM Employees e
LEFT JOIN Departments d ON e.department_id=d.department_id
WHERE d.department_id IS NULL;
```

Verify 100% and preserved history. Assessment overview should show all three questions. The originally recorded run has actual PL submission IDs 1–5; new runs will use new IDs.

## 4. Synthetic profile and comparison

Analytics Students → S003 shows its fixture trajectory plus imported real local PL attempts (source labels remain separate). Concept estimates are unvalidated heuristics, and syntax failures do not establish concept gaps.

Feedback lab shows the same wrong LEFT JOIN task answer under baseline, RAG and KG contexts. All default outputs are labeled deterministic_fallback. `make evaluate` writes 63 paired records and a comparison report; zero live successes is expected until a real local model resource is configured. Do not describe this as an LLM benchmark.

## 5. New submission updates

A new PL submission updates its real history immediately. From the SIIP assessment's instructor Downloads tab, download all_submissions.csv, place it at artifacts/pl_all_submissions.csv, and run:

```sh
.venv/bin/python scripts/import_pl.py artifacts/pl_all_submissions.csv --local-synthetic-only
```

Refresh analytics. New actual PL attempt IDs are added, duplicates are ignored, and S003's profile/aggregate counts update. Export/import is an explicit step, not an automatic production API connection. Normalized records omit raw identities.

Alternatively, use the explicitly labeled Add a synthetic attempt form in S003 to demonstrate immediate shared-engine/storage updates. This form is a fixture demo and must not be called a PL submission.

## 6. Restart

`make stop` then `make start` preserves the project PostgreSQL volume and synthetic SQLite database. Refresh both pages; earlier PL submissions and profiles should remain. Load from disk is needed only if JSON content changed. Screenshots, test output, manifests and status evidence are in artifacts/. `make reset` preserves a backup of the synthetic store and retains PL history; use PL's Regenerate your assessment instance control only when deliberately starting a fresh local trial.
