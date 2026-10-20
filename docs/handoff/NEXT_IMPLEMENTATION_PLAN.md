> Historical phase evidence. Current release status: [release audit](../release/FINAL_PR_AUDIT.md) and [test evidence](../release/RELEASE_TEST_EVIDENCE.md). Earlier pending/completion claims are preserved as history.

# Next implementation plan — after cross-validation follow-up

The accepted prototype is retained. This phase completes synthetic post-submission personalization, deterministic API reconciliation contracts and a compatible non-generative CPU ingestion path. No remaining task proposes rebuilding functioning components. Current user instruction keeps all generative inference blocked.

## P0.1 — Approved live local feedback canary — BLOCKED

1. State: endpoint/model/JSON/validation/error contracts pass against mocks; historical synthetic rule feedback works.
2. Problem: no actual model quality, latency, leakage or usage evidence.
3. Evidence: zero actual generative calls; Windows/GPU execution NOT_RUN.
4. Solution: only after instruction changes, choose an approved local model/hardware and bounded canary; compare identical attempts with/without history and fixed graph conditions, then rate outputs before a larger evaluation.
5. Files: feedback.py, configuration.py, scripts/evaluate.py, WINDOWS_GPU_READINESS.md, version manifest.
6. Tests: existing contracts; approved real endpoint canary, schema/fallback/grade invariance, latency/usage and human evidence/leakage ratings.
7. Acceptance: actual correctly labeled responses, unchanged deterministic grades, recorded model/checkpoint/prompt/settings, no secrets/records published.
8. Dependencies: explicit model-use authorization and approved local endpoint/model/resources; no paid account is intrinsically required.
9. Risks: VRAM, context budget, semantic injection/leakage, synchronous PL latency and confusing personalization with graph effect.
10. Complexity/responsibility: medium engineering plus human model/resource decision; autonomous implementation after that decision.

## P0.2 — Complete fresh research stages — BLOCKED; CPU ingest now PASS

1. State: actual native/Tesseract upstream chunks verified; original-settings generative enrichment not rerun.
2. Problem: concepts/roles/clusters/pairs/relations are not freshly generated; OCR/content quality and page 6coverage require review.
3. Evidence:13 chunks per variant; Tesseract16 cited pages; generation guard attempts0; historical 600s timeout retained.
4. Solution: review sampled chunks/coverage first; freeze chosen non-generative config and hashes. Only after approved model use, resolve a separate GPU/client environment and execute unchanged upstream downstream stages into new per-config output directories.
5. Files: extraction_cpu.py, profile_ingestion.py, verify_ingestion.py, CPU/GPU dependency inputs, research status/provenance.
6. Tests: input/source/profiler hashes, chunk links/citations, output/resume consistency, orphan cards/roles/directions and adapter schema; actual stage counts/errors/model/runtime.
7. Acceptance: real stage outputs with audit metadata and explicit instructor review queue; never substitute current historical graph counts or synthetic fixture nodes.
8. Dependencies: content review, approved model use, available compute and rights; local parsing needs no paid API.
9. Risks: OCR/table corruption, generative enrichment confounds, stale resumes, minimum-context filtering and upstream orphan-card issue.
10. Complexity/responsibility: medium preparation/high research validation; autonomous non-generative diagnostics, human pedagogical/model decisions only.

## P1.1 — Actual authorized local PL API canary — NOT_RUN

1. State: official endpoint/schema inspected; complete deterministic/mock HTTP reconciliation suite passes; actual PL→CSV E2E passes.
2. Problem: no authenticated live PL API poll has executed.
3. Evidence: no token was created/queried; synthetic mock endpoint tests and canonical scope policy.
4. Solution: obtain an explicitly scoped token for the owned synthetic course through supported PL settings, verify ID/map/CSV aliases, run a read-only poll and compare source IDs/scores/profiles before and after repeated/late attempts. Never point it at CS418 or real records.
5. Files: sources.py, synchronization.py, scripts/sync_pl.py, ignored scope/token config, integration tests/docs.
6. Tests: actual local supported GET, permissions denied, repeat 0inserts, completed/pending attempts, alias adoption, rollback/CAS and profile/feedback agreement.
7. Acceptance: authenticated local synthetic API evidence, no duplicate CSV/API counts, no raw UID/name/UIN stored and no unexpected scope access.
8. Dependencies: explicit local synthetic API access/token and verified scope mapping; no university production credentials requested.
9. Risks: token account-wide privileges, future schema/pagination changes, stable-origin aliases and immutable regrade policy.
10. Complexity/responsibility: small/medium; engineering autonomous once approved access exists. Hosted integration remains a separate gate.

## P1.2 — Runtime/load/restore hardening — PARTIAL

1. State: all retained tests, new contracts, actual E2E, exact restart and clean PG shutdown pass; preserved snapshots exist.
2. Problem: no target-course load/restore SLA, formal worker containment proof or full container/research vulnerability audit.
3. Evidence: scoped security audit and observed official-image stale socket fault/recovery.
4. Solution: benchmark the agreed synthetic workload, test isolated backup restoration, audit target containers/dependencies and define operational request-draining/shutdown policy before public/hosted service.
5. Files: sql_worker.py, store.py, manage.py, operations/security docs and workflows.
6. Tests: CPU/memory adversarial cases, concurrent readers/imports, stale checkpoints, owned-scope shutdown, isolated restore exact-ID/hash verification.
7. Acceptance: measured resource/latency/recovery limits, reviewed findings and no silent skipped checks.
8. Dependencies: target workload/environment definition; routine local checks autonomous.
9. Risks: platform-specific limits, SQLite contention, shutdown disconnects and small-fixture false confidence.
10. Complexity/responsibility: medium, autonomous engineering; institutional target access only if needed.

