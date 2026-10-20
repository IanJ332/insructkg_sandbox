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

## Completed candidate verification and final review

Candidate `fee6cca1cb51f0bdce07db68a82dc614eb9bc853`: **328 unit/integration tests PASS in 86.978s**; exact-commit complete browser/restart **1 PASS in 45.807s**. Earlier bounded full-browser repeats passed in 45.174s and 45.005s; the corrected six-test legacy browser suite passed in 22.383s. Ruff/format/scoped mypy/pip check/config/Bandit passed; publication scan covered current files and complete reachable history with zero secret findings. Dependency audit found no known vulnerabilities. Standard isolated wheel build/inventory passed (45 library files). Windows launcher health and receipt-verified stop passed; process inspection required execution outside the Codex sandbox on this host.

Independent final read-only reviews identified a separate feedback-session verifier missing the synthetic-auth gate, provisional-identity history ambiguity, q04 error-specific fallback ordering, relative-output normalization and stale inherited model digest. These are corrected before final-head acceptance. The release regression file now passes **16** focused tests, including feedback-route auth denial, provisional-history fail-closed and compilation-guidance preservation. These changes increase discovery to 330 tests; that count is not a PASS claim until final full discovery completes.

[Consolidation PR #4](https://github.com/IanJ332/insructkg_sandbox/pull/4) targets main and preserves history. Earlier candidate [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39449467116) and [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39449467185) passed; successor head must receive its own successful checks before merge. Final exact head/workflow URLs and G6 fresh-main results are recorded in the annotated release tag and external final handoff after completion (`git show siip-sandbox-v1.0` when created).

Candidate `5c6a71a`: CI and Security passed; all seven browser tests passed locally in 68.523s. The 330-test local run had one Windows `ConnectionAbortedError` in the existing hostile-origin negative test; it is retained as a failed run, not called PASS. Five bounded isolated reruns of that exact negative test passed with no timeout/expectation changes. A complete successor suite is required. Final provenance reconciliation also records effective/attempted provider and requested model in feedback and retains every graph review decision in the saved graph history. The 16 focused release tests pass after these additions.
