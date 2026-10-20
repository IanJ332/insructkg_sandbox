# Release test evidence — 2026-10-20

Release validation is separated from historical claims. Local interpreter: Python 3.14.3; CI targets 3.11 and 3.13. Locked development versions include Ruff 0.17.0, mypy 2.4.0, Bandit 1.9.4, Playwright 1.64.0 and pip-audit 2.10.1. Build backend is setuptools 80.9.0. Exact dependency versions remain in `requirements-dev.txt`; no inference backend/model dependency is downloaded for this release.

| Gate | Current evidence |
|---|---|
| G0 source integrity | Existing dirty checkout preserved; isolated candidate; publication/history audit required on final content |
| G1 static/build | Ruff, format, scoped mypy (3 configured files), pip check, config validation, Bandit, code-only wheel and vulnerability audit are run; final outcomes below |
| G2 tests | Initial current-plus-release run: 324 passed in 93.618s. Final suite must reconcile later added regressions; 313 is historical baseline, not current total |
| G3 browser/service | Initial 7-test run: 6 passed, 1 failed after a test provider change disabled async enqueue. Corrected test retains queue routing and deterministic worker. Subsequent 2-test rerun passed in 54.983s, including full upload/graph/assignment/student/EM/project/lineage and restart |
| G4 scientific integrity | Known stored COUNT and grouping response replays fall back; valid LEFT JOIN COUNT grades correct. Model guidance unreviewed; original InstructKG/learning outcomes NOT_RUN |
| G5 GitHub | Historical PR workflows green; consolidation exact-head workflows must pass separately before merge |
| G6 fresh main | NOT_RUN before merge; independent fresh-main clone/install/health/browser/restart required before tag |

The dedicated release regression file initially passes 13 tests, covering auth configuration matrix/HTTP role negatives, binary-key roundtrip, COUNT/grouping replay fallback, model-unreviewed state, concurrent graph versions, prior-only current/later attempts, ownership reconciliation, durable project review history and safe JSON escaping. Source-version substitution has a separate grounding regression.

Bandit initially reports zero findings; dependency audit reports no known vulnerabilities. Initial no-build-isolation wheel attempt failed because the existing environment lacked setuptools; a standard isolated build then succeeded, code-only wheel inventory 45 files. The initial secret scan detected two new fixed test-key strings; tests now generate ephemeral keys instead. No real credential was identified. Re-run publication scan against final source/history; do not treat the initial scan as PASS.

Original professor-video evidence remains external: qwen3:8b prompt v3, digest recorded in original manifest, model feedback 3687.953ms. This is historical measured inference latency, not fresh release inference or GPU throughput. Deterministic queue timings are never used as inference benchmarks.

Historical flaky workflow: [failed push](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39370903331), job 118458311580, timed out on `Logged in as instructor_alawini`. Key-byte trimming has a deterministic regression; repeated complete browser runs use fresh stores and unchanged global timeouts. This supports the fix without pretending the old log identifies its random key bytes.

Raw local logs, browser media and runtime stores stay under ignored candidate `artifacts/`. Final acceptance, exact candidate SHA/workflow links and repeated-run results are appended only after completion. Local Docker engine is unavailable, so native PL UI/Postgres checks are delegated to the required GitHub integration workflow rather than claimed locally.
