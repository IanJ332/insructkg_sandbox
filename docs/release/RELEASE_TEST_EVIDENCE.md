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

## Post-merge clean-room finding

Main `d1b4ea1` installed successfully into an independent new environment and completed the full synthetic browser workflow, but its test failed the separate MP4 recording gate (42.877s): the fresh environment had only Playwright's minimal VP9/WebM encoder. Both original actor WebMs decoded successfully; a full encoder was an undeclared test-environment dependency. Preserve this failed verification. The scoped follow-up accepts browser evidence only after all transition/lineage/restart assertions and valid original WebMs, explicitly leaving MP4 acceptance false when capability is absent. Full encoders retain the original strict MP4 gate. No test is deleted, no timeout increased, and no encoder/model dependency downloaded. A new exact-head CI and independent fresh-main verification remain mandatory before tagging.

## Conservative integration readiness — 2026-10-30

### Repository and consolidation scope

The open checkout at `C:\Users\ian\Desktop\PROJECT\insructkg_sandbox` started on
`feature/phase5-integrated-prototype`, SHA `5d1a3ece81b1009207054593971595ad6095e215`,
with nine modified tracked files and substantial untracked prototype work. It was
preserved. The older `C:\Users\ian\Desktop\PROJECT\instructkg` checkout has read-only
upstream/Jeffry reference remotes and was not repointed or modified.

Fetched development `origin/main` is `0f05ae011280837927ed5efe20fb42a7ebe9bb06`.
The isolated implementation checkout is
`C:\Users\ian\Desktop\PROJECT\insructkg_sandbox\artifacts\worktrees\consolidation`,
branch `codex/conservative-integration-readiness`. The sole synchronization target
is `git@github.com:IanJ332/insructkg_sandbox.git`. Final commit/push receipts belong
in the handoff and Git history, avoiding a self-referential future SHA here.

KEEP: existing modular services, SQL grader, native hooks, graph/source versions,
review, queue fencing, profiles, authorization, model transports and provenance.
SIMPLIFY: correct history selection within existing repositories, share the existing
profile calculation with batch preparation, and document one supported lifecycle.
DEFER: generalized concept mapping/full upstream extraction, institutional identity,
native dynamic publication, hosted operations and further EM/project development.
REMOVE: no runtime, tests, research records, dependencies or worktrees. No platform
rebuild, new service, schema column or model installation was needed.

Confirmed fixes: earlier same-batch attempts now inform later feedback; equal-time
ISO spellings cannot leak the current attempt; assignment and authorized replay
feedback stay within the student's course; old unknown-course records remain
replayable without guessed provenance; conflicting queue feedback modes fail;
grounding checks assignment question membership and compatible saved graph nodes.
Personalization badges reflect relevant minimized evidence rather than raw profiles.

### Fresh validation

Interpreter: existing Python 3.14.3 environment, reused without replacement for
the baseline. Final dependency verification uses a disposable environment at
`artifacts/validation-venv`; the existing environment remains untouched.
Commands run from the isolated checkout with `SIIP_ENV=development`,
`SIIP_ALLOW_SYNTHETIC_AUTH=1`, and `SIIP_DATA_DIR=$PWD\artifacts\public-data`.
The existing `scripts/init_public.py` prepared disposable synthetic fixtures.

| Check | Fresh result |
|---|---|
| Open dirty prototype baseline | 303 tests passed, 98.256s; preserved separately from main |
| Fetched main baseline | 330 tests passed, 104.393s |
| Focused data-flow/remediation checks | 59 tests passed, 24.551s |
| Final unit/integration discovery | 340 passed, 0 failed, 0 skipped, 101.742s in disposable environment |
| Full browser upload/review/version/assignment/submission/feedback/analytics/restart | Passed after correction, 47.677s |
| Final seven browser tests | 7 passed, 0 failed, 0 skipped, 72.007s in disposable environment; separate from unit totals |
| Ruff / format / mypy / pip check / validate_config | Passed; mypy retains its existing three-file scope |
| Bandit | Zero findings, existing configured exclusions retained |
| Publication audit | PASS, current prospective files and complete reachable history; no secret findings |
| Code-only wheel | Built and inspected: 45 files; no restricted graph, source or runtime data |
| Dependency vulnerability service | PASS after three pin updates: no known vulnerabilities found |
| Local native PrairieLearn UI/Postgres | BLOCKED: no Docker engine; native Python hook contracts covered by tests |
| Live Qwen evaluation | BLOCKED: local service unavailable; zero completed model-quality cases |

Test commands: `python -m unittest discover -s tests -v`; `python -m ruff check .`;
`python -m ruff format --check .`; `python -m mypy`; `python -m pip check`;
`python scripts/validate_config.py`; `python -m bandit -r
prairielearn-course/serverFilesCourse/siip scripts -c pyproject.toml`;
`python scripts/publication_audit.py`; `python -m pip wheel --no-deps . --wheel-dir
artifacts/dist`; `python scripts/check_wheel.py`; `python -m pip_audit -r
requirements-dev.txt --cache-dir artifacts/pip-audit-cache-final`.
Browser commands use the README full-browser opt-in and the integration workflow's
four legacy browser modules (six tests). Raw logs, databases and videos remain
ignored under this worktree's `artifacts/`.

Preserved failures: an initial strict subset check rejected a valid assignment
containing extra prerequisite nodes in the browser (29.539s). It was corrected to
require matching question tags while allowing additional saved graph nodes; no
test assertion/timeout was weakened. Initial packaging/dependency attempts hit
sandbox network/cache limits; the isolated wheel build succeeded after retry.

