> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Repository audit — 2026-10-14

## Revisions and scope

Public checkouts are isolated under research/. Jeffry HEAD c34a7786528e78766f15d918ab17aca2a9f7dc0b and original HEAD ade6263a348984cef848eae85dc3d3b15daeea09 exactly match the supplied references. PrairieLearn documentation/source HEAD eaaa91843807411918d260475e0a9188bcc2c979. Runtime image will be recorded separately: a source checkout does not prove the container runs that commit.

Read: Jeffry README.md, CLAUDE.md, source stages, findings.md investigation headings and relevant operational findings, testing_cmds.md SQL run log; original architecture and dependencies; PrairieLearn docs/installing.md, question/server.md, elements/pl-string-input.md, api.md and Python lifecycle source. Original InstructKG supplies the extraction architecture; Jeffry adds provider adapters, vLLM batching, OCR controls, robust parsing, review packets and evaluation. No second extraction implementation is needed.

## Actual InstructKG pipeline

- ingest.py: Docling DocumentConverter + HybridChunker(MAX_TOKENS=8191, merge_peers=True). PDF stem becomes lecture ID; chunk IDs append indices, page provenance and neighboring chunk pointers are retained. Natural numeric PDF sorting is used for ingestion. `_scan` token selects full page OCR; untagged PDFs retain native text with bitmap OCR. Formula/code enrichment is enabled and may overwrite clean text.
- llm.py: concept extraction followed by per-concept role classification (Definition, Example, Assumption, NA). concept_to_id uppercases and replaces nonalphanumeric spans with underscores. Mention cards aggregate contextual occurrences. Lecture order in cards/pairpackets can be lexicographic, different from ingestion natural sort; preserve original temporal metadata rather than asserting chronological correctness.
- clustering.py: sentence-transformer embeddings, normalized vectors, UMAP and HDBSCAN; clusters supply additional shared context. Model downloads required even without a generative model.
- pairpackets.py: chunk and cluster co-occurrence, roles, snippets and temporal first introductions. relation_judger.py prefers chunk evidence, produces A/B objects (name, role), relation, justification, evidence_chunks, _meta.
- Allowed edges are depends_on and part_of; null means no relation, but `_meta._error` can mark invalid model output. Adapter must preserve that distinction. Parse errors and unknown labels are not usable teaching edges.
- main.py resumes intermediate files and filters concepts with fewer than three distinct chunks. Known unresolved issue: concept_cards.jsonl is not rebuilt after the mention filter, leaving orphan cards (findings 2026-07-08). Single PDF SQL runs historically yielded 13 chunks, two retained concepts and one relation; do not promise large fresh graphs.
- adapters.py supports OpenAI, Anthropic, local vLLM (hf/local aliases), legacy transformers. GPU paths are unsuitable for this Intel Mac. vllm==0.19.1 pin avoids upstream CUDA 13 dependency against prior CUDA 12.8 drivers. Do not install GPU stack into integration environment.
- Known operational risks: full-page OCR damages typed slides; formula/code recognition can corrupt numeric values; OpenCV headless packages can be overwritten; relation token overflow; failed fake-null resumes in older runs. Current judging propagates engine failures. Existing cards/chunks/relations can be consumed directly without any inference.

## Verified existing graph

out/relations_sql_qwen14b.jsonl: 469 records; 247 depends_on, 72 part_of, 150 null; 319 non-null edges; 121 distinct named concepts. Evidence spans many SQL lectures, not only the available JOIN PDF. No separate SQL feedback application, deterministic SQL grader, student identity layer or PrairieLearn integration exists in these repositories.

JOIN_OPERATION part_of LEFT_OUTER_JOIN has a justification describing the opposite composition. Preserve it unchanged in an unreviewed queue. INNER_JOIN and NULL concepts are absent as exact named nodes; explicit developer aliases/provisional nodes must be labeled. Existing graph edges are research output, not instructor-approved truth.

## PrairieLearn supported integration

Official installation: https://docs.prairielearn.com/installing/ . Bind course to /course in official Docker image, bind port to loopback. No core source patch. infoCourse.json, courseInstances/*/infoCourseInstance.json, assessments/*/infoAssessment.json define course, instance, assessment. Homework supports repeat submissions. Built-in pl-string-input multiline collects SQL; server.py grade(data) executes after element grading and sets score, partial_scores and feedback. Explicit escaped Mustache feedback in pl-submission-panel displays custom feedback. Libraries in serverFilesCourse are imported by the Python lifecycle (apps/prairielearn/python/prairielearn/internal/question_phases.py).

Select internal grading with an isolated bounded SQLite subprocess: SQL is data, never Python code. This requires no external-grader network or Docker socket mount. External graders are supported via documented grading configuration and results JSON, but require sibling containers/jobs mount and add risks with no MVP benefit. Do not assume external graders can call an LLM network service.

PrairieLearn owns its real variants/submissions/assessment attempts. server.py does not provide a documented universal student UID. Use feedback as immediate response and a separate authorized export/API mapping for longitudinal research. Do not insert fake PrairieLearn submission records. Synthetic fixture runner calls the same engine but stores source=synthetic_fixture.

## API and hosted lifecycle

Official docs https://docs.prairielearn.com/api/ list GET course_instances/:id/assessments, assessments/:id/assessment_instances, assessment_instances/:id/submissions and individual submission retrieval. Private-Token authentication inherits account permissions. Course Editor is distinct from instance Student data viewer/editor. No arbitrary submission-injection endpoint is documented. POST course/:id/sync synchronizes authorized Git content; do not invoke against existing courses. Hosted course space, Git integration, instance publishing/access configuration and instructor/data permissions require the user's institutional work. CS418 is out of scope.

## Selected architecture

One portable standard-library Python package inside course/serverFilesCourse, three thin question hooks, two SQLite teaching fixtures, persistent synthetic analytics database, JSON graph adapter and review overlay. Host local dashboard consumes the same package. Separate optional API inference interface is disabled by default; no paid calls without explicit authorization. Lightweight development venv and isolated optional extraction dependencies. Preserve upstream repositories unmodified. Docker startup and real browser verification remain separate milestones from unit hook tests.
