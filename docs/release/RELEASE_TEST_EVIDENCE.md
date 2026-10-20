# Release test evidence — 2026-10-20

Release validation is separated from historical claims. Local interpreter: Python 3.14.3; CI targets 3.11 and 3.13. Locked development versions include Ruff 0.17.0, mypy 2.4.0, Bandit 1.9.4, Playwright 1.64.0 and pip-audit 2.10.1. Build backend is setuptools 80.9.0. Exact dependency versions remain in `requirements-dev.txt`; no inference backend/model dependency is downloaded for this release.

| Gate | Current evidence |
|---|---|
| G0 source integrity | PASS for runtime candidate: clean worktree, complete-history Security scan; original dirty checkout preserved |
| G1 static/build | PASS: Ruff, formatting, scoped mypy (3 files), pip check/config, Bandit, code-only wheel, dependency and publication/security scans |
| G2 tests | PASS: runtime candidate 5c72693 has 330 tests passing in 83.621s; baseline 313 + 16 release regressions + 1 source-version regression |
| G3 browser/service | PASS locally: all 7 browser tests in 68.618s, including full upload/graph/assignment/student/EM/project/lineage and restart. Native PL must also pass final-head GitHub integration |
| G4 scientific integrity | PASS within sandbox scope: COUNT/grouping replays fall back, valid COUNT grades correctly, no answer leakage. Original InstructKG and learning outcomes NOT_RUN |
| G5 GitHub | Runtime-head CI/Security PASS; final consolidation head must have all three successful workflows, unchanged base, clear reviews/rules before merge |
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

## Accepted runtime source snapshot

Runtime source `5c726930894b24104b38f7205c9573f5aab06cf1` passes 330 unit/integration tests (83.621s) and 7 distinct browser tests (68.618s). Repeated full-browser executions are reported separately and are not additional distinct tests. [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39450613891) and [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39450613902) pass; [native integration](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39450613916) is a separate required gate. This evidence-only documentation update does not alter runtime code. Its final exact head receives new GitHub checks and local discovery before merge. Final main/tag/G6 outcomes live in the annotated tag and completed external handoff, avoiding a self-referential future commit SHA in committed reports.

Visual QA confirms grounding/analytics JSON no longer displays literal escaped quotes. It also identified generic deterministic concept suggestions still mentioning COUNT for the reproduced valid-count/grouping query. The final scoped correction narrows that fallback to row preservation and rejects unsupported structured COUNT/GROUP_BY candidate diagnoses as well as textual ones. The existing KG fallback integration regression now checks those valid components are not mislabeled; the 16 release regressions still pass. Test discovery remains 330 and the successor head must pass complete validation before merge.
