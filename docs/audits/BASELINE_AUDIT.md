# Phase 2 baseline audit — 2026-10-14

This audit independently re-ran the existing workspace, not merely the previous report.

- Workspace /Users/ian/Desktop/InstructKG had no top-level Git repository. Three nested detached research checkouts remain isolated under research/. Their recorded pins match the user-supplied Jeffry/reference commits; PrairieLearn source is independently pinned from the runtime image.
- Public destination IanJ332/insructkg_sandbox verified with gh repo view. main already contains commit 2288d9dde881490e1effdf130496524dcc8c08d7 and README.md; preserve this history. It is not empty at this audit.
- .venv Python 3.13 contains pypdf==6.1.1 only. Integration runtime otherwise uses the standard library. Optional extraction dependencies remain separate.
- Baseline command: .venv/bin/python -m unittest discover -s tests -v. All original 43 tests reproduced (artifacts/phase2/baseline-tests.log). .venv/bin/python scripts/smoke.py reproduced five HTTP checks (baseline-http.log). Browser independently confirmed real PL assessment 3/3, three questions, five stored submission histories; dashboard confirmed five synthetic students and 27 records, 13 correct.
- Docker Compose project siip-sandbox is healthy, digest pinned, loopback 3000. Correct active data volume is pl-postgres-data at /var/postgres; an unused earlier pl-postgres volume is preserved. Dashboard listens on loopback 8080 with a PID file.
- Recovery points: artifacts/phase2/baseline-source-local-only.zip, baseline-synthetic.sqlite3 and baseline-pl.dump. All remain local-only. Original artifacts/logs are preserved. No upstream source or history was changed.

## Concrete gaps found in code

- store.py checks then inserts in separate connections: concurrent duplicates can raise IntegrityError rather than converge. It accepts arbitrary extra input fields, weakening minimization. Out-of-order history supplied to feedback includes future attempts. ID collisions do not compare timestamp/source/assessment scope.
- import_pl.py persists each row before checking the exported PL score. A mismatch or later invalid row can leave a partial import. There is no atomic batch boundary.
- dashboard.py parses Content-Length and UTF-8 outside exception handling; malformed inputs and storage failures can drop HTTP connections. Host/DNS-rebinding checks, idempotent API POST, structured logs and detailed health are missing.
- graph.py validates modified endpoints against nodes seen so far; references to valid later nodes are falsely rejected. Non-object records can crash the loader; missing files/evidence require explicit diagnostics.
- feedback.py has a local-compatible client but no configured approved remote-provider path/retry/cost controls; retrieval ignores submitted error terms, source failures can abort grading; PL hook does not isolate optional feedback failure from deterministic score. Baseline/RAG/KG must remain comparable.
- Existing tests exercise direct hooks but do not automate the whole PL UI → export → atomic ingestion → analytics path. Public CI must use original synthetic contract fixtures and never package course PDF/real graph evidence.
- No CI, lint/type/security configuration or public publication allowlist exists. Old .gitignore would allow screenshots/logs/research output artifacts into an initial commit.

Read root README, all prior docs, test_system.py, shared package, scripts and Compose. Preserve the modular-monolith architecture, actual PL interface, two-dataset grading, graph direction/provenance and synthetic-only boundary. Phase 2 will harden these components incrementally. Live model access is not assumed, and no paid request is authorized by credentials being present.
