# Current verified status — Phase 2

Snapshot: 2026-10-14. Source snapshot and actual CI run URLs are in [verification.json](verification.json). A later documentation commit may follow the tested implementation snapshot. Status words: PASS = completed stated check; PARTIAL = implemented with material gaps; FAIL = actual unsuccessful check; BLOCKED = prerequisite/instruction prevents execution; NOT_RUN = not executed.

| Subsystem/check | Status | Actual evidence and scope |
|---|---|---|
| Original baseline | PASS | 43/43 original tests; five HTTP checks; baseline audit and local logs |
| Expanded public suite | PASS | 81/81 tests, zero fail/skip; final-public-tests.log; 55.002sec final local run |
| Actual research graph suite | PASS | 2/2 distinct original tests; research-tests.log; 469 judgments/121 nodes |
| PrairieLearn | PASS | Actual local course/assessment and three questions; five final browser submissions, feedback and retries; e2e/result.json |
| SQL grading | PASS | Independent A/B SQLite bags, safety/deadline tests and actual PL results |
| KG Mode A | PASS | Real pinned research JSONL loads with direction/provenance; original edges remain unreviewed |
| Instructor graph approval | NOT_RUN | No instructor review; local overlay UI alone is not approval |
| Provider implementation/contracts | PASS | Config, local mocked HTTP success/errors, validation/fallback tests; no live model proof |
| Live feedback inference | BLOCKED | User explicitly instructed keep inference blocked/no paid usage; zero calls |
| Deterministic comparison | PASS | 21 submissions ×3 modes =63 outputs, zero live_success; evaluation.log |
| CPU extraction import | PASS | Unmodified upstream main.py --help in isolated Linux CPU image with network disabled |
| CPU locked image build | PASS | Exact lock recipe rebuilt; unmodified upstream import passed again with network disabled; extraction-locked-build.log / extraction-locked-import.log |
| Fresh upstream ingestion | FAIL | Actual 600 seconds run exit124; parsing models initialized, no chunks written |
| KG Mode B complete extraction | BLOCKED | Ingest failure plus model-stage use forbidden; no concepts/roles/clusters/pairs/relations claimed |
| Profiles / analytics | PASS | Five synthetic students,37 records (19correct/18incorrect),15 source-separated PL imports; UI/API agreement and isolation tests |
| Persistence | PASS | Exact 15 PL IDs and37 normalized record hashes survive stop/start; restart.log/persistence-{before,after}.json |
| Static checks/build | PASS | Ruff/format, strict mypy on 3 boundaries, config/pip integrity,23-file code-only wheel |
| Security checks | PASS within scope | Zero final Bandit findings; no known dev-pin vulnerabilities at audit; full-history publication audit has no unreviewed findings |
| GitHub publication/CI | See verification.json | Authorized original source only; actual remote run status, not inferred from YAML |
| Hosted course / real-data pilot | BLOCKED | No institutional/research authorization; no existing course touched |

## Local evidence

`artifacts/phase2/` holds baseline and expanded logs, E2E result/screenshots/trace, exact restart comparison, scans/build logs and extraction failure. These are intentionally ignored; published sanitized summaries and public CI logs provide reviewable nonrestricted evidence. The E2E driver is rerunnable from public synthetic fixtures. A failed earlier selector run preserved five actual attempts; final CSV import therefore added ten to the 27-record baseline. Fixture/source counts are22 synthetic_fixture (including one earlier dashboard attempt) +15 local_prairielearn_export.

The local UI is at http://localhost:3000/pl and http://127.0.0.1:8080/. Loopback prototype health is not hosted deployment readiness. Model output quality and student learning effectiveness remain unverified.
