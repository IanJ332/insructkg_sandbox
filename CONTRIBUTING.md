# Contributing

Use a short feature branch from main; keep commits scoped to one behavior or infrastructure concern. Never rewrite upstream or published history. The existing engineering/phase2-hardening branch preserves the repository's initial README commit and an audited Phase 1 recovery commit.

Install with `python3 scripts/manage.py install`. Run `make quality`, `make test-public`, and `python scripts/publication_audit.py` before proposing a change. Local research verification is separate: `make test-research` requires the ignored real graph; no silent credential/GPU skips are counted as passes. Run `make e2e` after changes to hooks, ingestion, course configuration or analytics. It writes real synthetic PL attempts and stores browser traces locally.

Ruff formats/lints all maintained Python. Mypy checks the new typed configuration, telemetry and CSV-ingestion boundaries; legacy dynamic PL dictionaries are covered by contract tests, not claimed fully typed. Keep request schemas, error behavior, provenance and related docs in sync. Add regression tests for actual bugs; avoid tests that merely repeat implementation statements.

PRs should describe a concrete before/after behavior and relevant verification. Create them as drafts for independent review. Never publish `.env`, real data, course PDFs/text, original graph evidence, research checkouts, logs, screenshots, recordings, weights or database files. Review the full proposed file list and Git-history secret scan before push. Do not add a blanket license until project/contributor ownership is established.

CI uses original synthetic contract fixtures; it cannot validate pedagogical quality or live inference. Changes to workflows, security allowlists, grader boundaries and research provenance require careful human review. No automated hosted course deployment is configured.
