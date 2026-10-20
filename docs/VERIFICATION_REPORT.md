> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Verification report — 2026-10-14

**18 PASS, 2 BLOCKED, 0 FAIL, 0 NOT_RUN in the local acceptance matrix. The full definition of done has not been reached.** Live model feedback and actual fresh extraction remain blocked. No production/hosted/research approval is claimed.

## Environment and runtime

Intel macOS 15.7.4; 16 GiB RAM, 16 logical CPUs; Intel UHD 630 / AMD Radeon Pro 5500M (4 GB), no CUDA GPU. About 639 GiB host disk space was available initially. Host Python 3.13.9, Node 24.14.0, Git 2.50.1, Docker 28.5.2, Compose 2.40.3. WSL2 is not applicable.

Actual official PL image digest: sha256:f030faf735fdbb80c0307cc1b599d0757bb76a2f4573fbab9a7303adad4275ac, created 2026-10-14T17:26:39Z. Runtime Python 3.13.15 and Node 24.21.0. The image has no Git checkout; its source SHA is not asserted. Audited source revision and image digest are recorded independently.

Both services bind loopback. The corrected PostgreSQL volume mounts /var/postgres. A normal stop/start retained all five actual PL submissions and all 27 normalized profile records; browser assessment remained 3/3. Check artifacts/container_status.txt, prairielearn.log, environment_check.log, pl-after-restart.txt/.png and http_smoke.json.

## Acceptance matrix

| ID | Requirement | Status | Executed evidence / blocker |
|---|---|---|---|
| A01 | Repositories cloned and pinned | PASS | artifacts/repository_pins.log; input_manifest.json; detached public revisions |
| A02 | Local environment reproducible | PASS | scripts/bootstrap.py + manage.py; image digest; requirements-dev.txt; actual stop/start checks |
| A03 | Real PrairieLearn instance starts | PASS | artifacts/container_status.txt; prairielearn.log; actual browser page and http_smoke.json |
| A04 | Sandbox course loads | PASS | Load from disk sync jobs succeeded; artifacts/pl-assessment.txt and pl-after-restart.txt |
| A05 | Three SQL questions available | PASS | artifacts/pl-assessment.png/.txt; actual rendered questions and assessment score |
| A06 | Actual PL SQL submission works | PASS | Five real UI submissions: pl-q1-correct, pl-q2-incorrect/retry-correct, pl-q3-incorrect/retry-correct evidence |
| A07 | Deterministic grading works | PASS | artifacts/tests.log; actual correct/incorrect UI scores on both datasets |
| A08 | Custom feedback displayed | PASS | artifacts/pl-q2-incorrect.txt/.png; pl-q3-incorrect.txt/.png |
| A09 | Synthetic submission tests pass | PASS | 21 fixtures executed in synthetic_results.json; tests.log; 9 correct / 12 incorrect initial batch |
| A10 | Existing KG JSONL loads | PASS | artifacts/graph_audit.json: 469 records, 319 non-null, 150 null, 121 concepts; zero parse errors |
| A11 | Concept mapping works | PASS | mapping.json; tests.log; actual PL feedback concepts; graph-review.png |
| A12 | KG-informed live model feedback | BLOCKED | Deterministic KG feedback verified. No authorized model provider/key; 0 live calls in FEEDBACK_COMPARISON.md |
| A13 | Student profiles update | PASS | profile-before.txt / profile-after.txt: S003 10 to 11 attempts; analytics 26 to 27; final_analytics.json |
| A14 | Instructor analytics available | PASS | artifacts/analytics.png/.txt; actual browser overview, students, graph, comparison and HTTP smoke |
| A15 | Baseline/RAG/KG evaluation harness | PASS | artifacts/feedback_comparison.json: 63 executed deterministic outputs; FEEDBACK_COMPARISON.md explicitly reports 0 live calls |
| A16 | Actual fresh KG extraction | BLOCKED | fresh_extraction_status.json; no approved model resource; pipeline-dependency-check.log has no compatible torch wheel |
| A17 | Automated tests executed | PASS | 43 unittest checks passed in artifacts/tests.log; five live HTTP smoke checks; separate browser-assisted UI checks |
| A18 | Reproducible documentation | PASS | README.md; required docs; Makefile and scripts/manage.py commands; .env.example |
| A19 | Local security boundaries validated | PASS | SQL unsafe/read-only/time/resource tests; feedback validation; loopback Compose; limitations explicit in SECURITY_AND_PRIVACY.md |
| A20 | Hosted requirements documented | PASS | docs/DEPLOYMENT_GUIDE.md and HUMAN_ACTION_REQUIRED.md; hosted connectivity not claimed |