The fresh vulnerability service reported 26 advisory entries across three existing
locked dependencies. Only their reported fixed pins were changed:
[certifi 2026.10.18](https://pypi.org/project/certifi/2026.10.18/),
[filelock 4.2.1](https://pypi.org/project/filelock/4.2.1/) and
[pypdf 6.21.2](https://pypi.org/project/pypdf/6.21.2/).
These are development-lock maintenance, with no new application dependency.
The full locked install completed in the disposable environment.

A complete 340-test run before the dependency refresh had one Windows
`ConnectionAbortedError` in the existing hostile-origin negative test (99.921s).
This matches the release's earlier documented transport intermittency; a focused
rerun passed in 0.562s. The failure is retained under ignored raw logs. No exception
was ignored and no assertion or timeout was changed. A clean complete final run
is reported independently below.

Final disposable-environment acceptance: **340 unit/integration tests passed in
101.742s**, **7 browser tests passed in 72.007s**, no failures or skips. Strict
browser lineage/restart assertions passed with valid original WebMs; optional
MP4 packaging was unavailable and is not claimed. Ruff, formatting, scoped mypy,
pip check and configuration passed. The updated lock's vulnerability scan found
no known vulnerabilities. Publication scanning covered prospective files and
complete reachable history with no secret findings. Independent review and final
diff inspection found no unresolved blocker or important issue. Raw evidence is
retained in `artifacts/disposable-final-{tests,browser}.log`,
`artifacts/dependency-audit-accepted.json` and `artifacts/publication-audit-final.log`.

### Local model preservation and independent review

Ollama client is 0.17.7. CLI list/show attempts could not reach a running service;
`GET http://127.0.0.1:11434/api/tags` was refused. The existing read-only
`scripts/check_local_model.py --probe` reported valid local configuration and
unavailable metadata. Requested model remains `qwen3:8b`; actual installed digest,
quantization, family and effective runtime loading configuration are UNKNOWN.
No model download, migration, cache deletion or configuration overwrite occurred.

Existing launcher settings remain unchanged: Ollama `/v1`, native Ollama transport,
60s feedback timeout, 500 generated tokens, temperature 0.1, context 8192;
local extraction defaults to 120s, 2400 tokens, temperature 0, context 8192.
Feedback prompt remains `siip-feedback-v4`. Deterministic mode and COUNT/GROUP BY,
NULL, unsupported-diagnosis, leakage and provider-error regression protections
remain. These contract tests do not establish Qwen quality or inference latency.

Independent reviewer: GPT-6.1 Terra, High. Reviewed the actual diff for isolation,
cutoffs, graph provenance, idempotence, compatibility, security, complexity, Git
destination and model preservation. The important legacy replay compatibility
finding was fixed and regression tested; focused re-review found no remaining
blocker or important defect. Model/provider replacement was absent. No generated
Qwen responses were available for independent output screening. A pre-existing
worker limitation remains: history-resolution errors degrade to unavailable
history; this is not a substitute for hosted provenance/access qualification.

### Pinned read-only comparison and readiness matrix

[Original source](https://github.com/aalrabah/instructkg/tree/ade6263a348984cef848eae85dc3d3b15daeea09)
uses `master`, SHA `ade6263a348984cef848eae85dc3d3b15daeea09`.
Its extraction/role aggregation, pair-packet temporal/co-occurrence evidence and
relation selection were inspected. Existing relation/schema adapters are retained;
the local extractor is not relabeled as this full pipeline.
[Jeffry reference](https://github.com/code-royce/instructkg/tree/c34a7786528e78766f15d918ab17aca2a9f7dc0b)
is branch `jeffry`, SHA `c34a7786528e78766f15d918ab17aca2a9f7dc0b`.
README, findings, adapters, evaluation and review-packet code were inspected.
OCR coverage versus accuracy, measured/pinned runs, separate node/triplet scoring
and seeded instructor sampling remain useful research patterns. Importing vLLM,
other models or packet dependencies adds no value to this history fix; none was
borrowed or installed. Both references remained read-only.

| Area | Local development | IanJ332 GitHub baseline | Upstream reference | Jeffry reference | Status |
|---|---|---|---|---|---|
| Architecture | Existing modules retained | Main foundation preserved | Multi-stage extraction | Local research additions | ALIGNED |
| Knowledge graph | Reviewed saved graph grounding | Existing local adapter | Full pedagogical pipeline | Extraction/evaluation tooling | INTENTIONAL EXTENSION; full pipeline DEFERRED |
| Versioning | Immutable source/graph checks retained | Existing snapshots retained | Output artifacts | Run/output reproducibility | ALIGNED |
| Student Profile | Batch/time/course fixes | Narrow correction to main | No integrated learner lifecycle established | No equivalent verified here | UPDATED |
| Feedback | Relevant prior/course evidence | Existing modes/guards retained | Extraction model use | Research evaluation model use | UPDATED |
| Local Qwen integration | Configuration preserved; service absent | Ollama path retained | Different model/provider options | vLLM examples not imported | ALIGNED configuration; live BLOCKED |
| PrairieLearn integration | Four hooks/contracts preserved | Existing native integration CI | No equivalent bridge established | No equivalent bridge established | ALIGNED contracts; local native UI BLOCKED |
| Tests | Existing suite plus focused regressions | Exact branch checks required | Separate pipeline research | Separate quality harness | UPDATED |
| Documentation | Existing release docs updated | Scientific boundaries preserved | Read-only source comparison | Read-only findings comparison | UPDATED |

Available exercised path: synthetic lesson → reviewed saved KG version → canonical
question/selected-node binding → deterministic attempts → durable profile and
queue → deterministic feedback/fallback → learner UI/instructor analytics.
The Qwen-generation stage and authentic PrairieLearn deployment were not exercised.
No pedagogical validation, learning improvement or production readiness is claimed.
