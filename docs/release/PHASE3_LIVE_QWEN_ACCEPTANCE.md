# Phase 3 live Qwen acceptance — 2026-10-30

**Decision: Partial Local E2E. G8 FAIL: history-aware Qwen feedback was not demonstrated.**
The system does not qualify as a Backend Integration Release Candidate or as
Real-Course Production Ready. Live extraction/inference, synthetic grading,
scoped evidence, delivery, analytics and restart persistence were exercised.
Four of eight application feedback outputs passed validation; four retained
visible deterministic fallbacks. Independent review found identical accepted
feedback for contrasting prior histories. No model setting or guard was changed
to make these outcomes pass.

## Repository and runtime

Baseline: merged main `3cc668edbc800bd70d0c1b9935652c4fcf406ae1`.
Branch: `codex/live-qwen-e2e`. Checkout:
`C:\Users\ian\Desktop\PROJECT\insructkg_sandbox\artifacts\worktrees\live-qwen`.
The dirty original prototype and earlier worktrees remain preserved. Only
`IanJ332/insructkg_sandbox` is a synchronization destination. Upstream and Jeffry
repositories were not modified. No merge into main is authorized by this report.
Exact final commit, PR and workflow receipts belong in the final GitHub handoff.

The existing launcher started an isolated local-model sandbox on port 8823 with
output root `artifacts/phase3/run`. Normal Ollama CLI recovery started the installed
service; no model was downloaded, replaced, migrated, requantized or deleted.

| Model evidence | Actual value |
|---|---|
| Requested/effective model | `qwen3:8b` |
| Ollama client/server | 0.17.7 / 0.17.7 |
| Family / size / quantization | qwen3 / 8.2B / Q4_K_M |
| Installed digest | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Endpoint | `http://127.0.0.1:11434`, compatible `/v1`, native `/api/chat` |
| Model context capability / exercised context | 40960 / 8192 |
| Existing feedback settings | 60s timeout, 500 tokens, temperature 0.1, no retries, thinking disabled |
| Existing extraction settings | 120s timeout, 2400 tokens, temperature 0, thinking disabled |
| Feedback prompt / extraction pipeline | `siip-feedback-v4` / `siip-local-ollama-evidence-v1` |

Readiness was verified by actual `OllamaProvider` inference, not just metadata:
`live_success`, effective Qwen model and matching digest, 48402.062ms including
the cold invocation. The subsequent extraction took 10.58s. These are measured
single-run observations, not throughput or pedagogical benchmarks.

The eight application calls used a capture subclass of the existing native
`OllamaProvider` and the existing durable `FeedbackWorker`. Only this run's
receipt-verified background worker was stopped during capture; submissions still
used the HTTP practice/queue path. The normal worker was restored on restart.
Captured input, raw Qwen response, validation result and delivered response remain
distinct artifacts. Model text was never supplied by an engineering agent.

## Source, graph and independent quality review

Source: existing `demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md`, uploaded through
the instructor route as `instructor_alawini`, a **simulated** instructor identity.
Course `phase3-sql`, module `joins-null`, source `phase3-joins-source`, version 1.
Raw source SHA-256:
`a4f4f4f746ce2c8cab4d8f8764804f37f5f3c072baa987c6bccd4ee4f2936c79`.
The graph's separate trimmed-text SHA-256 is
`3530b7200c2b4a0eb304f15dd8ff5c8d8d727a21279d9defb4f9dae50fdd44b1`.

Fresh graph `kg-a18670e90f73b4ae` used `LOCAL_LLM_ASSISTED_EXTRACTION` with no
fallback. Five evidence-validated nodes and three edges remained; one node and
two edges were rejected by existing checks. The original candidate graph is
preserved. This local pipeline is not full original InstructKG reproduction.

Independent reviewer: **GPT-6.1 Terra High**, inspecting the actual source, graph,
metadata, quotes and canonical question catalog. Rubric: 1 seriously deficient,
2 materially weak, 3 mixed/limited, 4 good with limited shortcomings, 5 strong and
complete for the stated scope.

| Dimension | Score |
|---|---:|
| Concept significance | 3/5 |
| Pedagogical alignment | 3/5 |
| Relationship accuracy | 3/5 |
| Evidence grounding | 4/5 |
| Graph structure | 2/5 |
| Assignment compatibility | 2/5 |

Recommendation: **ACCEPTABLE AFTER CORRECTION**, restricted to synthetic join
integration. Main accepted the evidence-based recommendations and used the
existing instructor review route:

- Approve `INNER_JOIN depends_on JOIN_PREDICATE` (`edge-f483bb16c8c8`) as a
  qualified instructional inference. Source line 32 describes its join predicate.
- Approve `LEFT_OUTER_JOIN depends_on JOIN_PREDICATE` (`edge-7b36044b0121`) on
  the same qualified basis; source lines 47–48 discuss matching and missing rows.
- Reject `MISSING_MATCHING_ROWS part_of LEFT_OUTER_JOIN` (`edge-1314592e45c1`):
  source lines 62–63 describe an application, not a component–whole relationship.

