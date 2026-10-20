# Supported integration and architecture contract

## Current runtime

The loopback dashboard owns role checks and authoring. Uploaded UTF-8 lesson bytes have stable document IDs, numbered versions and raw SHA256. Extraction derives candidate concepts/directed edges with quotes and offsets; instructor graph review is separate. Saving publishes an immutable graph version. Assignments bind source/course and saved graph version. Deterministic SQL execution owns grades. The durable queue records public grading observations, source/graph bindings, provider result status and measured latency. Workers use prior-only submission timestamps; learner responses omit reference SQL and worker credentials. EM/project decisions retain append-only history alongside current state.

Mutable drafts/authoring are intended for one dashboard process, not distributed editing. Published versions additionally use exclusive filesystem publication across processes. Research and demo runs require separate database/output roots. No authentic learner records are shipped or authorized by demo login.

## Future original InstructKG adapter

Input: authorized source bytes, raw hash, document/version/course/module IDs, configuration and explicit adapter identity. Output: upstream repository/revision, named stage outcomes, concepts/roles/order, directed relations, verbatim evidence with defined offset coordinates, raw/normalized hashes, provider/model/digest, prompt/pipeline version, measured elapsed time, rejection/fallback details and provisional review state.

`A depends_on B` means B is a prerequisite of A; `A part_of B` means A is a constituent of B. Known reversed-wording claims are rejected; lexical checks cannot prove relation semantics. Instructor review remains required before grounding. Source bytes, graph source version/course, hashes and assignment bindings must agree. Later draft reviews cannot alter a saved version used by an attempt.

`local_kg_extractor.py` / `demo_kg.py` run bounded Ollama extraction (`LOCAL_LLM_ASSISTED_EXTRACTION`) or a labeled synthetic fallback. `actual_instructkg_extraction` remains false. An upstream adapter must implement the original additional stages; relabeling the local adapter does not satisfy this contract. Original extraction, clustering, pedagogical structure and multi-stage validation remain future work.

## PrairieLearn contract

Four question directories implement native `generate(data)` / `grade(data)` hooks through `siip/pl_bridge.py`; configuration is in `prairielearn-course/infoCourse.json` and `courseInstances/Fall2026`. The bridge invokes the bounded SQL grader and exposes public feedback. Hidden cases/reference SQL remain server-side. Missing/group identity fails closed for individual personalization.

Native variants belong to PrairieLearn. Supplied native submission IDs become namespaced authoritative attempts. Events without such IDs get distinct provisional UUIDs; identical SQL does not imply identical attempts. Reconciliation is explicit and compares stored owner/question evidence. Service keys or signed per-job tickets establish queue/feedback access; caller-supplied student fields do not establish identity. Synthetic maps/dev CSV allowlists are not classroom policies.

The implemented CSV adapter accepts only its documented synthetic scope. The bounded GET snapshot adapter requires authorized scope, one owner per individual assessment instance, known questions, pending-grade deferral and explicit CSV/API overlap reconciliation. Attempts/checkpoints commit atomically and stale polls fail. Hosted authenticated polling has not been demonstrated by this release. No new PrairieLearn API or internal-database write is introduced.

`PUBLISHED_LOCAL_DEMO` changes only SIIP records. Native publication requires authorized course-repository synchronization using supported PrairieLearn mechanisms, instructor access restrictions, authentic variant/submission IDs, approved identity mapping and authorized feedback delivery. Resolve these before classroom use. Native dynamic publication is not a gate for this synthetic baseline.

Course materials remain accessible only through authorized instructor routes. Real materials/exports, restricted research graphs and raw runtime evidence stay outside public Git unless separately approved and sanitized.
