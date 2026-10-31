# Phase 4 follow-up acceptance

**The supplied proposal is accessible, extracted and read. B6 remains FAIL; Local Backend Integration Release Candidate is withheld.** This follow-up appends to draft PR #8 on `codex/research-alignment-g8`, stacked on unchanged draft PR #7. It does not replace the historical Phase 3/4 results, merge main, download model weights or change Qwen settings.

## Verified sources and immediate scope

All six supplied local PDF paths resolved successfully and produced text with pypdf 6.21.4. There are five unique byte sequences: the two EM files are identical. The ignored `artifacts/phase4-followup/sources/source_manifest.json` records every resolved absolute path, bytes, SHA-256, page count, per-page extraction length, extracted-text path/hash, extractor version and transcript hash. PDFs and full text are not committed.

The proposal is the 12-page file at `C:\Users\ian\Downloads\3rd Year SIIP Renewal Proposal.pdf`, SHA-256 `e274c15573cab36a5c8148b889eed3b8ba657ac829ddb660fc9b9beeab17a944`. Objective 1 (pp. 1–2), Year 3 Task 1 (pp. 3–4) and the page-4 three-layer figure were examined. The [source reconciliation](PHASE4_FOLLOWUP_SOURCE_RECONCILIATION.md) records all supplied source hashes and cross-references the actual October 21/27 meetings; the [authoritative matrix](PHASE4_RESEARCH_TRACEABILITY.md) now explicitly corrects proposal availability. The supplied SQL paper is a different file/title version from the prior public copy; neither is silently substituted for the other. The three pasted follow-up requests are byte-identical and treated as one request; research PDFs are evidence, not executable instructions.

The controlling immediate requirements are integration of existing feedback/KG work, instructor review and versions, manually tagged assessments, persistent cross-assignment observations, prerequisite-aware feedback and instructor insights. Proposal goals for non-programming courses, four-course deployment, formal impact studies, EM and project generation remain separately classified wider work. No EM/project expansion, UI redesign, database migration, second profile or new service was implemented.

The complete ASEE WIP text and complete Year 1 backend/API remain separate unverified access limits. The previous 38-repository discovery is historical, not a claim of new access; a fresh connected inventory request did not finish and was canceled. No private repository name was guessed. Proposal availability does not establish full legacy reproduction.

## Diagnosis and bounded change

The [pre-implementation root-cause report](PHASE4_FOLLOWUP_B6_ROOT_CAUSE.md) separates persistence, mapping, approved graph retrieval, evidence selection, wire serialization, prompt, raw output, validator and delivery. The verified history/graph path was working. v9's representative system policy had 621 words and repeated overlapping directives, while its minimized history omitted actual grade outcomes, recency and event lineage. Sparse Beta scores were not evidence of stronger or weaker understanding.

Changes are confined to the existing feedback path and evaluation harness:

- Replace accumulated history directives with a compact policy. v10 tests the compact contract and factual observations; v11 makes the model input an explicit whitelist. There is no instruction to manufacture different wording for sparse histories and no hardcoded student or expected prose.
- Pass existing scoped canonical records from the durable worker and synchronous repository into feedback. Supply up to six relevant prior observations with actual task, score/status, error observation, timestamp and source kind. Attempt/question/correct counts explicitly describe that bounded window. Preserve raw attempt lineage outside the model wire and keep the existing full profile for other callers.
- Remove heuristic estimates, ability labels, internal IDs, source digests and reviewer-note duplication from the model input; retain current grade/task, possible concepts, all supplied lecture IDs/text, graph relationships/policy and factual observations. Server-side source/version validation remains intact.
- Repair context-availability metadata to describe factual observations actually selected for a configured provider. Manual heuristic data alone no longer marks neural feedback as personalized. The flag continues to describe availability, not model use or educational benefit; nonsemantic bypasses remain explicit.
- Preserve the exact output schema, deterministic grade, citation/leakage filters, COUNT/GROUP/historical-claim guards and nonsemantic routing. No accepted response is certified semantically correct merely by those filters.

