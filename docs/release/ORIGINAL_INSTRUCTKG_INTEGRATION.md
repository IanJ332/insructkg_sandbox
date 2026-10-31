# Original InstructKG chunk-based integration acceptance

## Post-implementation quality review

This review starts from accepted PR #9 head `7a5a01dadcc24ff63c7ac21763c02a17edfd77b6`. It preserves the historical milestone and all prior artifacts below. The new changes are limited to direction coverage, reviewed metadata selection, precise failure provenance and reproducibility instructions. No upstream file, algorithm, grading database, feedback prompt, model setting or validator rule was replaced.

| Result area | Status | Independent conclusion |
|---|---|---|
| PDF-to-KG engineering | PASS, bounded local execution | Same original PDF; six original chunks preserved, five selected for extraction; original concepts/roles, PairPackets and judger executed. Source hash and page/ID/neighbor metadata match the baseline. |
| Concept and relationship quality | PARTIAL improvement; automatic-use quality FAIL | Fixture metadata nodes disappear and the missing supported prerequisite is recovered. Generic concept noise, reversed/unsupported judgments and contradictory directions remain. Five of 78 edges have direct-source support under Terra's conservative review. |
| Student Profile and Question Mapping | PASS, existing bounded scope preserved | Regression/E2E pass. New reviewed prerequisite mapping resolves JOIN_PREDICATE to JOIN_CONDITION. Controlled replay reuses canonical prior records without changing any attempts or historical jobs. |
| History-aware Qwen feedback | FAIL (B6) | Improved prerequisite context reaches the model, but useful evidence-grounded history adaptation is not demonstrated; a raw response still casts doubt on a correct counting component. |
| Independent model-output review | COMPLETED; quality FAIL | Terra inspected all 78 new edges and both controlled feedback outputs against actual source/context. An automated accepted sparse-history response still prescribed a replacement join, failing independent non-revealing review. |
| Clean-room reproducibility | BLOCKED for unprovisioned environment | Local execution using the supplied external source/runtime/caches works. A source-only checkout does not supply authorized upstream code, heavy runtime/assets, existing Qwen weights or optional fixture-authoring reportlab; no new model downloads/installations were attempted. |
| External research dependencies | PARTIAL/DEFERRED | Original source redistribution permission, full MiniLM/UMAP/HDBSCAN execution, Year 1 backend/model artifacts and real-course access remain separate README backlog items. No source audit was repeated. |

### Direction error: precise origin and correction

The baseline packet is ordered `[JOIN_PREDICATE, LEFT_OUTER_JOIN]`. Original `pairpackets._cooc_counts()` emits alphabetically ordered pairs. The unchanged judgment prompt explicitly requires **A → B** and defines `A depends_on B` as B being a prerequisite of A. The raw baseline response says `depends_on` for that ordered pair while its justification argues that left outer join requires the predicate. Original parsing preserves that label and the adapter projects `A.name → B.name` without swapping. Thus the observed wrong edge is a **model semantic-direction failure**, while alphabetical candidate order plus unordered judger dedup also prevents assessing the supported opposite direction. Parsing/adapter reversal is not the cause.

Version `original-instructkg-jeffry-chunk-only-v2` calls the original builder twice. In the second worker-scoped call, a wrapper exposes the original co-occurrence counts with reversed keys; the original builder recomputes temporal, role, negative and confidence evidence for that orientation. The original helper is restored in `finally`. No saved packet is relabeled after calculation. Forward/reverse files are judged separately because the original file judger deduplicates an unordered pair within one file. Both decisions, including nulls and conflicts, are retained. Direction-specific edge IDs remain unreviewed until instructor action; there is no score-based choice, automatic reversal or automatic approval.

The actual same-PDF run tested **both orientations** for two explicit source prerequisites:

| Pair | Supported output recovered | Opposite output |
|---|---|---|
| Left outer join / join predicate | LEFT_OUTER_JOIN depends_on JOIN_PREDICATE | JOIN_PREDICATE depends_on LEFT_OUTER_JOIN still generated; its own justification argues the supported direction. Rejected by independent review. |
| Inner join result / join predicate | INNER_JOIN_RESULT depends_on JOIN_PREDICATE | JOIN_PREDICATE depends_on INNER_JOIN_RESULT also generated with reversed semantics. Rejected by independent review. |

