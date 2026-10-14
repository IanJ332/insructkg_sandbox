# Test strategy and evidence

Original baseline: `.venv/bin/python -m unittest discover -s tests -v` reproduced **43/43**, no failures/skips, before changes. `scripts/smoke.py` reproduced five HTTP checks. Evidence: `artifacts/phase2/baseline-tests.log`, `baseline-http.log`.

Expanded suite: 41 retained baseline tests + 40 new hardening tests = **81 public deterministic tests**, plus two original real-graph tests moved explicitly to `research_tests/` = **83 distinct tests**, not 164. Both local real-data and isolated public-fixture executions passed the 81; the two research tests passed separately. Final reruns and CI results are in the verification record. No skipped tests.

```sh
.venv/bin/python scripts/manage.py test-public
.venv/bin/python scripts/manage.py test-research  # authorized real data required
.venv/bin/python scripts/manage.py quality
.venv/bin/python scripts/manage.py build
.venv/bin/python scripts/smoke.py                # running services required
.venv/bin/python tests/e2e/prairielearn_flow.py --ack-local-synthetic
```

The SQL suite tests bag semantics, duplicates, NULLs, alternative solutions and adversarial statements across independent A/B databases. Worker tests exercise bounds, denied file/system functions, DDL/DML, multiple statements, unsafe pragmas and deadlines. This is tested SQLite containment, not a formal security proof for arbitrary DB engines.

Graph contracts cover malformed/non-object rows, empty/missing files, endpoints, labels/direction/cycles/evidence, review overlays and provisional separation. The public fixture has CONTRACT_* concepts and a synthetic lesson. Only the local research suite asserts the actual 469-judgment graph.

Provider tests start a local mock HTTP server and test response contract, HTTP errors/retries, bad credentials, timeouts, malformed/oversized outputs, invented references and obvious solution leakage. These are **mocked provider contract tests**, never live inference. Prompt-injection tests check separation/filtering; they cannot establish semantic resistance to all attacks.

Storage/API tests exercise rollback, concurrent duplicates, collisions, temporal profile isolation, strict schemas, source minimization, safe 503s, Host/Origin rejection and logs. New tests target concrete baseline defects rather than mirror implementation.

The Playwright driver uses actual local PL UI and downloads the supported CSV, then imports it and compares persisted analytics. Five final submissions passed; a prior selector-failure run already saved five attempts, so the final successful CSV imported ten new records. Trace/screenshots remain ignored. Exact PL IDs and repository hashes are compared across deliberate stop/start. No hosted API E2E, multi-user load benchmark or live pedagogical quality study has run.