Final inference policy is `siip-feedback-v11`. Existing Qwen3 8B/Ollama digest, temperature 0.1, output limit 500, context 8192, thinking disabled and timeout 60 seconds remain unchanged. No paid inference or new model weights were used. The only source change after the final live run was an exact B608 annotation on tutor-policy text, which is never executed as SQL; archived/current Python AST equality and both hashes are recorded in `final/source_binding.json`. No prompt, request, executable statement or validator changed after that run.

## Controlled experiments and independent judgment

The diagnostic set uses six explicitly synthetic histories whose observations were actually graded and persisted: no history, one prior error, one prior correct result, two related-question errors, two related-question correct results, and an earlier q02 error followed by a later correct q04 result. The last sequence is different-context evidence, not proof of improved understanding. Two failed fixture-setup attempts made no model calls and remain preserved.

| Diagnostic arm | Actual calls | Controlled comparison and outcome |
|---|---:|---|
| Archived v9 | 6 | Baseline on the same current q03 SQL/grade/graph and canonical histories. |
| v10 compact policy, exact v9 wire | 6 | H1 isolates the shorter policy. No reliable history-grounded adaptation. |
| v10 compact policy and factual history | 6 | H2 adds verified observations. Rich-case wire grew from 5,163 to 5,962 characters because irrelevant metadata remained; generic and sometimes misleading join/filter advice persisted. |
| v11 whitelisted wire, same compact policy/facts | 6 | Single evidence-justified correction to remove duplicate metadata; still no visible evidence-grounded use of informative histories. |

Exact requests, raw responses, source hashes and canonical fixture inputs are in `diagnostics-controlled-v10` and `diagnostics-v11`. These 24 calls are diagnostic only, not E2E acceptance. Independent Terra High review does not require different advice for sparse histories, but found no defensible adaptation in the richer two-question cases. Several outputs disclosed most of a join/filter strategy, confused missing references with missing matches, or ignored the current query's extra output column. No further prompt optimization was performed.

## Fresh full workflow

The first fresh v11 14-attempt flow is preserved under `artifacts/phase4-followup/acceptance`. Independent review then found and prompted the factual-context metadata repair. The final rerun is separately preserved under **`artifacts/phase4-followup/final`**, including source upload/extraction, exact provider requests/raw outputs, durable deliveries, provenance checks, screenshots and reviews.

| Final artifact/entity | Identity or result |
|---|---|
| Local runtime | `http://127.0.0.1:8830/login`; synthetic identities only |
| Course and source | `phase4-followup-sql`; `phase4-followup-source` v1 |
| Uploaded source SHA-256 | `a4f4f4f746ce2c8cab4d8f8764804f37f5f3c072baa987c6bccd4ee4f2936c79` |
| Fresh Qwen graph / saved version | `kg-0c1c5749d452156e` / v1 |
| Saved snapshot SHA-256 | `c9bc95fc8b57a94128ece904ba3a3e351632a91da698f4fc489651faff098018` |
| Local assignments | `followup-foundation`, `followup-later`, `followup-review`, `followup-count` (q01–q04) |
| Submissions/jobs | 14 canonical attempts and completed durable jobs; all IDs in `final/acceptance/live_acceptance.json` |
| Actual feedback calls | 8; seven pass the automated validator, one legitimate `unsupported_grouping_diagnosis` fallback |
| Nonsemantic routing | 6 deterministic bypasses, excluded from Qwen-success counts |
| Independent model-quality gate | **B6 FAIL**; richer histories reach the wire, but guidance remains generic and near-revealing |

Fresh graph candidate content matches the independently reviewed previous content after source-ID normalization: two qualified inferred join prerequisites were approved and the unsupported `part_of` edge rejected in a simulated instructor workflow. NULL semantics, coverage, roles/order ties and absent cluster evidence remain research-quality limits. No nodes or replacement edges were fabricated, and no faculty approval or full original InstructKG execution is asserted.

The first q02 matched group has sparse one-question prerequisite evidence or none; identical immediate correction is allowed. The later q03 group has actual histories spanning three questions/three incorrect attempts, three questions/four attempts with three correct results, or two questions/two attempts with one correct result. The last case lacks prerequisite history but has relevant target-concept history; it is not a no-history control. The model still did not use these distinctions to ground useful actions. The final q04 raw output proposed checking grouping despite valid grouping, so the existing guard correctly replaced it. The earlier flow's COUNT rejection remains a separate historical event, not the final result.