The saved immutable version is **v1**, SHA-256
`2106b57c629606909d85fca6a8d15c739d50a892a1d59600a1d8cae3390e820d`.
It retains rejected edges with their decisions; only approved edges enter context.
No new node or replacement edge was invented. NULL semantics remains missing,
and two nodes are isolated after rejection. Approval is synthetic review, not
Professor Alawini's approval or validation of the whole curriculum.

An initial HTTP draft export was mislabeled as the saved snapshot. Independent
review caught its DRAFT status/encoding differences. It remains preserved as
`reviewed_draft_http_export.json`; `reviewed_graph_v1.json` is now a byte-for-byte
copy of the actual immutable v1 snapshot with the matching hash above. The opt-in
validator now exports saved snapshot bytes directly.

## Mapping, submissions and actual model results

Two assignments were created and locally published as `PUBLISHED_LOCAL_DEMO`:
`phase3-foundation` / `sql_join_01` and `phase3-later` / `sql_join_02`, both bound
to source version 1 and graph v1. Draft access was denied before publication.
This does not publish anything natively inside PrairieLearn.

The explicit simulated-instructor mapping `JOIN_PREDICATE → JOIN_CONDITION`
is recorded in each assignment's grading configuration, with reviewer identity
and source rationale. Source lines 37–38 show the same ON equality used by the
canonical exercise. This is a reviewed local equivalence, not automatic ontology
alignment. Original graph IDs and saved bytes remain unchanged. Existing question
tags remain candidate associations; provenance separately lists graph-backed tags
and tags absent from the graph, including NULL_SEMANTICS for the later question.

| Scenario | Learner | Attempt ID | Grade | Delivered inference status |
|---|---|---|---:|---|
| First wrong foundation | S001 | `demo-e693b1c2d65625c97be151ce` | 0 | `live_success` |
| Correct foundation | S002 | `demo-14e77fa075d15e2279ee7dc3` | 1 | `provider_error_fallback` |
| Later wrong join | S001 | `demo-86644cec4e4a0549a55b9193` | 0 | `live_success` |
| Contrasting history, same wrong join | S002 | `demo-889ff1e1dcea57784f7cb35a` | 0 | `live_success` |
| No prior history, wrong join | S003 | `demo-20c5dbe97d36c374caf20a75` | 0 | `live_success` |
| Correct retry | S001 | `demo-23a3a878f8c5e36237876227` | 1 | `provider_error_fallback` |
| Unsupported query / SELEC typo | S003 | `demo-9f5f69ba6ca227bc190efd95` | 0 | `provider_error_fallback` |
| Correct retry | S003 | `demo-e2484e5d7185cbbba1aed388` | 1 | `provider_error_fallback` |

All eight calls returned actual Qwen responses. Four were rejected by existing
output validation, including concept-gap lists for correct/nonsemantic outcomes;
the delivered results were deterministic fallbacks, not accepted Qwen guidance.
The status name `provider_error_fallback` does not imply transport failed here:
the captured responses and validation `ValueError` distinguish the failure.

The S001/S002 later contexts contain reviewed prerequisite `JOIN_CONDITION`
with contrasting prior estimates **1/3 versus 2/3**. These are unvalidated Beta
heuristics. Their accepted Qwen feedback texts are nevertheless identical and
omit a history-supported prerequisite recommendation. Terra's independent
feedback review therefore marks **G8 FAIL**. Context availability and the retained
API `personalized` flag do not prove output adaptation. The UI now states this
explicitly. No prompt, sampling parameter or guard was changed to hide the result.

The accepted semantic guidance is broadly relevant, with imprecise NULL-extension
wording in two outputs. No full answer SQL or hidden rows appeared in the eight
reviewed feedback texts; naming a required join is still a substantive hint, and
lesson citations can lead to worked examples. This screening is not pedagogical
endorsement or a complete answer-leakage proof.

## Delivery, isolation, analytics and persistence

Complete example lineage: source above → Qwen graph → Terra review → simulated
edge decisions → v1 → `phase3-later` → S001 attempt
`demo-86644cec4e4a0549a55b9193` → durable job `job-6f29867eff7648a8` → trusted
grade 0 / `missing_unmatched_rows` → prior S001 foundation evidence → mapped
JOIN_CONDITION prerequisite → actual Qwen response → learner HTTP/UI → instructor
read path → deterministic scoped analytics. Individual times and all request
contexts are recorded in the local acceptance artifacts.

The new instructor-only `GET /api/instructor/feedback?course_id=...&attempt_id=...`
reads the **same durable job projection** as the learner API, including actual
text, validation status and provenance. It does not display separately recomputed
submission feedback or regenerate output. Course, assignment, question, owner,
SQL and grounding associations are checked. Pending jobs remain pending.
`GET /api/instructor/analytics?course_id=...` returns deterministic course-filtered
counts, observed errors, contributing attempt IDs and improvement transitions.
These are shared synthetic lab instructor roles, not institutional course ownership.