The correction expands **coverage**, not demonstrated precision. A two-direction pass approximately doubles relation calls; source review remains essential. Synthetic instructor simulation approved the five supported edges and rejected the other 73 for the controlled context replay, in a separate immutable graph; the earlier four-edge graph/version and assignments were not modified.

### Same-PDF concept contamination comparison

The original byte hash remains `a508a4ea5e7ca39f485646c6657d7d5d3ce2d4c07fcf1fd5fa756ae9e6fd64de`. Actual Docling conversion marks the title/banner as body `section_header` and the provenance/license paragraph `#/texts/2` as body `text`; only the footer is furniture. Therefore a generic header/footer or label filter cannot justify dropping that paragraph.

The trusted synthetic-PDF manifest can now include explicit non-instructional item reviews, bound to each item reference, exact text SHA-256, synthetic instructor principal and reason. Original Docling/HybridChunker still produces all chunks. The adapter records item provenance before upstream serialization drops it and excludes a whole chunk only if **every** contributing item has that review. Mixed chunks and unreviewed material are retained; stale item/hash or unauthorized reviews fail. No SQL vocabulary or metadata keywords decide which concepts disappear. The policy is part of graph identity, preventing cache reuse across different reviews.

For this fixture, the synthetic review excludes only `lecture_text__0000` (license paragraph) from extraction; `chunks_original.jsonl` and `docling_document.json` retain it. All five teaching chunks keep their exact original text, IDs, pages, indices and neighbor pointers, including pointers into the retained original corpus. No source PDF bytes are edited.

| Measure | Accepted baseline | Targeted same-PDF run |
|---|---|---|
| Original / selected chunks | 6 / 6 | 6 / 5 |
| Mentions / concepts | 30 / 28 | 27 / 25 |
| Unordered pairs / directional judgments | 61 / 61 | 61 / 122 |
| Non-null candidate edges | 33 | 78 |
| Terra: approve / revise / reject | 4 / 10 / 19 | 5 / 25 / 48 |

CC0, fixture, integration-validation and public-domain concept nodes are absent afterward. `PREREQUISITE_KNOWLEDGE` remains generic pedagogical noise, and concept labels vary. Changed candidate sets and two orientations prevent treating 4/33 versus 5/78 as a controlled precision trend. Independent unreviewed-graph quality remains FAIL. [All 78 independent decisions](evidence/pr9_quality_review/after_quality_review.json) include page/chunk evidence and rationale.

### Provider-error fallback: exact boundary

Historical call 0 returned a parsed dictionary and token usage from `CompatibleProvider.generate()`. Its three-field schema and citation shape were available, but `feedback_text` contained `SELECT`. Replaying that exact saved return through unchanged validation triggers **Potential SQL solution leakage**. The broad `except Exception` labeled the rejection `provider_error_fallback` with `ValueError`, obscuring the output-validation boundary. The historical durable job was completed with safe fallback and matching learner/instructor readbacks: no generation, parsing, queue or persistence failure caused this event.

Validation rules/messages are unchanged. A `FeedbackOutputError` (still a `ValueError`) now carries a safe reason code; new results/events record `failure_stage=output_validation` and `error_details=potential_sql_solution_leakage`. The legacy fallback status remains for compatibility, and the raw response remains rejected. Quality and provider-generation failures have separate stage provenance. The focused test replays the **actual captured response**, verifies rejection and confirms it is not delivered as feedback. No historical record is rewritten or reclassified as successful.

### Better prerequisites do not establish better feedback

The new approved `LEFT_OUTER_JOIN → JOIN_PREDICATE` edge, assignment-mapped to `JOIN_CONDITION`, adds a source-supported prerequisite alongside `NULL_SEMANTICS`. Two fixed-v11 Qwen context replays reused the historical same-SQL Q4 cases and trusted prior-only records. The experienced request now includes four relevant observations rather than the baseline two; sparse history remains empty. Canonical records were checked unchanged afterward. These are **controlled diagnostic replays, not new student deliveries/jobs**.