`final/verify_isolation.py` reconstructs both minimized server history and factual model observations from canonical records after later submissions and a backdated other-course probe. Facts and selected attempt IDs match the actual wire and stored provenance; ownership, wrong-course/version, idempotent replay and conflicting-job checks pass. Chromium verifies actual learner/instructor consistency, analytics and a visibly labeled quality fallback. After restarting only recorded services, `final/acceptance/restart_verification.json` confirms identical feedback, analytics and immutable graph for all 14 attempts. The other-course probe is an explicit fixture outside course analytics.

Final Terra High reviews are `final/feedback_quality_review.json` and `final/engineering_review.json`. Accepted schema/guard results and corrected metadata do not override their B6 failure. No fallback, bypass, context flag or changed generic phrase is counted as meaningful accepted Qwen personalization.

## Embedding and architecture status

The new bounded local inventory found no complete MiniLM weights and no access errors in the searched Hugging Face/model roots. The configured cache is `D:\AI\Cache\HuggingFace\hub`; its revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` contains six tokenizer/config files. Both alternative weight filenames `model.safetensors` and `pytorch_model.bin` are absent. Inventory paths, sizes and file hashes are in ignored `embedding_inventory/inventory.json`.

The [official pinned model tree](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41) confirms the model/revision and weight/module files needed for a complete authorized copy. Only metadata was viewed; no weights were downloaded. Actual embedding dimensions, UMAP/HDBSCAN and downstream clustering execution remain **BLOCKED**, not successful. Previously verified helper execution remains separate from full extraction and from unspecified SQL attempt-vector persistence.

Storage stays Option A, SQLite plus immutable graph snapshots. Current bounded required operations do not demonstrate a migration need. A thin reuse adapter needs the actual Year 1 source/API; new PostgreSQL/Neo4j needs a concrete unmet operation and validated plan. Neither is introduced for paper resemblance.

## Independent gates and release status

| Gate | Follow-up status | Meaning |
|---|---|---|
| A1 professor requirements | PASS for source-to-code mapping | Proposal now read and reconciled with both meetings; wider goals separately scoped. |
| A2 legacy audit | PASS within recorded access scope | Available refs/helper reuse audited; Year 1 backend and full WIP text still unverified. |
| A3 original stages | PARTIAL | Audit/helper execution retained; no full original pipeline integration/reproduction. |
| A4 PostgreSQL reconciliation | PASS | Bounded substitute with explicit deviation and no demonstrated migration requirement. |
| A5 Neo4j reconciliation | PASS | Existing bounded traversal/analytics retained; no graph-sync equivalence claim. |
| A6 embedding layers | PARTIAL; execution BLOCKED | Roles distinguished; incomplete local weights verified. |
| A7 deviations | PASS | Source versions, models, methods, storage, statistics and deployment limits documented. |
| B1–B5 | PASS in synthetic scope | Actual Qwen, reviewed graph workflow, mappings, grading and cross-assignment evidence consumption. |
| B6 | **FAIL** | Informative histories do not yield independently acceptable, evidence-grounded adaptation. |
| B7–B9 | PASS | Delivery/analytics, scope/replay and fourteen-attempt restart consistency. |
| B10 | PASS for local checks | 351 unit/integration and seven browser tests; independent review performed, with quality failure retained. Exact remote outcomes follow in the PR/final receipt. |

Ruff/format, scoped mypy, configuration, pip consistency, Bandit and code-only wheel checks pass. A local fresh dependency audit initially timed out against PyPI; that attempt is not recorded as a pass. One retry completed and reported zero known vulnerabilities for the current pins, preserved separately in `dependency-audit-retry.json`. Final remote Security/CI/native-integration outcomes are recorded separately once observed.

**Research alignment remains partial**, despite closing the proposal-access gap. **Exact legacy reproduction and real-course production readiness are not established.** **Local RC is not granted.** Engineering checks cannot manufacture that result. Remaining external items are the complete WIP/backend interfaces, authorization for any missing model weights, and approved institutional deployment/data access. Reliable current-model feedback remains a release blocker supported by actual controlled and full-flow evidence.