## Tests executed

`python3 scripts/manage.py test`: **43 tests, all passing**. The preserved raw log is artifacts/tests.log. Covers two datasets/reference outputs, join/NULL errors, syntax vs runtime, bag duplicates/order, alternative NOT EXISTS, unsafe SQL including writes through CTEs, extension/filesystem/metadata denial, row/resource caps and actual recursive/parent deadlines; graph schema/nulls/direction/duplicates/provenance/reviews/cycles; context separation, malformed/leaking/timeout provider fallback; timestamp/idempotence/student isolation/mastery; actual question Python hooks. Hook unit tests are not browser proof.

`python3 scripts/manage.py smoke`: **five live HTTP checks passed**, with bounded readiness retry. These cover actual PL HTTP response and dashboard/store/profile/graph/three comparison views. See artifacts/http_smoke.json.

Browser-assisted integration checks used the actual local PL student workflow: Q1 correct 100%; Q2 INNER JOIN error 0% then corrected LEFT JOIN 100%; Q3 NULL-reference-only error 0% then corrected anti-match 100%; custom feedback and prior attempts displayed. Five actual submission IDs were exported through the supported instructor CSV and imported to S003; recomputed scores matched exported scores. The separate instructor dashboard was inspected and a new synthetic form submission updated persistent counts/profile. UI screenshots and text snapshots are evidence, not fabricated interfaces.

`scripts/evaluate.py`: same 21 fixtures × three contexts = 63 inspectable fallback outputs; **0 live model successes**. Automated schema/filter checks passed; semantic quality, specificity, relevance and human leakage ratings remain pending. Usage/cost are null.

## Data and graph evidence

Initial fixture run: 21 attempts, 9 correct, 12 incorrect. Local PL export: five actual UI attempts, three correct/two incorrect. New synthetic dashboard attempt: one correct. Current total: **27 records, 13 correct, 14 incorrect**; source counts are 22 synthetic_fixture (21 batch + one form), five local_prairielearn_export. The three sources are never conflated with production API activity.

Graph: 469 original judgments; 247 depends_on, 72 part_of, 150 null; 121 named concepts; zero duplicate/parse errors; nine flagged review records. Zero instructor-approved original edges. Eight separate developer provisional dependencies. Seventeen PDF pages yielded native text; that extraction is not a fresh InstructKG run.

## Failures discovered and resolved

- Initial restricted-shell network requests could not resolve GitHub/PyPI; approved network execution retrieved public sources and the lightweight dependency.
- macOS SQLite lacks enable_load_extension; the worker now handles the absent API while denying extension functions. Reference queries then passed.
- One early test expected unsupported_query for readfile; SQLite has no such function on this build. Classification now explicitly treats unsupported functions as unsupported_query. No file read occurred. Final suite passes.
- Initial volume mount used /var/lib/postgresql instead of the image’s /var/postgres. Backed-up local data was restored into the corrected project volume. A restore attempted while the web app was active encountered schema dependencies; the stopped-app clean restore succeeded. Normal restart/recreation then retained all UI attempts.
- First HTTP smoke immediately after restart raced server readiness. A bounded retry handles transient startup connection failures; final live checks pass.

## Remaining blockers and honest limits

- Live inference: no approved available provider/key/model server; default outputs are deterministic fallbacks. No paid usage initiated.
- Fresh pipeline: no CUDA GPU or authorized API model; optional dependency dry-run also fails on this Intel Python 3.13 host because no compatible torch wheel resolves. No fresh chunks/concepts/relations are claimed. Exact preflight requirements are in fresh_extraction_status.json.
- Existing graph judgments are unreviewed and can be wrong; development dependencies are provisional. Source evidence spans more than the one PDF. Native text can lose complex table layout.
- Production API connectivity, hosted publication, institutional identity mapping and real-student study activity were not run; no authorization was available or assumed. API field mapping is implemented/tested with controlled records only. Local CSV integration is verified; automatic hosted data synchronization is not.
- Process/SQLite controls are not a kernel sandbox against a compromised database binary. Dashboard is unauthenticated local synthetic tooling. Feedback rule filtering and mastery are unvalidated heuristics. Read the security/profile/design documents before any pilot.

## Reproduction and delivery

Use README.md and docs/DEMO.md. The official PL assessment and instructor analytics are left running locally. Required guide documents and .env.example are present. `make test`, `make smoke`, `make evaluate`, `make stop/start` and explicit local export/import are documented. No real UIUC course, production records, upstream repository or hosted service was modified.
