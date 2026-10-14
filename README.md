# SIIP — PrairieLearn × InstructKG SQL sandbox

Original integration code for a local SQL learning research prototype. Three **actual PrairieLearn** questions share a bounded SQLite grader, concept diagnosis, Baseline/RAG/KG feedback interface, and synthetic instructor analytics. Immediate feedback is stored by PrairieLearn; an explicit supported CSV export/import connects its attempts to longitudinal profiles.

Phase 2 reproduced the original 43 tests, expanded to **83 distinct tests** (81 public-fixture tests and two local research tests), and exercised five real browser submissions through feedback, correction, export, persistence and analytics. The local store now has 37 synthetic records across five students. **Live model inference is BLOCKED by the user's instruction: no paid usage.** Existing real KG loading passes; fresh upstream ingestion timed out after 600 seconds in a working isolated CPU environment. No fresh concepts or relations are claimed.

[Current status](docs/handoff/CURRENT_STATUS.md) · [External review packet](docs/handoff/EXTERNAL_REVIEW_PACKET.md) · [Next implementation plan](docs/handoff/NEXT_IMPLEMENTATION_PLAN.md) · [Documentation index](docs/README.md)

## Clean public-code setup

Requires Git, Python 3.11 or 3.13 and Docker Desktop/Compose for PrairieLearn. Public tests need no university services, paid credentials or GPU.

```sh
python3 scripts/manage.py install
.venv/bin/python scripts/manage.py test-public
.venv/bin/python scripts/manage.py quality
.venv/bin/python scripts/init_public.py prairielearn-course/serverFilesCourse/siip/data
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/manage.py start
.venv/bin/python scripts/smoke.py
```

The fixture initializer creates a **clearly synthetic contract graph and lesson**, not an InstructKG extraction. Use its course-data target only in a fresh public checkout: it must not overwrite local research data. For authorized real local research preparation use [Local setup](docs/engineering/LOCAL_SETUP.md).

Open [PrairieLearn](http://localhost:3000/pl), **Load from disk**, open SIIP SQL → Fall 2026 Synthetic Sandbox → SQL Concept-Aware Feedback Sandbox, then Dev User → Student view. [Analytics](http://127.0.0.1:8080/) shows profiles, graph review and feedback comparisons. See [demo steps](docs/DEMO.md).

```sh
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/manage.py e2e   # adds actual local synthetic submissions
.venv/bin/python scripts/manage.py evaluate  # 63 deterministic fallback comparisons, zero model calls
.venv/bin/python scripts/manage.py stop  # retains both databases
.venv/bin/python scripts/manage.py start
```

## Implemented boundaries

`prairielearn-course/serverFilesCourse/siip/` holds grading, graph, feedback and storage; question hooks are thin. PrairieLearn's digest-pinned official image owns PostgreSQL history. Our analytics use a separate SQLite store. The dashboard binds loopback and has no public authentication. No PL core changes, hosted course synchronization or Neo4j service are required.

`.env.example` documents literal environment configuration. The default deterministic provider makes no inference requests. Compatible providers implement bounded timeouts, response validation and explicit paid-consent gating; credentials alone never authorize spending. Leave inference disabled under the current instruction.

GitHub Actions implement two-Python quality/tests/build, full-history publication scanning, Bandit and dependency audit, plus a slower actual PL browser/restart workflow. CD is reproducible local startup and a restricted-data-free wheel; there is no automatic institutional deployment.

## Data and research limits

Research checkouts, course PDF/text, original KG outputs, databases, model caches, screenshots and raw logs stay ignored locally. The existing local graph has 469 judgments / 121 nodes; none are instructor approved. Eight developer provisional edges are separate. Public CI uses different original contract fixtures. Profiles are descriptive beta heuristics, not validated mastery measures; no student learning benefit is established.

Original code publication is authorized. Third-party redistribution and blanket licensing rights are not established; see [NOTICE](NOTICE.md). Old root-level docs under `docs/` preserve Phase 1 history; the organized Phase 2 handoff is authoritative for current status.
