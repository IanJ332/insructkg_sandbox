# Full requirements audit — October 19, 2026

This is the initial evidence-based audit of inherited prototype snapshot `7b13fa0`, followed by scoped authoring hardening. The integration owner must append the final exact commit, browser run, recording evidence, and CI results. No feature in this document is certified `VERIFIED_END_TO_END`: this audit did not execute the complete browser lifecycle. A passing component test demonstrates only its tested boundary.

The machine-readable coverage matrix is [REQUIREMENTS_TRACEABILITY.csv](REQUIREMENTS_TRACEABILITY.csv). Its rows include every journey transition, the four research objectives, security, extraction, observability, recording, and release requirements. [HIDDEN_GAPS.md](HIDDEN_GAPS.md) contains actionable findings, and [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) controls integration order.

## Source authority and limits

The supplied overnight request is available and was read in full. It describes the four Year 3 objectives, acceptance criteria, and reference hierarchy. The explicitly authorized `transcript.txt` in Downloads was located and read. Relevant faculty priorities are actionable instructor-aligned feedback, pedagogically sensible graphs, dynamic learner profiles, identification of common struggles, possible material ambiguity, comparisons among baseline/RAG/KG conditions, and future authorized treatment/control evaluation. These are paraphrases of imperfect transcription, not verbatim faculty quotations.

`SIIP_Reference_Pack_for_Local_Agent.zip` was not located in the narrowly inspected Downloads/Desktop top level or the SIIP subtree under `D:\AI`. The source manifest, Year 3 proposal PDF, supplied paper PDFs, and two Phase 5.6 logs therefore remain unavailable to this audit. Requirements attributed to the proposal use the user's supplied objective descriptions; they are not independently checked against the unavailable PDF. Research mechanisms in existing code and repository documentation are inspected implementation evidence, not a substitute for those references. No private PDF or transcript is added to Git.

External upstream, current GitHub/CI, deployed UI, and installed PrairieLearn compatibility must be verified by the integration and extraction owners. This audit does not infer them from historical completion reports. Existing repository audit/handoff documents were treated as historical context.

## Findings that control development

1. **P0: establish one complete local lifecycle.** `scripts/dashboard.py` contains upload, candidate generation, review, local assignment publication, learner submission, and queue routes. The existence of these routes does not establish their operation through browser interaction. Fresh integrated browser evidence and playable recordings remain release gates.
2. **P0: uploaded graph must reach feedback.** The inherited assignment route stores graph references only inside `grading_config`. `DemoStudentJourney` queues feedback without those references; `feedback.build_context` loads bundled static graphs and lecture evidence. This is a real disconnected producer/consumer boundary. The integration owner is implementing immutable assignment grounding through the feedback queue.
3. **P0: choose the intended graph explicitly.** Inherited assignment authoring selects `graphs[-1]`, accepts the form's course ID independently, and checks only that at least one edge was approved. This can associate the wrong graph/course and does not establish all selected relations were reviewed. Select a saved graph/version explicitly, derive source/course/module from that version, and describe review scope accurately.
4. **P0: extraction failure must become a persisted failure.** The inherited route sets `PROCESSING` before synchronous generation and has no local failure transition. An exception can leave a permanent processing indicator. Persist `FAILED`, show a retry action, and record the actual failed event.
5. **P1: course/module and interest collection were incomplete.** Inherited course IDs and learner interests are fixed in UI code or fixtures. This work adds local course/module persistence and typed source/graph assignment lineage; the integration owner connects browser selectors and interest selection. Existing fixture choices cannot be presented as newly collected interests.
6. **P1: audit permissions at HTTP boundaries.** New tests execute the actual local HTTP server with isolated databases. Instructor routes reject anonymous users and student sessions, mutation requires session-bound CSRF, cross-origin publication is rejected, and student profile/recommendation/EM endpoints reject access to another learner. The inherited overview route still exposes cohort aggregates without the authorization used by `/api/cohort-analytics`; the integration owner must resolve this consistency gap.
7. **Research integrity: distinguish mechanisms.** The inherited demo extractor is explicitly a deterministic synthetic fixture, not original InstructKG or local-model execution. Draft survey structures are present, but the inherited instrument page calls them validated. Synthetic reflection acceptance is a local review demonstration, not a validated EM measurement or authentic faculty approval.

## Changes delivered in the authoring worktree

`DemoAuthoringRegistry` now supports `create_course`, `list_courses`, `create_module`, and `list_modules`. `LessonRecord.module_id` and assignment course/module/source-version/graph-version fields persist as additive JSON fields, preserving existing version-1 files and old callers. When supplied, module and source lineage must agree with the selected course; an assignment source must be processed. Legacy assignment creation without these optional fields remains supported for old components, so the router must enforce the full contract for the new browser path.

