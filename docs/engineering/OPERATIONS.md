# Local operations and recovery

`manage.py start` starts only Compose project siip-sandbox and the loopback dashboard. PL waits on health (300-second bound); dashboard waits on `/health` and checks service=siip-analytics. `manage.py stop` validates its dashboard PID command before SIGTERM and stops only this Compose project. Dashboard shutdown drains its server loop. Keep Docker Desktop running.

PL uses `pl-postgres-data:/var/postgres`; the earlier unused pl-postgres volume is preserved. Analytics uses `artifacts/synthetic.sqlite3` unless a nonempty `SIIP_DB_PATH` is supplied. Do not use `down -v`, delete volumes or overwrite the database for routine troubleshooting. `reset` stops the sandbox and moves the synthetic database to a timestamped local backup; PL history is retained.

Read-only health checks: `curl http://127.0.0.1:8080/health`, `scripts/smoke.py`, Docker Compose ps. Health distinguishes storage, graph, provider configuration and **llm=not_probed**. A healthy process is not evidence of inference availability. Logs contain allowlisted correlation/status/latency fields; they omit SQL, prompts and keys. PL owns its operational logs and history separately.

To verify restart preservation run `persistence_probe.py before`, `manage.py stop`, `manage.py start`, `smoke.py`, then `persistence_probe.py after`. The comparison checks exact PL submission IDs and a SHA256 of all normalized records, not just counts. Phase 2 performed this against 37 synthetic records and 15 PL submissions; see status for final evidence.

Before risky changes, use SQLite's backup API while connections are closed/consistent and pg_dump inside this project's PL container. Existing recovery points are `artifacts/phase2/baseline-synthetic.sqlite3`, `baseline-pl.dump`, `baseline-source-local-only.zip`. Stop owned services before restoring; restore into a separate test store/volume first and validate counts/IDs. A PostgreSQL restore is destructive to its target: inspect and explicitly select only this sandbox. Never apply local exports to a hosted course.

For rollback, check out a known reviewed commit in an isolated checkout, preserve runtime state, compare schema and restore a compatible snapshot if necessary. Root Git history preserves the pre-hardening implementation. There is no destructive automatic database migration.

If start fails: inspect Docker health/startup logs and `artifacts/dashboard.log`; cold PL esbuild compilation previously took four minutes. Do not increase SQL or model deadlines to conceal platform startup failure. If port 8080 has an unrelated service, startup stops and preserves it. If grade succeeds but feedback fails, the fallback label is evidence of a degraded optional subsystem; do not report complete research success.

`scripts/report.py` is the preserved Phase 1 static acceptance-report generator; do not run it to establish current Phase 2 results. Current evidence is docs/handoff/verification.json plus actual logs/CI. The old generator does not execute the checks it lists.

Follow-up restart fault: the official image left a stale `/var/run/postgresql` socket lock in its container writable layer. The named database volume was intact; an owned-container force recreation recovered it without volume deletion. `manage.py stop/reset` now checks the owned service, invokes the official PostgreSQL stop script when ready, then stops Compose. This is independently tested with isolated fake-Docker contracts and actual restart/E2E. Do not delete PostgreSQL lock/PID files blindly or run `down -v`. Preserve backups before recovery.
