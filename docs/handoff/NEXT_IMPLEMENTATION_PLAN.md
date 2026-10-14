# Next implementation plan

This plan retains the working package, course and CSV boundary. Each task states its current evidence and a completion gate. Complexity is relative engineering effort, not a promised calendar date. No inference is authorized under the current user instruction.

## P0 — Blocking research functionality

### P0.1 Live model feedback validation — BLOCKED, human resource decision then autonomous engineering

1. Current state: configurable compatible client and three context modes implemented; mocked HTTP/error/filter tests pass. Zero live calls.
2. Problem: no actual provider-backed response or quality/cost measurement exists.
3. Evidence: 63 deterministic comparison outputs, contract tests, explicit user instruction to keep inference blocked/no paid usage.
4. Solution: only after a changed instruction, select approved endpoint/model and finite batch/cost ceiling; run a one-attempt Baseline/RAG/KG canary, inspect outputs, then the bounded frozen comparison set. Do not automatically start 63 paid calls.
5. Files: configuration.py, feedback.py, scripts/evaluate.py, .env.example, feedback-evaluation/status docs.
6. Tests: retain contract/error/grade-invariance tests; add approved live evidence including model/prompt/settings, usage, latency, retrieved references and validation failures. Independent humans rate quality/leakage.
7. Acceptance: actual live responses in all three modes with citations valid for their condition; unchanged deterministic scores; failures and observed usage reported; no secrets/raw records published.
8. Dependencies: explicit model-use authorization; endpoint/model; credential only in ignored configuration; instructor-approved corpus for pedagogical claims.
9. Risks: synchronous tail latency, prompt injection, semantic leakage, unsupported API details and cost.
10. Complexity: medium. Human: resource/usage decision only; implementation and debugging autonomous. Current instruction blocks execution, not coding readiness.

### P0.2 Complete fresh upstream extraction — PARTIAL, autonomous parsing work; model stages blocked

1. Current state: Linux CPU dependency isolation and upstream CLI import pass; actual ingestion exceeded 600 seconds with no chunks.
2. Problem: Mode B has no freshly completed document/concept/role/cluster/pair/relation artifacts.
3. Evidence: exit124, fresh-ingest.log, empty fresh-cpu output, unchanged Jeffry pin; no fabricated counts.
4. Solution: profile the existing parser on cached weights and isolate whether native text/OCR/enrichment causes delay; rerun unchanged algorithm with a documented justified CPU/time budget. If an optional OCR setting changes, treat it as a distinct experimental configuration. After approved model access, execute upstream stages with isolated outputs and capture each stage's metadata/counts/errors.
5. Files: infrastructure/Dockerfile.extraction, extraction-cpu.lock, scripts/extraction_cpu.py, extraction status/provenance docs; do not edit upstream algorithm in place.
6. Tests: no-network import; bounded PDF ingestion; checksum/page/chunk provenance; role/cluster/packet/relation validation; deterministic resume only when input/model/config hashes match. Record unsuccessful stages, not only final file presence.
7. Acceptance: actual nonstale chunks and complete stage outputs with model/settings/runtime, no orphaned-card promotion, graph adapter accepts schema and instructor review queue exposes uncertain directions.
8. Dependencies: current PDF/local rights; parsing resources for ingest; approved generative model for later stages; review rights before publishing outputs.
9. Risks: CPU enrichment latency, nonhermetic weight downloads, stage resume contamination, tiny source corpus, known upstream orphan cards and OCR damage.
10. Complexity: medium for profiling, high for completed research validation. Autonomous nonmodel diagnostics; human model decision/instructor review only.

## P1 — Reliability and quality

### P1.1 Hosted latency and optional-feedback lifecycle — experimental

1. Current state: deterministic grade set before optional bounded synchronous feedback; fallback isolates exceptions.
2. Problem: a configured provider can still delay a synchronous PL request up to its bounded timeout/retries.
3. Evidence: current PL hook and provider contract; no hosted latency measurement or approved live endpoint.
4. Solution: measure permitted host runtime/deadlines first. If the measured budget is unsuitable, design an explicit authorized feedback job/cache service with status polling and a reproducible attempt key; preserve immediate deterministic grade. Do not add a speculative queue before a constraint exists.
5. Files: pl_bridge.py, feedback.py, optional new service/adapter, question rendering, integration contracts.
6. Tests: delayed provider, failed job/retry, stale result isolation, duplicate keys and actual hosted E2E in a separate test course.
7. Acceptance: grade latency within agreed budget; feedback status is observable and cannot attach to a different attempt or change scores.
8. Dependencies: hosted network/runtime facts and approved model access if measurement uses inference.
9. Risks: added operational complexity, identity leakage and job persistence.
10. Complexity: medium investigation / high if async service justified. Autonomous engineering after institution facts.

### P1.2 Broaden boundary verification and operations — partial

1. Current state: 83 distinct tests, local restart, full-history secret scan, Bandit and dev dependency audit; CI runs linked in verification.json.
2. Problem: no formal containment proof, target-load benchmark, image/research-stack vulnerability audit or automated restore drill.
3. Evidence: TEST_STRATEGY.md and SECURITY_AUDIT.md explicitly scope current checks.
4. Solution: threat-model target deployment; exercise worker memory/process bounds on the target OS, concurrent imports/readers, and restore into isolated databases; audit pinned containers/research dependencies and triage actual findings. Extend type checking at changed boundaries incrementally.
5. Files: sql_worker.py, store.py, dashboard.py, tests/test_hardening.py, workflows, operations/dependency docs.
6. Tests: adversarial resource cases, measured contention/error rates at agreed synthetic load, backup/restore ID/hash comparison, scanner failure-path tests.
7. Acceptance: documented target/resource limits and residual risks; recovery drill passes; CI failures resolved without skipped tests; publication checks remain fail closed.
8. Dependencies: defined target workload/environment; ordinary local work can proceed autonomously.
9. Risks: expensive builds, platform-specific bounds and false confidence from small fixtures.
10. Complexity: medium. No user action needed for ordinary engineering; target-host access may require institution.