Upload accepts Markdown/text UTF-8 only, rejects path/control-character filenames and binary content, preserves the synthetic banner, and verifies stored content by SHA-256. Multiple registry instances in one process now share the same directory lock; an isolated concurrent-upload test verifies versions are not lost. This is a single-process local registry; multiple independent processes must not share it as a database.

Processing transitions require `UPLOADED → PROCESSING → PROCESSED/FAILED`, permit retry from failure, and preserve immutable upload metadata. Assignment publication remains idempotent and explicitly `PUBLISHED_LOCAL_DEMO`, with `native_prairielearn_publication=False`.

`DemoStudentJourney` validates recognized synthetic students, feedback mode, bounded SQL and event keys, assignment publication metadata, and replay identity before persistence. Reflection ownership still comes from the existing repository lookup; a new negative test verifies another student cannot attach evidence to the attempt. Optional `feedback_grounding` is forwarded to the integration owner's queue contract when present. Deterministic grading is reused through `SubmissionRepository`, not reimplemented.

## Verification from this worktree

Executed with the original repository's `.venv\Scripts\python.exe`, isolated temporary directories/databases, and a server bound to loopback on an assigned ephemeral port:

| Scoped suite | Result | Boundary |
| --- | --- | --- |
| `test_demo_authoring.py` | 10 passed | Upload, persistence, versioning, course/module, lineage, concurrent instances, publication, invalid input |
| `test_demo_student.py` | 7 passed | Existing grader, diagnosis, queue, replay, history/recommendation, EM separation/ownership |
| `test_demo_security.py` | 7 passed | Actual HTTP authentication, role, CSRF, origin, draft visibility, cross-student checks |

These 24 tests establish `VERIFIED_COMPONENT_ONLY` for their boundaries. The new HTTP tests do not execute browser upload or inference and do not prove a full lifecycle. Existing regression totals from previous reports were not adopted as current results. The integration owner must run the complete regression suite after cherry-picking.

An additional broader `test_demo_*.py` run initially exposed a setup dependency in `test_demo_integration.py`: expected `deterministic_fallback`, actual `context_error_fallback`. The clean worktree lacks bundled `siip/data/lecture.json` and `existing_relations.jsonl`, which `feedback.build_context()` reads. Main identified the existing safe initialization contract: run `scripts/init_public.py artifacts/public-data` and set `SIIP_DATA_DIR` to that generated directory. This agent executed those commands against its isolated worktree and reran the entire `test_demo_*.py` set: **36 tests passed in 8.216 seconds**. No private lecture or research graph was copied. The initial failure is retained here so startup instructions must include fixture initialization; it is resolved for the configured component run, not an unresolved application defect.

## Objective coverage

**Objective 1:** Deterministic SQL execution, diagnosis, histories, recommendations, and async feedback services exist and have component tests. Fresh uploaded-material grounding and assignment identity propagation are critical integration work. Native PrairieLearn publication and local SIIP publication are distinct channels.

**Objective 2:** Existing optional prompts, reflection response storage, proposed evidence, review states, and summaries support a synthetic behavioral-observation workflow. Evidence is separate from technical mastery. No underlying entrepreneurial mindset change or validated measurement is established.

**Objective 3:** Existing project templates cover interest-dependent construction and ranked milestones using technical profiles and graph prerequisites. Interest collection and approved-only learner activity access need integrated browser verification. Reference SQL must remain instructor-only for both HTML and JSON views.

**Objective 4:** Existing cohort/profile analytics and draft evaluation instruments provide infrastructure. The initial implementation lacks complete assignment-scoped lineage and ambiguity evidence in the new workflow. Repeated errors can motivate `CANDIDATE_INSTRUCTIONAL_AMBIGUITY` for instructor review; they cannot establish a lecture defect or learning benefit. Study allocation, actual survey response collection, and institutional approval remain future work unless separately implemented and authorized.

## Release gate

Final acceptance requires fresh integrated state transitions, at least two synthetic learner histories, reviewed EM evidence and project, an assignment-grounded feedback result, truthful extraction/inference labels, complete linked artifacts, a played/inspected professor recording and uncut recording, executed browser tests, and exact local/remote/CI commit evidence. Until that evidence exists, report `COMPONENT_ONLY`, `NOT_CONNECTED`, or `BLOCKED` as appropriate. Only the integration owner can certify the complete release.
