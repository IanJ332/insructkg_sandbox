# Issues and failed experiments

| Issue | Evidence/investigation | Resolution/status |
|---|---|---|
| Initial workspace not a root Git repository; remote not empty | Baseline audit, remote README 2288d9d | Preserved remote history; recovery commit, no force push |
| Per-row CSV writes before score validation | Baseline store/import source | Fixed atomic prepare/check/transaction; rollback/collision tests |
| Concurrent duplicate race and temporal future history | Baseline source | Fixed lock/transaction duplicate recheck and as-of profile; tests pass |
| Invalid HTTP body reset/drop, missing imports during development | Intermediate hardening test logs | Fixed length/close responses, safe error paths/imports; nine API contract tests pass |
| Valid graph modified endpoint appears later | Baseline loader single-pass check | Precollect endpoints; non-object rows and evidence warnings handled |
| Sandbox socket permission caused test failures | Initial local HTTP tests denied bind | Reran authorized local socket tests with appropriate execution permission; application unchanged for that environment failure |
| Intel Mac/Python 3.13 no compatible torch wheel | Extraction preflight/resolver logs | Isolated Linux Python 3.11 CPU image imports upstream; no algorithm patch |
| Upstream PDF ingestion exceeds 600 seconds | fresh-ingest.log; exit 124; no chunks | Open; 2 CPU / 5 GiB budget exhausted after parsing-weight initialization; generative stages not attempted |
| PL cold asset compilation initially exceeded readiness | PL logs, first E2E failure | Startup waits on health for 300sec; warm E2E passed |
| E2E total-score exact text selector ignored DOM whitespace | e2e-selector-failure.log after five real attempts | Regex whitespace assertion fixed; final full E2E PASS; prior attempts retained/imported |
| Bandit flagged SHA1 scanner identifier calculation | bandit.json development finding B324 | Explicit usedforsecurity=False for nonsecurity detector identifiers; rerun required |
| No authorized live feedback/extraction model | User explicitly says keep inference blocked/no paid usage | BLOCKED, never mock as success |
| Research graph orphan-card/OCR/direction concerns | Pinned upstream findings and baseline audit | Remain review risks; do not silently alter research algorithm |

New failures from GitHub runs are appended with run IDs and corrective commits. Local raw logs/exports stay excluded from publication.

## Actual GitHub first-run findings

CI run 38635364492 failed only the Python 3.11 dependency installation: local freeze selected pyee 14 requiring Python >=3.12. Pinning compatible pyee 13.0.1 satisfies Playwright's >=13,<15 contract on both tested Pythons. Security run 38635364514 passed. Slow integration run 38635364319 exposed SameFileError when the public fixture target equals its source course-data directory; skip identical copies and refuse replacement of an existing real graph. Reruns, not initial workflow creation, establish final CI status. The root ignore pattern research/ was anchored to /research/ so the requested docs/research/ is publishable while upstream checkouts remain excluded.

The public-only smoke path also needed explicit fixture awareness: the original smoke asserted469 real graph judgments, which is inappropriate for the distinct 2-record public contract graph. It now validates the declared corpus mode and labels it; the graph UI exposes synthetic provenance instead of describing that fixture as extracted multi-lecture output. No real-graph assertion was relaxed in the separate research tests.