## P2 — Deployment readiness

### P2.1 Authorized hosted sandbox and identity adapter — BLOCKED

1. Current state: local PL and explicit dev@example.com→S003 CSV integration pass; no hosted deployment or real identities.
2. Problem: actual course permissions, UID mapping, retention and outbound API constraints are unknown.
3. Evidence: local-only URLs/allowlist, no original backend/API token, official docs distinguish course editing from student-data rights.
4. Solution: obtain a separate sanctioned course; verify supported runtime and documented read APIs; implement a narrowly scoped source adapter with consent-aware pseudonym mapping, minimized fields and idempotent pagination/checkpoints. Synchronize only the approved new course and reviewed public/authorized materials.
5. Files: sources.py, ingestion.py, infrastructure, protected deployment configuration, PL course metadata and operations/security docs.
6. Tests: mocked documented API pagination/auth/redirect/error contracts then actual authorized sandbox read/export, student separation and restart/rollback under synthetic data.
7. Acceptance: approved course/permission record, no changes to existing courses, correctly mapped synthetic attempts, bounded feedback and monitored storage; real records only after research authorization.
8. Dependencies: institution/course owner; access policy; credentials; material rights and research approval for real data.
9. Risks: SSO/FERPA/retention, course API constraints, external-grader network assumptions, public unauthenticated dashboard.
10. Complexity: high. Human obtains authorization/access; deployment/adapters/tests autonomous within that scope.

### P2.2 Original backend reuse assessment — BLOCKED on access

1. Current state: modular replacement boundaries documented, original backend schema/source unavailable.
2. Problem: cannot assess whether previous platform improves diagnosis/analytics without code/contracts.
3. Evidence: LEGACY_SYSTEM_INTEGRATION.md; provided paper titles/demo do not prove API availability.
4. Solution: inspect rights and run backend in isolation, compare identical synthetic attempts, reuse whole service or selected modules only on measured benefit and safety. Preserve shared PL adapter and migration/rollback contract.
5. Files: sources.py, grader.py, feedback.py, graph.py, store.py and versioned adapters only where needed.
6. Tests: equivalence/discrepancy matrix, schema migration, security/fallback, actual PL E2E.
7. Acceptance: evidence-based reuse/keep/rebuild decision with no duplicate authoritative grade or identity store.
8. Dependencies: repository access and rights from researchers.
9. Risks: incompatible SQL/ontology, unsupported Neo4j/Postgres assumptions and unnecessary rewrites.
10. Complexity: medium assessment, implementation conditional. Human access only; engineering autonomous.

## P3 — Research extensions

### P3.1 Instructor-reviewed graph and defensible mastery — pending review

1. Current state: preserved real graph/review UI, nine flags, eight provisional edges, beta heuristic profiles.
2. Problem: unreviewed directions/mappings and heuristic counts are not validated instructor alignment or mastery.
3. Evidence: graph audit and RESEARCH_LIMITATIONS.md; no instructor ratings.
4. Solution: version instructor decisions with rubric/evidence, resolve mappings and direction contradictions, evaluate retrieval/diagnosis on held-out rated attempts, then compare calibrated knowledge tracing only if data justify it.
5. Files: graph.py, mapping.json, store.py, review scripts/UI and research rubrics; real review artifacts remain access-controlled.
6. Tests: overlay audit history, blind interrater agreement, mapping/diagnosis accuracy and calibration/temporal leakage tests.
7. Acceptance: reviewed graph coverage and uncertainty published with rights; profiles explicitly calibrated or kept descriptive; no unsupported learning claim.
8. Dependencies: instructor time and authorized examples.
9. Risks: small corpus, observer bias, concept overlap and provisional-edge confounding.
10. Complexity: medium engineering, high empirical effort. Human pedagogical judgments; tooling autonomous.

### P3.2 Controlled learning study; later EM/adaptive projects — NOT_RUN

1. Current state: paired technical harness and future experiment design; EM and project generation absent.
2. Problem: no evidence of student learning benefit, study power or adaptive-project safety.
3. Evidence: synthetic-only data, no live inference and no authorized learner study.
4. Solution: preregister a powered Baseline/RAG/KG study after P0/P2/P3.1 gates; blind feedback ratings, measure transfer/retention and clustered uncertainty. Consider EM/adaptive assignments as a separate instructor-defined extension only after SQL validation.
5. Files: evaluation harness, research protocol/rubrics, approved data pipeline; new EM schema only after requirements exist.
6. Tests: reproducibility/provenance, assignment leakage, valid outcome capture, missingness/randomization audit and independent analysis review.
7. Acceptance: approved protocol, appropriate sample/power and transparent null/positive results; no adaptive production rollout based on fixture success.
8. Dependencies: professor/research authorization, participants/course schedule, statistician/design agreement and approved resources.
9. Risks: contamination, underpowering, inequitable feedback, measurement confounds and scope growth.
10. Complexity: high research program. Human approvals/design decisions; implementation and reproducibility work autonomous.