## P2.1 — Authenticated hosted learner feedback — BLOCKED

1. State: anonymous PL hook plus local trusted synthetic principal service; no principal serialization/HTTP endpoint exposed.
2. Problem: supported hosted identity/delivery/retention contracts remain unknown.
3. Evidence: PL hook ignores identity/mastery fields; service tests do not establish SSO or real authorization.
4. Solution: use an approved authenticated external feedback view first; derive subject/course principal server-side and minimize history. Investigate immediate PL delivery only through a verified documented identity/rendering contract. Do not invent feedback-writeback endpoints.
5. Files: personalization.py, sources.py, future approved auth/delivery adapter, infrastructure/security/operations docs.
6. Tests: authenticated subject/course separation, replay/expiry if tokens are introduced, hostile self-selected IDs, data retention/access controls and sanctioned synthetic hosted E2E.
7. Acceptance: approved course/identity mechanism, no user-controlled principal proof, correct subject-only feedback and bounded failure behavior; real records only after research permission.
8. Dependencies: university/course authorization, identity/privacy/retention decisions, runtime/network facts and research approvals.
9. Risks: real-record disclosure, token overprivilege, unauthenticated dashboard exposure and unsupported PL assumptions.
10. Complexity/responsibility: high; human institutional decisions/access, autonomous implementation within that scope.

## P2.2 — Future Windows GPU / extraction protocol validation — NOT_RUN

1. State: fixed official server versions, read-only readiness and configuration/transport dry-run tests; no server/model installed.
2. Problem: actual GPU/driver/VRAM, local routing and upstream Responses behavior are unverified.
3. Evidence: current Mac tools absent; server vs research runtime pins differ; extraction uses Responses while feedback uses Chat Completions.
4. Solution: validate future Windows/WSL2 hardware/driver and isolated pinned server environment, record resolved packages/model digest; later approved canary validates protocols. Keep CPU Docling lock separate from GPU vLLM.
5. Files: infrastructure/windows/*, check_local_model.py, extraction.py/wrapper and GPU lock after resolution.
6. Tests: metadata-only readiness first, then authorized endpoint/structured-output/error contract, Responses extraction schema and actual GPU resource measurements only after authorization.
7. Acceptance: reproducible hardware/software/model manifest and actual protocol evidence; local backend never demands a paid provider credential.
8. Dependencies: Windows NVIDIA host and future model-use authorization; no current installation/inference allowed.
9. Risks: incompatible wheels/driver, VRAM, WSL routing and partial Responses support despite Chat compatibility.
10. Complexity/responsibility: medium; human hardware/model decision, autonomous deployment/testing after scope permits.

## P3.1 — Instructor review and study integrity — NOT_RUN

1. State: original KG remains unreviewed,8 developer provisional edges separate; descriptive Beta profile and synthetic personalization demonstrated.
2. Problem: no instructor-aligned truth, calibrated mastery, semantic grounding or learning benefit established.
3. Evidence: FEEDBACK_CAPABILITIES.md and source/review labels; no real learners/inference study.
4. Solution: version instructor graph/mapping decisions; blind-rate concept/edge/evidence/feedback quality; hold history constant or add factorial ablations when comparing RAG/KG; preregister appropriately powered learner study after authorization.
5. Files: graph review/mapping, profile/evaluation harness, research rubric/protocol and access-controlled artifacts.
6. Tests: review audit trail, mapping/grounding accuracy, temporal leakage, raters' agreement, calibration and reproducible clustered outcome analysis.
7. Acceptance: honest uncertainty/coverage and approved empirical design; synthetic behavior never reported as student learning gain.
8. Dependencies: instructor/research/consent decisions, approved content, data and resources.
9. Risks: concept overlap, graph/history confounding, OCR errors, small sample/contamination and observer bias.
10. Complexity/responsibility: high research effort; human judgments/approvals, autonomous tooling/analysis implementation.

## P3.2 — Legacy backend reuse; later EM/adaptive projects — pending external evidence

1. State: reuse framework exists; original backend source/schema unavailable; EM/project generation absent.
2. Problem: cannot justify replacement or new pedagogical scope without contracts/requirements.
3. Evidence: LEGACY_SYSTEM_INTEGRATION.md; no backend access or EM rubric.
4. Solution: inspect authorized backend rights/runtime and compare identical synthetic attempts before reuse; retain current stable boundaries. Treat EM/adaptive assignments as a separate later instructor-defined study.
5. Files: selected grader/feedback/graph/store/source adapters only if needed; legacy integration/research docs.
6. Tests: contract/equivalence/security/migration/E2E and assignment leakage/reproducibility where applicable.
7. Acceptance: evidence-based reuse decision with no duplicated authoritative grader/identity store; approved EM requirements before code.
8. Dependencies: researcher repository access/rights and professor priorities.
9. Risks: incompatible dialect/ontology, unnecessary rewrites and scope expansion.
10. Complexity/responsibility: medium assessment/high extensions; human access/requirements, autonomous engineering.
