# CI and local delivery

Three workflows use immutable checkout/setup-python action SHAs, `contents: read`, no repository secrets, and synthetic public fixtures. Never upload raw exports, model caches, protected lecture data or browser traces.

| Workflow | Triggers | Executed checks |
|---|---|---|
| ci.yml | push, PR, manual | Python 3.11/3.13; exact dev pins; synthetic initialization; configuration; pip integrity; Ruff/format; strict mypy on three typed boundaries; 119 deterministic tests; wheel inventory |
| security.yml | push, PR, manual | Full reachable Git history + prospective files scan; restricted-path audit; Bandit; pip-audit of exact dev pins |
| integration.yml | relevant workflow/E2E/Compose/script/course pushes, manual | Official pinned PL; five actual browser submissions/feedback/retries; instructor CSV export; atomic import; analytics; stop/start exact-record persistence; always stops services |

See [verification.json](../handoff/verification.json) for executed run URLs and actual status. A workflow file is not evidence that a run passed. Local research graph tests and fresh extraction are separate from public CI. No tests are conditionally skipped to manufacture a green result.

CD currently means `manage.py build`, explicit local start/stop and versioned configuration. The distribution contains original code/teaching fixtures only; check_wheel.py rejects restricted lecture and graph data. There is no automatic deployment to a university or public server.

Repository owner settings: require passing CI and Security checks for main; review slow integration for course/adapter changes; require review before merge; keep Actions read-only and secrets unavailable to untrusted PRs. Settings are recommendations, not claimed applied. No API secret is required today. A manual workflow may not appear until its file reaches the default branch; relevant push triggers allow this branch to be verified before merge.

Rollback uses a prior reviewed Git commit plus separately backed-up SQLite and PL PostgreSQL state; never `down -v`. Review schema/data compatibility before rollback. Published wheel packaging is preparation only, not an uploaded release or hosted deployment.