Verified through HTTP and real Chromium: published student access, actual learner
feedback, identical instructor job content, and class JSON. Cross-student feedback
and student analytics access were denied; wrong-course instructor lookup failed.
Duplicate replay preserved its job and attempt; conflicting feedback modes and
wrong graph bindings failed. Current/equal/future evidence is excluded. A separate
backdated **synthetic isolation probe** in another course left all eight rebuilt
contexts and this course's analytics unchanged; this is a deterministic adversarial
check, not an extra live Qwen case or real historical event.

Class totals: 3 synthetic learners, 8 attempts, 3 correct, 5 incorrect; four
semantic mismatches and one unsupported query. Two same-assignment improvement
transitions are traceable to S001/S003 attempt IDs. One extra other-course probe
remains outside these totals. Tags and heuristic profiles are descriptive signals,
not proven misconceptions, validated mastery, or learning gains.

Receipt-verified stop/start preserved all eight exact learner/instructor job
responses, timestamps, analytics and graph hash. Both live text and fallback text
survived. No unrelated process was stopped. The local model remained unchanged.

## Engineering changes and reproducibility

Minimal changes reuse existing registries, queue, SQLite records, provider and UI:
explicit reviewed mapping; approved-prerequisite history retention; exact instructor
feedback readback; scoped analytics; supported question selection; truthful context
badge; and opt-in `scripts/verify_live_qwen.py`. No dependency, service, framework,
model launcher, schema column, extraction replacement or institutional auth was added.

Use the existing `start_full_sandbox.ps1 -LocalModel` with a fresh output root.
Upload the supported text lesson, retain the fresh graph, obtain independent
review, use simulated instructor review/save, and publish the two supported
assignments with the explicit mapping. Stop **only the receipt-verified isolated
background worker** before the capture harness; it uses the same durable worker.
Then run, substituting that run's paths and IDs:

```powershell
python scripts/verify_live_qwen.py --launch-receipt artifacts/phase3/run/runtime/launch.json --course phase3-sql --foundation-assignment phase3-foundation --later-assignment phase3-later --output artifacts/phase3/acceptance --ack-isolated-synthetic-local
# After receipt-aware service stop/start with the same output root:
python scripts/verify_live_qwen.py --launch-receipt artifacts/phase3/run/runtime/launch.json --course phase3-sql --foundation-assignment phase3-foundation --later-assignment phase3-later --output artifacts/phase3/acceptance --ack-isolated-synthetic-local --verify-restart
```

The harness exits unsuccessfully when accepted live feedback falls back; that
failure is retained. It never auto-approves a graph or grants pedagogical acceptance.
Ordinary CI remains deterministic and independent of installed Qwen.

Local raw artifacts under ignored `artifacts/phase3/`: `original_source.md`,
`source_metadata.json`, `qwen_generated_graph.json`, `kg_quality_review.json`,
`instructor_review.json`, `reviewed_graph_v1.json`, `published_assignments.json`,
`acceptance/model_calls.json`, `acceptance/live_acceptance.json`,
`feedback_quality_review.json`, `engineering_review.json`, restart/isolation/browser
verification JSON, original failure logs and screenshots. They are not uploaded
with source code. Public code alone does not include these local run artifacts.

## Acceptance gates

| Gate | Status | Evidence / limitation |
|---|---|---|
| G1 — Local Qwen | PASS | Actual existing-provider inference; effective model/digest recorded |
| G2 — KG extraction | PASS | Fresh local Qwen graph, no synthetic fallback |
| G3 — KG quality | PASS | Terra review accepted narrow scope after explicit rejection/correction; low coverage scores remain |
| G4 — Instructor review | PASS | Two qualified approvals, one rejection, immutable v1; simulated approval only |
| G5 — Assignment | PASS | Two graph-bound local publications; unpublished access denied |
| G6 — Student flow | PASS | Eight synthetic graded/persisted/delivered lifecycles; four delivered fallbacks |
| G7 — Longitudinal history | PASS | Captured contrasting prior-only prerequisite evidence; isolation checks |
| G8 — Personalized feedback | FAIL | Four validation fallbacks; identical contrasting-history live text |
| G9 — Student delivery | PASS | Actual authorized API/HTML/Chromium content; fallback status retained |
| G10 — Instructor delivery | PASS | Exact job readback and scoped deterministic class analytics |
| G11 — Persistence | PASS | Eight responses, analytics and saved graph identical after restart |
| G12 — Regression | PASS | Final 345 tests passed in 102.935s; 7 browser tests passed in 70.034s; no failures or skips |
| G13 — Independent review | PASS | Both important engineering findings resolved and independently verified; G8 research-quality failure retained |
| G14 — Repository | NOT RUN | Final branch synchronization/CI receipts belong in the GitHub handoff |

Lint/format, scoped mypy (existing three-file scope), pip/config checks, Bandit,
dependency audit and a 45-file code-only wheel passed. Full-history publication
scan and exact-commit GitHub workflows are final handoff gates.
No actual approved real-course PrairieLearn deployment, trusted institutional
identity, research approval, learning outcome or production readiness is established.