The experienced raw output again questions valid `COUNT(employee_id)` and prescribes a replacement join; the existing counting-quality guard rejects it. The sparse raw output passes automated rules (`live_success`) but explicitly prescribes `LEFT OUTER JOIN`, violating the non-revealing instruction under independent review. This exposes a validator coverage limit; automated acceptance is not pedagogical or non-revealing acceptance. No prompt tuning, extra guard weakening or repeated optimization was performed. The generic deterministic history sentence is not evidence of useful Qwen adaptation. **B6 remains FAIL.** The six historical outcomes remain **1 accepted, 4 quality fallbacks, 1 provider-error fallback**.

[Controlled outputs without copied prior records](evidence/pr9_quality_review/controlled_feedback_outputs.json) and [Terra's independent feedback review](evidence/pr9_quality_review/controlled_feedback_review.json) retain the distinction. Model/digest, feedback temperature 0.1, 500 output tokens, 8192 context, thinking disabled and 60-second timeout are unchanged; original extraction settings also remain unchanged.

### Reproducibility and validation

The root README now supplies source revision/hash checks, external runtime paths, observed dependency versions, cached asset revisions, existing Ollama model/digest checks, optional reportlab requirement, fresh fixture/manifest generation, configurable browser replay and independent-review procedure. Fixture generation refuses overwrites; browser replay accepts a fresh output root/port. A demonstrated standalone Windows failure (`UnicodeEncodeError` printing upstream emoji under cp1252) is fixed by setting `PYTHONUTF8=1` in the subprocess environment, without editing upstream code.

The same-PDF local full run succeeds using existing authorized resources. Fresh fixture generation was also exercised and rendered/inspected; new PDF metadata produces a new source hash, which its generated manifest records. This fresh fixture is not substituted for the unchanged before/after PDF. The full heavy environment is inventoried in [runtime_versions.json](evidence/pr9_quality_review/runtime_versions.json); it is not a tested portable install lock. A clean source-only/unprovisioned run is blocked at the explicit external-source/runtime/cache/model prerequisites, and a fresh-machine model/dependency installation was not attempted. No unavailable weights were downloaded, and upstream code remains external/read-only.

Fresh local verification: **366 unit/integration tests PASS**, **14 end-to-end test-suite cases PASS** (including the seven previously exercised browser cases), Ruff lint/format, configured mypy and Bandit pass. Initial two pypdf test errors were sandbox access denials to the existing patched dependency; the properly authorized rerun passes. Temporary synthetic package fixtures were hash-checked before cleanup/restoration. Tests cover actual-response rejection provenance, reviewed metadata/stale hashes/mixed-content retention, directional parity/helper restoration and contradictory unreviewed candidates. Exact-head CI/security/native results are recorded in PR #9 after push. No merge or unrelated architecture/database change is authorized.

Local complete diagnostics: `artifacts/pr9-quality/`. Historical source, raw requests/responses, six-feedback outcome evidence, accepted graph, student profile and assignment artifacts remain preserved. New published evidence contains synthetic source/hash comparisons and reviews; full upstream prompt logs and raw prior-record contexts stay local.

## Accepted engineering milestone at 7a5a01d (historical evidence)

Date: 2026-10-31. **Original InstructKG Chunk-Based Integration Verified.**
Mode: `ORIGINAL_INSTRUCTKG_CHUNK_ONLY`. This is a bounded synthetic local engineering result. **B6 remains FAIL; Local Backend Integration Release Candidate is withheld.** Full original research reproduction, real-course deployment and student-data collection remain pending.

## Implemented path and original reuse

The instructor uploaded real binary PDF bytes in Chromium and clicked Generate Knowledge Graph. The selected mode called `DemoKGRepository.generate_candidates()` → `siip.original_instructkg.generate()` → the isolated heavy-runtime worker. The unchanged external functions executed:

1. `ingest.ingest_pdfs()` → `ingest.pdf_to_chunks()` (Docling and HybridChunker).
2. `main.run_llm_and_cards()`, including `llm.extract_concepts_llm_batch()`, `llm.classify_concept_role_llm_batch_texts()`, `llm.concept_to_id()` and `llm.build_concept_cards()`.
3. `pairpackets.build_pairpackets(chunks=actual_chunks, mentions=actual_mentions, clusters=[])`.
4. `relation_judger.judge_pairpackets_file()` → `relation_judger.judge_pairpacket_batch()`.

The source is the Jeffry reference at `c34a7786528e78766f15d918ab17aca2a9f7dc0b`; original master was verified at `ade6263a348984cef848eae85dc3d3b15daeea09`. Ten source modules are SHA-256 checked before execution. The upstream README claims MIT but the inspected trees lack the linked LICENSE. Redistribution terms remain unverified: upstream code stays in an external read-only checkout and is not included in this PR. [Original repository](https://github.com/aalrabah/instructkg), [pinned reference](https://github.com/code-royce/instructkg/tree/c34a7786528e78766f15d918ab17aca2a9f7dc0b).

The adapter changes transport and orchestration, not the extraction or relation algorithms. Original batched response contracts are translated to Ollama native chat. The transport is restricted to local HTTP(S), refuses redirects, disables thinking, and records raw calls locally. Explicit relation labels and response cardinality are validated before upstream normalization can obscure invalid output. No synthetic graph replaces a failure in this mode. Existing fixture and local single-call extraction modes remain available under their existing labels.

Configuration deviations are explicit: this native-text fixture used CPU Docling, OCR disabled, formula/code enrichment disabled, with remote services disabled and offline model caches. Embeddings, UMAP, HDBSCAN and cross-chunk semantic clustering were not run; clusters are literally empty. Scanned-PDF/OCR coverage has not been established by this run. Missing cached resources cause failure; no weights were downloaded.

## PDF and stage evidence

The one-page lesson is an original, explicitly synthetic CC0 fixture generated by `scripts/create_original_integration_fixture.py`. It contains no professor material or student records. Original-byte SHA-256:

`a508a4ea5e7ca39f485646c6657d7d5d3ce2d4c07fcf1fd5fa756ae9e6fd64de`

Upload provenance comes from the server's SHA-256 trusted fixture manifest, not a client checkbox or an injected banner. Uploads enforce bounded size, PDF parsing, type, authentication, CSRF and course/module binding. Text/Markdown retain their existing policy. Original PDF bytes, derived UTF-8 text, original chunk metadata and graph artifacts are distinct persisted objects with independent integrity checks. The live run exposed a Windows path-length defect in the derived filename; the fix uses one composite digest while preserving both full hashes in metadata. A retry reused the preserved completed graph and registered the source view successfully.

The original stages produced **6 chunks, 30 mentions, 28 concepts, 61 PairPackets, 61 judgments: 33 non-null edges and 28 explicit nulls**. Actual chunk IDs, page 1 references, chunk order and neighbor metadata remain available. The manifest records original functions, source module hashes, model identity, input/output paths and hashes, counts, configuration, deferred clustering and `fallback=false`.

[Committed synthetic evidence](evidence/original_chunk_integration/) includes the trusted fixture manifest, original stage outputs, reviewed graph, assignment actions, canonical attempts, actual delivered feedback, model contexts/responses and independent reviews. The PDF remains local under the repository's binary-publication policy; its complete fixture generator and original-byte hash are recorded. The hash inventory covers each published evidence file. Full original prompt/request logs remain local because upstream prompt redistribution is unverified; their original hashes are retained in the stage manifest.

Local complete run root: `artifacts/original-integration/`. Original stage directory: `live/runtime/demo-state/knowledge_graph/kg-6b9ac34972ee3e35/original_artifacts/run-zblqo_5y/`. Historical failure logs are preserved alongside the successful retry.

## Graph review and concept mapping

Independent Terra High read the actual PDF and all 33 proposed edges. Recommendations: 4 approve, 10 need revision, 19 reject. The unreviewed graph fails pedagogical quality: reversed dependencies, unsupported claims and fixture metadata concepts are common. Alphabetical A→B PairPacket orientation prevents judgment of some correct reverse-direction prerequisites, including `LEFT_OUTER_JOIN → JOIN_PREDICATE`. The adapter does not reverse or invent edges.

A synthetic instructor reviewed every edge, approved the 4 supported candidates and rejected the other 29, including all revision recommendations. Immutable graph **`kg-6b9ac34972ee3e35`, version 1** was saved. This is simulated review, not Professor Alawini's approval. Only approved `depends_on` edges may support prerequisite context; `part_of` is not treated as a prerequisite.

Four assignments `original-e2e-q1` through `original-e2e-q4` were published locally. Q1 selects original node `JOIN_PREDICATE`, explicitly reviewed-mapped to canonical question tag `JOIN_CONDITION`. This non-identity selection succeeds through assignment creation, publication, student loading, grounding and submission. Saved KG IDs remain unchanged. Mapping review provenance and graph/source binding remain assignment-scoped; unknown, unreviewed, colliding, wrong-course and stale mappings are rejected. The valid reviewed prerequisite available for the later questions is `NULL_SEMANTICS`; the missing join-predicate edge is disclosed rather than repaired synthetically.

## Student profile, delivery and feedback quality

Ten submissions across four assignments and two synthetic students reused the canonical submission repository, deterministic grader and durable feedback queue. The existing JSON attempt record now optionally persists the validated seven-key `feedback_grounding`, including assignment/course, source version/hash and graph version. No new profile database or grading backend was created. Replay conflict checks include lineage.

The experienced student's target Q4 attempt had four earlier same-course attempts; its model context included the two relevant prior observations across two questions. The sparse student had no earlier observations. Current and later attempts, another student and a seeded other-course record were excluded. Course-scoped profiles retained 9 S001 and 1 S002 attempts; full canonical records retain grades, observations, concepts, assignment and source/KG lineage. Profile estimates remain heuristics, not proven understanding.

The original Year 1 PostgreSQL/Neo4j backend/API remains unavailable. This work reuses the current implementation and does not claim original Year 1 source reuse or introduce a database migration.

Student feedback and instructor individual analysis read the same delivered job and canonical evidence. Deterministic analysis provides prior counts, concept evidence, repeated observed errors, reviewed prerequisites and provenance/uncertainty. No extra instructor LLM diagnosis is generated. Legacy jobs remain accessible with an explicit unavailable-analysis reason when reviewed lineage is absent; conflicting lineage is rejected. Class analytics use existing deterministic aggregates. Synthetic instructor access covers synthetic courses under the existing local role contract; institutional membership and real-course authorization are separate work.

Actual Qwen feedback used the unchanged `siip-feedback-v11`, `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, temperature 0.1, 500 output tokens, context 8192, thinking disabled and 60-second timeout. Original extraction uses temperature 0, 2400 output tokens and the recorded upstream-stage settings.

Of **6 actual feedback calls**, 1 was accepted, 4 triggered quality fallbacks and 1 triggered a provider-error fallback. Two correct/unsupported-query cases bypassed the provider; two earlier cases used deterministic feedback. Independent Terra High evaluated the six raw outputs and delivered outcomes, including COUNT(*), missing grouping, and experienced-versus-sparse same-SQL cases. **B6 FAIL**: history reached Qwen but useful history-conditioned model feedback was not demonstrated; both matched comparison outputs were filtered, and the generic fallbacks do not precisely distinguish all COUNT/grouping errors. Prompt and validators were not weakened or repeatedly tuned. The provider-error call has captured output, but its precise post-return failure cause is not established by this evidence.

All ten learner/instructor job payloads matched exactly. Cross-student feedback returned 403; wrong-course instructor lookup returned 404. Both services were actually restarted: profiles, immutable graph, ten jobs, student/instructor HTTP readbacks and analytics remained identical. Chromium rendered the actual persisted student feedback after restart. This is bounded local verification, not exhaustive production privacy or pedagogical assurance.

## Independent acceptance gates

| Gate | Status | Evidence and scope |
|---|---|---|
| P1 | PASS | Actual binary PDF upload, trusted provenance and original-byte hash; focused invalid/oversize/type tests. |
| P2 | PASS | Original Docling ingestion produced six page-referenced chunks. |
| P3 | PASS | Original extraction/role/card stages; 30 mentions and 28 concepts. |
| P4 | PASS | Original 61 chunk-based PairPackets, actual chunks/mentions, empty clusters. |
| P5 | PASS | Original 61 judgments; independently validated explicit raw labels/nulls. |
| P6 | PASS | Browser Generate action and actual 33-edge candidate graph displayed. |
| P7 | PASS | All synthetic decisions persisted; four approved edges in immutable version 1. |
| P8 | PASS | Actual generated JOIN_PREDICATE mapped to JOIN_CONDITION; selected nonidentity assignment usable. |
| P9 | PASS | Existing persistent cross-assignment profiles, grade/error/concept evidence and canonical lineage. |
| P10 | PASS | Captured actual feedback requests contain source chunks, reviewed KG and filtered prior observations. |
| P11 | PASS | Ten exact student/instructor delivered-job matches and deterministic analysis/analytics. |
| P12 | PASS | Bounded local auth, binding, prior-only isolation and actual service-restart persistence checks. |
| P13 | PASS | 362 fresh unit/integration tests and seven browser tests; lint/format, scoped typing, security/dependency and wheel checks pass. Exact-commit hosted/native checks are recorded in the draft PR. |
| P14 | PASS | Independent source-grounded review completed; unreviewed KG quality FAIL is separately retained. |
| P15 | PASS | Root README two-contact resource/dependency backlog updated. |
| P16 | PASS | Independent actual-output feedback evaluation completed; B6 quality FAIL remains release-blocking. |

P14/P16 mean the required independent evaluations were performed; they do not turn failed quality results into passes.

## Validation and delivery

Fresh **362 unit/integration tests** (zero failures), **seven browser tests** (zero skips), Ruff lint/format, configured mypy scope, dependency consistency/audit, Bandit, configuration validation and code-only wheel inventory are recorded under `artifacts/original-integration/validation/`. Final hashes are recorded in the accompanying validation receipt; exact-commit hosted/native CI results belong to the draft PR and do not alter the separate B6 failure. Native PrairieLearn checks exercise the existing four static question hooks; dynamic publication of newly created local assignments inside PrairieLearn is not claimed.

The branch is `codex/original-instructkg-integration`, based on verified PR #8 head `7d64d7585decdb60144743acebe83d6058adfd2e`. PR #7/#8 and dirty prior worktrees are preserved. No merge to main, force push, reference-repository write, private PDF publication, student-data ingestion or model download is part of this delivery.

## Re-run prerequisites

Set `SIIP_INSTRUCTKG_SOURCE_DIR` to the exact hash-verified external Jeffry snapshot and `SIIP_INSTRUCTKG_PYTHON` to its existing Docling-capable Python. Set `SIIP_SYNTHETIC_PDF_MANIFEST` to a trusted SHA-256 → provenance/license manifest. Start the existing local sandbox with `-LocalModel`, upload the approved synthetic PDF, and explicitly select **Original InstructKG (chunk only)** in authoring. Existing model/cache installation is required; absence is a reported failure. `scripts/validate_original_pdf_browser.py` records the instructor UI proof. The captured run's `scripts/original_instructkg_e2e.py` uses the saved launch receipt and independent review to reproduce prepare/submit validation; it is a fixture-specific validation script, not an additional application service.

Resume full MiniLM/UMAP/HDBSCAN only through original code after verified weights and resources are available. The supplied third-year proposal is accessible and reconciled in the earlier source manifest; unavailable Year 1 backend and full ASEE WIP are separate limitations. The README records both contact groups, ownership uncertainty and remaining access/approval/verification work. EM expansion, project generation and unrelated research objectives remain deferred.
