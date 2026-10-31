# Phase 4 acceptance: research audit and live Qwen recovery

**Release decision: withhold Local Backend Integration Release Candidate. B6 FAIL.** The engineering workflow persists and delivers results, but reliable, appropriately qualified history-aware Qwen feedback has not passed. Two final matched responses were replaced with labeled quality fallbacks; those fallbacks are not Qwen success.

This candidate extends draft PR #7 (`9e298a35b400fccfca842a5eade55c0682d408f7`) on `codex/research-alignment-g8`. PR #7 and its eight-call G8 failure remain historical evidence. No merge into main is authorized. Original/Jeffry repositories and the dirty original checkout are preserved.

## Research decisions

The [authoritative traceability matrix](PHASE4_RESEARCH_TRACEABILITY.md) was written before implementation. It maps the actual October 21/27 transcripts, both examined primary PDFs, pinned reference files, and sandbox boundaries. Classification distinguishes source reuse, tested behavior, partial implementation, deviation, and unverified claims.

- **Option A: retain SQLite and reviewed graph snapshots for this bounded sandbox.** No demonstrated required operation warrants a migration. Option B, a thin adapter to the previous backend, remains unavailable because no authorized Year 1 implementation/API was found. Option C, minimal new PostgreSQL/Neo4j integration, is deferred until a concrete unmet requirement is demonstrated. This is not PostgreSQL or Neo4j reproduction.
- Discovery inspected the local PROJECT repository/remotes inventory, existing integration notes and legacy adapter experiments, actual original/Jeffry refs, and the 38 repositories returned by the connected GitHub inventory. No private repository names were guessed. This does not prove the backend does not exist elsewhere.
- The third-year proposal was not found locally or in connected Drive; its location was requested and it has **not** been read. The official [ASEE WIP landing page](https://peer.asee.org/60812), DOI `10.18260/1-2--60812`, was located; complete-text retrieval failed (403/timeout/522), so no full-text claim is made. Historical slides and titles do not substitute for these documents.
- The SQL paper's two-model semantic analysis/filtering architecture is not reproduced by Qwen plus deterministic guards. Local publication and synthetic identities do not establish institutional PrairieLearn deployment or real-course readiness.

### Persistence and graph operations

| Operation | Current implementation and evidence | Boundary |
|---|---|---|
| Canonical attempts, course/assessment/question/student association, SQL, grade, status, time | `store.py` normalization, attempt identity and stored JSON; `test_submission_history_integrity.py`, final HTTP run | SQLite attempts are canonical; no new store/profile was introduced. |
| Atomic batch/replay | `store.py` `BEGIN IMMEDIATE`, commit/rollback, fingerprint conflict checks; ingestion/storage tests | No atomic transaction across the separate attempt and job databases is claimed. The job database is derived delivery state. |
| Prior-only, course/student-scoped profile reconstruction | `records(... before=True, course_id=...)`, `profile`; historical/integrity tests and captured-context reconstruction | Descriptive beta heuristic, not calibrated mastery or a learning trajectory. Two attempts on one question are sparse, correlated evidence. |
| Directed prerequisites and question association | `graph.py`, immutable graph version binding and reviewed mapping in `assignment_grounding.py`; grounding tests | Approved `depends_on` edges support bounded traversal without a graph service. |
| Attempt trajectories, concept/error associations and instructor summaries | Scoped persisted records and `store.analytics`; instructor endpoints and restart comparison | Not Neo4j synchronization. Question-tag associations are possible error concepts, not established diagnoses. No roster-based course-completion denominator is invented. |
| Attempt vectors | Not implemented; no verified consumer/model contract available | Distinct from InstructKG lecture clustering. No pgvector, vector service or speculative table was added. |

### Original stages and embedding limits

[Representative stage evidence](PHASE4_LEGACY_STAGES.md) records actual unmodified Jeffry canonicalization, concept-card aggregation, adapter payload parsing, and pair-packet execution on clearly labeled synthetic inputs. Six imported files byte-match `c34a7786528e78766f15d918ab17aca2a9f7dc0b`. Roles/mentions and the packet cluster input were fixtures, not model extraction.

Original MiniLM embedding execution was attempted offline but **BLOCKED**: snapshot `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` contains tokenizer/config files without weights. No vector dimensions, successful UMAP/HDBSCAN output, or operational embedding layer are claimed. No model was downloaded. The standalone local extractor still omits original clustering/role/evidence stages; running helpers does not integrate or reproduce the complete pipeline.

## Feedback change and failure analysis

The checked chain is persisted history → reconstructed profile → reviewed concept mapping → approved prerequisite → minimized context → actual provider request → raw output → strict validator → durable job → learner/instructor delivery. The original history/mapping path supplied different prerequisite evidence correctly. The original prompt did not require using it, and inference unnecessarily diagnosed nonsemantic outcomes.

The existing feedback component now:

1. Calls the provider only for `semantic_error`. Correct, compilation, unsupported and other nonsemantic outcomes use deterministic guidance with `provider_routing=bypassed_nonsemantic` and no attempted provider or usage. Bypasses are not inference successes.
2. Versions the contract as `siip-feedback-v9`, distinguishes question tags from possible causes, supplies approved prerequisite evidence/counts, and requests history-conditioned actions with uncertainty. A wire-only projection uses neutral descriptive field names; server/profile contracts are preserved.
3. Preserves grading authority, exact output schema, citations, SQL/solution leakage checks and COUNT/GROUP guards. A narrow additional guard rejects specific observed unsupported understanding claims. It is not a general semantic correctness or no-reveal guarantee.

The model/digest and sampling remain unchanged: `qwen3:8b`, Q4_K_M, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, Ollama 0.17.7; feedback temperature 0.1, 500 output tokens, context 8192, thinking disabled, timeout 60 seconds. No paid provider, model download, quantization or inference-setting change occurred.

### Preserved experiments

All paths below are ignored local evidence under `artifacts/phase4`; they are not GitHub-published research artifacts.

| Run | Actual feedback calls | Result |
|---|---:|---|
| Historical Phase 3, separate `../live-qwen/artifacts/phase3` | 8 | Four accepted, four validation fallbacks; contrasting histories gave identical text; G8 FAIL. |
| v5, `acceptance` | 8 | Eight accepted plus four explicit bypasses; q02 contrasts identical; B6 FAIL. |
| v6, `round2/acceptance` | 8 | Eight accepted plus four bypasses; history still ignored, with a wrong preserved-table instruction; B6 FAIL. |
| v7, `round3/acceptance` | 8 | Different raw actions, but independent review found overclaims and near-solution guidance; quality PARTIAL. |
| v8, `round4/acceptance` | 8 | Raw action contrasts retained; independent quality remained PARTIAL. |
| v9, **final `round5/acceptance`** | 8 | Six accepted; two quality fallbacks; four separate nonsemantic bypasses. Required accepted matched contrasts fail. |

Separate two-call and four-call prompt diagnostics are labeled diagnostic only and are excluded from E2E success counts. Earlier raw outputs, contexts and reviews are retained. Only final v9 captures additionally contain the exact serialized `request_payload`; do not infer full archived wire requests for earlier rounds.

Final matched groups use q02 and q03 with the same course, SQL, grade, question and graph version within each group. S001 has weaker JOIN_CONDITION evidence (1/3), S002 stronger evidence (2/3), both from two foundation attempts on one question; S003 has no prerequisite history. Raw weak outputs propose a matching-key example, while strong outputs propose transferring key-matching evidence to trace matched/unmatched employees. However, both weak outputs assert unsupported understanding and trigger `feedback_quality_fallback`. An accepted strong output still says “stronger understanding,” outside the narrow guard. Control outputs continue to prescribe solution operators despite the prompt. No literal reference SQL was observed, but the rule filter cannot certify pedagogical correctness or non-revealing strategy.

Terra High independently recommends **B6 FAIL** in `round5/feedback_quality_review.json`. Main accepts that decision. No deterministic fallback or context-availability flag is counted as accepted history-aware Qwen output.

## Final synthetic workflow and evidence

Final runtime: `artifacts/phase4/round5/run/runtime`; local UI `http://127.0.0.1:8828/login`. Synthetic course `phase4-sql`; source `phase4-joins-source` v1; source SHA-256 `a4f4f4f746ce2c8cab4d8f8764804f37f5f3c072baa987c6bccd4ee4f2936c79`.

Actual fresh Qwen graph `kg-19e72f64bf3ef243` has five retained nodes and three candidates. Independent source review qualifies two join→predicate dependencies and rejects the unsupported missing-records `part_of` edge. Simulated instructor actions save graph v1; snapshot SHA-256 `d12e87ad77a6f84682e088ada3c1085b9e3f213c5cbc744baf864905bef20df8`. The repeated validated node/edge content matches the preserved previous extraction; this is not new evidence of accuracy. NULL semantics, complete canonical tag coverage, mention-level roles, cluster evidence and precise teaching-order ties remain limitations. No nodes or replacement edges were fabricated.

Three assignments (`phase4-foundation`, `phase4-later`, `phase4-followup`) are published **locally**, targeting q01/q02/q03. The reviewed JOIN_PREDICATE→JOIN_CONDITION mapping preserves graph IDs and versions. Twelve HTTP submissions produce canonical attempts and completed durable jobs. `round5/acceptance/live_acceptance.json` contains every attempt/job ID, grade, actual call index, delivered learner/instructor response, graph identity and course analytics; `model_calls.json` contains eight actual raw responses, contexts and wire payloads.

Representative lineage:

| Scenario | Canonical attempt | Durable job | Delivered inference status |
|---|---|---|---|
| Weak q02 | `demo-3f1d3d3aa207c959f6d30ea0` | `job-9093c46698b347b3` | `feedback_quality_fallback` |
| Strong q02 | `demo-5e9202ed19435ac1184a9532` | `job-62bb329a696f4794` | `live_success` (quality limitations remain) |
| Weak q03 | `demo-4e6206b5f831c7a34b1e7dbf` | `job-67f7b662f39944ff` | `feedback_quality_fallback` |
| Strong q03 | `demo-ad20b193f52ea9040e2b4408` | `job-f6d2bdd2294b4f90` | `live_success` |

`round5/isolation_verification.json` rebuilds each prior-only context after later submissions and a backdated other-course fixture. `live_acceptance.json` also verifies ownership rejection, wrong graph/course binding rejection, idempotent retry, conflicting job rejection and identical instructor/learner jobs. Chromium observes both a labeled fallback and actual accepted Qwen delivery, plus scoped instructor analytics. `round5/acceptance/restart_verification.json` confirms identical feedback, analytics and immutable graph for all twelve attempts after restarting only the recorded services. The extra other-course fixture is not a genuine learner event or part of course analytics.

## Acceptance matrix

| Gate | Status | Qualification |
|---|---|---|
| A1 requirements | PARTIAL | Actual October requirements mapped; mandatory proposal unavailable/unread. |
| A2 legacy reuse audit | PASS | Accessible sources/remotes/code audited; Year 1 backend/API remains unverified. |
| A3 original stages | PARTIAL | Audited; selected original helpers executed; full extraction/integration not reproduced. |
| A4 PostgreSQL reconciliation | PASS | Option A justified for bounded operations, with explicit paper deviation. |
| A5 Neo4j reconciliation | PASS | Required bounded queries supported without new service; no synchronization claim. |
| A6 embeddings | PARTIAL | Distinct roles established; MiniLM execution blocked and attempt vectors unverified. |
| A7 deviations | PASS | Model, pipeline, inference/filter, storage, statistics and deployment differences documented. |
| B1 actual Qwen | PASS | Actual extraction and eight final feedback responses with unchanged model/settings. |
| B2 generation/review | PASS | Narrow synthetic workflow; independent KG-quality limitations remain open. |
| B3 mapping | PASS | Reviewed version-bound mapping consumed; incomplete graph coverage disclosed. |
| B4 submission/grading | PASS | Twelve deterministic graded HTTP submissions; provider cannot change grade. |
| B5 cross-assignment profile | PASS | Prior-only scoped evidence consumed by actual calls. |
| B6 meaningful accepted Qwen history feedback | **FAIL** | Both weak matched responses rejected; accepted overclaims remain. |
| B7 delivery | PASS | Learner/instructor consistency and real browser delivery, including explicit fallbacks. |
| B8 analytics | PASS | Scoped twelve-attempt summaries and improvement event; no validated mastery claim. |
| B9 persistence/replay/isolation | PASS | Saved snapshots, replay/conflict/ownership checks and twelve-attempt restart comparison. |
| B10 regression/review | PASS for local checks | 349 unit/integration tests; seven browser tests on v8 plus final v9 browser delivery; final GitHub checks are recorded separately. Independent review performed and failures retained. |

Fresh local quality checks pass: Ruff, format, scoped mypy, configuration, pip consistency, Bandit and code-only wheel inventory. The final 349-test run uses patched pypdf 6.21.4 in an isolated validation target. Initial dependency audit found seven pypdf 6.21.2 advisories; the verified patch pin now audits with zero known vulnerabilities, and both primary PDFs parse successfully with 6.21.4. Historical audit failure is preserved. Publication audit and exact remote workflow outcomes are reported by the final handoff receipt/PR checks; they must not be inferred from an earlier baseline.

## Release classification and remaining boundary

- **Research Architecture Audit Complete: PARTIAL.** Accessible materials are audited; mandatory proposal, complete WIP text and original SQL backend remain unavailable.
- **Paper-Compatible Backend: PARTIAL.** Bounded execution/history/review contracts are present; full pipelines, original persistence and two-model feedback architecture are not verified equivalents.
- **Local Backend Integration Release Candidate: NOT GRANTED (B6 FAIL).**
- **Exact Legacy System Reproduction: NOT ESTABLISHED.**
- **Real-Course Production Ready: NOT ESTABLISHED.**

The next release-enabling evidence is accepted matched Qwen guidance that uses sparse history without diagnosing understanding or revealing a near-complete strategy. Current tests and rule filters cannot establish that result. Further inference/model configuration changes require the user's separate approval; none is silently substituted here. Source/API access is additionally required for the unavailable research materials and exact legacy-reuse claims.
