# SIIP Integrated Synthetic Research Sandbox

The [Phase 4 follow-up](docs/release/PHASE4_FOLLOWUP_ACCEPTANCE.md) verifies all six newly supplied PDFs and maps the now-readable proposal to the October meetings. It supplies bounded prior grade facts through a compact feedback contract; **B6 still FAILS**, and local release-candidate status remains withheld. Historical PR #7/#8 evidence below is preserved.

Phase 4's [research and live-model acceptance report](docs/release/PHASE4_ACCEPTANCE.md) withholds release-candidate status: **B6 FAIL**. The final run completed twelve persisted submission lifecycles with eight actual Qwen calls, six accepted outputs, two quality fallbacks, and four separate nonsemantic bypasses. [Research traceability](docs/release/PHASE4_RESEARCH_TRACEABILITY.md) and [representative legacy-stage execution](docs/release/PHASE4_LEGACY_STAGES.md) distinguish observed reuse from incomplete reproduction.

SIIP connects instructor lesson upload, source-grounded graph review, local SQL assignment publication, deterministic grading, asynchronous feedback, prior-only learner profiles, entrepreneurial mindset (EM) reflections, personalized projects, and instructor analytics. Four native PrairieLearn SQL question hooks are also included.

This is a **synthetic research sandbox**. Local `PUBLISHED_LOCAL_DEMO` publication does not publish an assessment inside PrairieLearn. All demo identities and histories are artificial. Local single-call Ollama extraction is labeled `LOCAL_LLM_ASSISTED_EXTRACTION`. The separately selected `ORIGINAL_INSTRUCTKG_CHUNK_ONLY` mode now executes pinned original PDF ingestion, concepts/roles, chunk evidence and relation judgment through instructor authoring. Embedding/clustering, institutional authentication, native dynamic publication, authentic student-data delivery, faculty endorsement and classroom outcomes remain pending. Hosted dashboard startup is refused because trusted institutional authentication is not implemented.

[Original InstructKG integration acceptance](docs/release/ORIGINAL_INSTRUCTKG_INTEGRATION.md): **Original InstructKG Chunk-Based Integration Verified**. The real synthetic PDF produced 6 chunks, 28 concepts and 61 judged pairs. Independent review supported 4 of 33 edges, which were saved after synthetic instructor review. Four local assignments, reviewed nonidentity question mapping, ten submissions across two students, shared instructor/student delivery and actual restart persistence were verified. **B6 remains FAIL**: 1 of 6 actual Qwen feedback outputs was accepted, 4 triggered quality fallbacks and 1 triggered a provider-error fallback. Local Backend Integration Release Candidate is withheld.

The [post-implementation quality review](docs/release/ORIGINAL_INSTRUCTKG_INTEGRATION.md#post-implementation-quality-review) preserves that milestone and its six historical feedback outcomes. Version 2 separately judges both original pair orientations and permits only hash-bound, explicitly reviewed whole-chunk metadata exclusions. On the identical PDF it extracted 25 concepts and judged 122 directions; Terra supported 5 of 78 edges, so unreviewed KG quality still fails. Two additional controlled feedback replays also failed independent pedagogical/non-revealing review; they were not new student deliveries. The historical provider fallback is now traced to output leakage validation, with explicit failure-stage provenance in new records. **B6 remains FAIL.**

[Phase 3 live Qwen acceptance](docs/release/PHASE3_LIVE_QWEN_ACCEPTANCE.md): **Partial Local E2E**.
Fresh extraction and eight actual Qwen feedback calls ran; four feedback responses
passed validation and four fell back. Contrasting histories reached Qwen but did
not produce adapted feedback in this sample. Backend release-candidate acceptance
is withheld; deterministic regression success does not override that quality result.

## Install and run on Windows

Use Git and Python 3.11 or 3.13 (CI versions). Python 3.14 is additionally checked locally. No GPU, model, Docker, or paid API is needed for the default SIIP demo.

```powershell
git clone https://github.com/IanJ332/insructkg_sandbox.git
cd insructkg_sandbox
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\scripts\start_full_sandbox.ps1 -Python "$PWD\.venv\Scripts\python.exe" -Deterministic
Invoke-RestMethod http://127.0.0.1:8810/health
```

Open [local demo login](http://127.0.0.1:8810/login). Choose `instructor_alawini` to create a course/module, upload `demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md`, generate/review the labeled graph, save its version, create an assignment, and publish locally. Sign out and choose `S001` to submit SQL to that assignment, inspect grading/completed feedback, submit an optional EM reflection, and generate an interest-selected project. Return as instructor to review reflection/project and inspect analytics/lineage. These are simulated roles, not faculty review or SSO.

The launch receipt and submission/EM/project database and separate job store live under ignored `artifacts/full-sandbox/runtime`. Change `-OutputRoot` and `-Port` for independent runs. Stop only the recorded, verified SIIP processes with `scripts/stop_full_sandbox.ps1`. Restart with the same output root to preserve state. See [clean-room setup](docs/release/CLEAN_ROOM_SETUP.md).

## Optional installed local model

With Ollama and a model already installed, stop the deterministic service, then opt in:

```powershell
$env:SIIP_LLM_MODEL = 'qwen3:8b'
$env:SIIP_LLM_BASE_URL = 'http://127.0.0.1:11434/v1'
.\scripts\start_full_sandbox.ps1 -Python "$PWD\.venv\Scripts\python.exe" -LocalModel
```

The launcher downloads no model. Extraction/feedback failures retain visible fallback labels. Provider/model/digest, prompt version, source/graph lineage, validation state, and measured latency are retained when available; a missing digest stays unknown. Successful inference does not establish pedagogical correctness. Known unsupported COUNT/grouping diagnoses trigger a review-required fallback; accepted model guidance remains unreviewed.

## Validation

```powershell
$env:SIIP_ENV = 'development'
$env:SIIP_ALLOW_SYNTHETIC_AUTH = '1'
$env:SIIP_DATA_DIR = "$PWD\artifacts\public-data"
.\.venv\Scripts\python.exe scripts/init_public.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
$env:SIIP_RUN_FULL_BROWSER = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p test_full_sandbox_browser.py -v
```

The full browser test starts isolated services, drives instructor/student flows, verifies persisted graph consumption, and restarts the dashboard. Browser tests are reported separately from unit/integration totals. Native PrairieLearn UI/Postgres restart tests require Docker; GitHub's Local platform integration workflow runs them. [Release evidence](docs/release/RELEASE_TEST_EVIDENCE.md) records actual counts and failures.

Browser verification needs Chromium and its bundled WebM encoder. MP4 professor-package creation additionally needs a full FFmpeg build on PATH, the optional `imageio_ffmpeg` package, or the recorder's `--ffmpeg` parameter. The browser test preserves valid raw WebM evidence when that optional MP4 capability is absent; it does not mark MP4 recording acceptance as passed. With a full encoder, the original strict recording checks still apply. Existing professor videos remain external artifacts.

## Maintained layout and entry points

| Area | Location / entry point |
|---|---|
| HTTP UI, authorization, JSON API | `scripts/dashboard.py` |
| Async queue and worker | `siip/jobs.py`, `scripts/feedback_worker.py` |
| Authoring, reviewed graph, learner lifecycle | `siip/demo_authoring.py`, `demo_kg.py`, `demo_student.py` |
| KG extraction and grounding | `siip/local_kg_extractor.py`, `assignment_grounding.py`, `instructkg_schema.py` |
| Model feedback and SQL grading | `siip/feedback.py`, `grader.py`, `sql_worker.py` |
| Profiles, EM, projects, analytics | `siip/store.py`, `em_repository.py`, `project_generator.py`, dashboard |
| Native PrairieLearn course | `prairielearn-course/questions`, `courseInstances`, `siip/pl_bridge.py` |
| Evaluation/reproducibility | `scripts/experiment_runner.py`, `benchmark_adapters.py`, `research_tests` |
| Deployment/CI | `infrastructure`, `.github/workflows`, `scripts/manage.py` |
| Tests/demo tools | `tests`, `tests/e2e`, `demo_materials`, `record_professor_demo.py` |

`siip` lives under `prairielearn-course/serverFilesCourse`. Its wheel contains the library; UI/demo tools run from a source checkout.

API index: `GET /health`; development-only `POST /api/auth/synthetic-session`; instructor `/api/demo/{lessons,graphs,assignments,lineage,events}` reads and `/api/demo/lessons/upload`, `/api/demo/kg/{generate,review,save}`, `/api/demo/assignments/{create,publish}` writes; learner `POST /practice`, signed `GET /api/feedback?job_id=...`, profile/recommendation and EM/project routes; service-key protected queue routes. [Architecture/contracts](docs/release/INTEGRATION_CONTRACTS.md) describe trust boundaries.

[Release audit](docs/release/FINAL_PR_AUDIT.md) · [Release report](docs/release/MAIN_RELEASE_REPORT.md) · [Cleanup](docs/release/REPOSITORY_CLEANUP_REPORT.md) · [Next phase](docs/release/NEXT_PHASE_BLOCKERS.md) · [Documentation index](docs/README.md)

Earlier Phase 2–5 reports remain historical evidence. Current release documents take precedence for counts, authentication, extraction and completion status. External professor recordings preserve original failures and model-quality limitations outside Git.
## Reproduce original chunk-based integration

The default install above reproduces the deterministic sandbox. The original mode additionally needs an authorized **external** Jeffry checkout/snapshot at `c34a7786528e78766f15d918ab17aca2a9f7dc0b`, a Docling-capable Python, cached Docling/tokenizer assets and an existing Ollama `qwen3:8b`. No upstream source or weights are bundled. Exact SHA-256 values for all ten imported source modules are enforced by `siip/original_instructkg.py`; a changed/missing module fails before execution. Redistribution permission remains unverified. Obtain source/access from the resource owners below rather than copying it into this repository.

Observed working runtime: Python 3.14.3, Docling 2.109.0, docling-core 2.103.1, docling-ibm-models 3.15.0, Torch 2.14.1, Transformers 5.20.2 and tokenizers 0.23.3. Original `main.py` imports its clustering module even though clustering is not executed: installed sentence-transformers 6.2.0, UMAP 0.5.12 and HDBSCAN 0.8.44 are therefore still import dependencies. [The full observed environment](docs/release/evidence/pr9_quality_review/runtime_versions.json) is an inventory, not a validated portable installation lock. Upstream's unpinned requirements include cluster-specific vLLM; this Ollama adapter does not initialize or require that backend. A newly provisioned heavy environment has not been installed/tested here.

The local test used existing Hugging Face caches for `docling-project/docling-layout-heron` revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` and `docling-project/docling-models` revision `fc0f2d45e2218ea24bce5045f58a389aed16dc23`. HybridChunker also needs the existing MiniLM tokenizer/config cache at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; the full MiniLM weights remain absent and are not needed for chunk-only execution. Set `HF_HOME`/`HF_HUB_CACHE` to the corresponding **existing authorized cache**. Worker execution sets offline mode; missing resources are an explicit failure. Do not download or replace weights as part of this procedure without separate authorization.

From the repository root, after the normal development install:

```powershell
# Substitute existing authorized local paths; this does not fetch source/models.
$env:SIIP_INSTRUCTKG_SOURCE_DIR = 'C:\authorized-reference\instructkg-jeffry'
$env:SIIP_INSTRUCTKG_PYTHON = 'C:\authorized-runtime\Scripts\python.exe'
$env:HF_HOME = 'D:\existing-cache\HuggingFace'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:PYTHONPATH = Join-Path $PWD 'prairielearn-course\serverFilesCourse'
.\.venv\Scripts\python.exe -c "from siip.original_instructkg import verified_source; print(verified_source())"

# Confirm the existing model; do not run ollama pull.
Invoke-RestMethod http://127.0.0.1:11434/api/tags
# Expected qwen3:8b digest:
# 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41

# Fixture authoring alone additionally requires reportlab (tested 4.4.9).
# Install that Python package separately if needed; it is not a model weight.
.\.venv\Scripts\python.exe -m pip install reportlab==4.4.9
$run = Join-Path $PWD ('artifacts\original-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
.\.venv\Scripts\python.exe scripts/create_original_integration_fixture.py --output-dir $run --content-exclusions docs/release/evidence/pr9_quality_review/content_exclusions.json
$env:SIIP_SYNTHETIC_PDF_MANIFEST = Join-Path $run 'synthetic_pdf_manifest.json'
.\scripts\start_full_sandbox.ps1 -LocalModel -OutputRoot (Join-Path $run 'live') -Port 8831 -Python "$PWD\.venv\Scripts\python.exe"
.\.venv\Scripts\python.exe scripts/validate_original_pdf_browser.py --base-url http://127.0.0.1:8831 --output-dir $run
```

Choose a free port and use it in both commands. The browser logs in as an explicitly synthetic instructor, creates the course/module, uploads actual PDF bytes and clicks **Original InstructKG (chunk only)** Generate. Fixture generation refuses to overwrite an existing PDF. The supplied exclusions are reviewed only for this fixture's exact Docling item references/text hashes; they are not a general metadata detector or faculty approval. Omit `--content-exclusions` to retain all text. For other documents, inspect Docling items and obtain a new explicit metadata review. Mixed chunks remain intact.

Inspect the candidate graph and its manifest: `chunks_original.jsonl` preserves all ingestion output, `chunks.jsonl` is the selected extraction view, and `content_selection.json` records every exclusion. `pairpackets_forward/reverse.jsonl` and `relations_forward/reverse.jsonl` retain both original judgments. Do not automatically reverse edges or choose between conflicting directions. Verify source bytes, original module hashes, pages, item hashes, counts and `fallback=false`. Have an independent reviewer (Terra High in this study) read the PDF and all generated relationships, then a synthetic instructor explicitly approves/rejects candidates and saves an immutable version. Mapping and publication follow the existing assignments UI. Runtime artifacts and full upstream prompt logs stay local.

**Clean-room status: BLOCKED for an unprovisioned checkout.** The repository alone lacks the authorized external source/runtime, cached Docling assets and Qwen weights; fixture authoring also needs the optional reportlab package. Local execution with the already provisioned resources succeeded. Clean source/fixture checks are separate from a fresh-machine dependency installation and from independent pedagogical review. [Detailed results and exact dependencies](docs/release/ORIGINAL_INSTRUCTKG_INTEGRATION.md#post-implementation-quality-review) preserve these boundaries.

## Research Resources, External Dependencies, and Follow-up Tasks

This checklist is for the next graduate research assistant. Statuses reflect evidence available in this checkout; a meeting mention is not delivery or approval. In each final table cell, request only the access/approval listed for that resource, then complete the stated verification. No requests have been sent to either contact. Do not commit private course PDFs, identifiable student records, raw sensitive research text, model weights, or secrets.

The authorized local path is degraded `ORIGINAL_INSTRUCTKG_CHUNK_ONLY`: preserve PDF/chunk provenance, extract concepts and roles, build evidence from actual chunk co-occurrence, judge candidate relations, then permit instructor review/versioning. This path is now verified through actual instructor authoring and student submissions; independent KG and feedback quality limitations remain explicit. Embedding and semantic clustering remain deferred until the original model stage is available. This is not a full reproduction of the paper. History-aware feedback quality B6 remains **FAIL**, and local release-candidate status remains withheld. See [current integration gates and evidence](docs/release/ORIGINAL_INSTRUCTKG_INTEGRATION.md), [historical Phase 4 follow-up](docs/release/PHASE4_FOLLOWUP_ACCEPTANCE.md), [research traceability](docs/release/PHASE4_RESEARCH_TRACEABILITY.md) and [legacy-stage evidence](docs/release/PHASE4_LEGACY_STAGES.md). The supplied third-year proposal is accessible and already reconciled; the missing Year 1 backend and full ASEE WIP are separate source-access limitations.

### Contact Group A — Previous Research Contributor / Original-System Faculty Lead

**Responsible contact:** Original research faculty lead — identity/contact to confirm. Verify the person and artifact owner from project records before contacting. The public Jeffry reference has a verified repository contributor, but artifact ownership and the appropriate contact are unknown. Do not infer a private checkpoint, ownership, faculty identity, or email from public authorship.

| Status | Resource / owner | Why needed; availability and blocker | Required access/approval; temporary path, next action, and verification |
|---|---|---|---|
| REQUEST NEEDED | Original deployment configuration — original-system lead/engineer TBD | Needed to reproduce runtime, packages, storage and supported configuration; no verified deployment bundle is available. | Continue only with the documented local synthetic workflow. Request a secret-free config from the verified owner; compare versions and verify original startup/health. |
| PARTIAL | Official `sentence-transformers/all-MiniLM-L6-v2` — public model source; local installer TBD | Needed for sentence embeddings/clustering. Revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` is in the HF cache, but only tokenizer/config files are present; `model.safetensors` and `pytorch_model.bin` are absent. No complete authorized local weights were found in the bounded inventory. | Embedding/UMAP/HDBSCAN is blocked; chunk-only evidence with an explicitly empty unavailable-cluster collection is the temporary path. Obtain approval for an authorized install or locate a complete local copy; verify revision, module/config files, hashes, and a known-input encoder run. No download is authorized by this checklist. |
| REQUEST NEEDED | Any custom/fine-tuned checkpoint — owner only if one exists | It is unknown whether research used a checkpoint in addition to public MiniLM; no evidence says the previous team owns a private MiniLM model. | Keep public weights and custom research checkpoint distinct. Ask whether a custom checkpoint was used, who owns it, and what access/rights apply; verify provenance and hashes if supplied. |
| PARTIAL | Original embedding/UMAP/HDBSCAN configuration and known-good outputs — original pipeline owner | Source configurations and prior invocation notes exist, but complete model execution and known-good clustering outputs are not established. An empty cluster artifact is not a good result. | Chunk-only evidence remains the workaround. Request a lawful input/config/output bundle; run the original stages on matching inputs and compare parameters, IDs, and hashes. |
| REQUEST NEEDED | Shareable original PDF/chunks/concepts/roles/clusters/relations — original artifact owner | Needed for stage-by-stage comparison and pedagogical review; rights to redistribute original course materials are not established. | Use only public/licensed or explicitly synthetic PDFs meanwhile. Identify owner and sharing terms; verify source/page/chunk lineage and expected artifacts without committing restricted material. |
| REQUEST NEEDED | Original Year 1 SQL Feedback backend and API definitions — system maintainer TBD | The paper documents a prior system, but complete backend/API source has not been located; reuse cannot be claimed without code evidence. | Keep the current local implementation; no migration is implied. Request authorized source/contracts, inspect actual functions, and compare I/O and failure behavior. |
| REQUEST NEEDED | PostgreSQL schema/migrations; Neo4j graph schema/synchronization — Year 1 maintainers TBD | Needed to compare original persistence and graph sync contracts; these artifacts are not verified available. | Keep local storage for now. Request schemas/migrations/sync code; verify transactions, identity mappings and version behavior before proposing changes. |
| REQUEST NEEDED | Trained semantic/non-revealing feedback model artifacts — model owner TBD | May be needed to reproduce prior feedback if separately trained; no artifact, owner or license is confirmed. | Do not assume one exists or substitute it. Ask about provenance, evaluation, rights and access; verify checksum and safe evaluation if received. B6 remains a separate failed gate. |
| REQUEST NEEDED | Implementation notes, known defects, deployment dependencies — previous engineering owner TBD | Needed to avoid repeating known failures; no complete owner-verified handoff bundle is established. | Request shareable notes; reconcile defects/dependencies against source and runtime evidence, then cite findings in the detailed report. |
| BLOCKED | Source access/redistribution rights and contributor contact — repository rightsholder/maintainer TBD | Read-only upstream source refs are available: `aalrabah/instructkg` `ade6263a348984cef848eae85dc3d3b15daeea09`; Jeffry `code-royce/instructkg`, branch `jeffry`, `c34a7786528e78766f15d918ab17aca2a9f7dc0b`. A README license claim exists, but LICENSE was absent in both inspected snapshots; redistribution terms are unverified. | Public visibility is not permission. Keep authorized read-only source references; confirm rightsholder/terms, verify pinned revision licensing or written permission, and recheck hashes before any allowed integration. |

### Contact Group B — Current Supervising Professor

**Responsible contact:** Professor Abdussalam Alawini. No message/access request has been sent. Do not ingest authentic student data or private course material until authorization and privacy safeguards are established.

| Status | Resource / owner | Why needed; availability and blocker | Required access/approval; temporary path, next action, and verification |
|---|---|---|---|
| ACCESS PENDING | Authorized PrairieLearn course/staging instance and instructor/developer role — Professor Alawini / institutional administrator | Needed for native course flow and permissions; local synthetic mode is not a real course. | Real-course acceptance is blocked; continue local synthetic work. Request scoped staging role/test course; verify identity, course ownership, least privilege and deployment route. |
| REQUEST NEEDED | Existing course/assessment configuration, approved course/assignment IDs and schema refs — Professor Alawini | Needed to bind concepts, assignments, grades and provenance; real IDs/config are not authorized here. | Use synthetic IDs locally only. Request sanitized schema/config and test IDs; verify ownership, mapping and graph-version binding in staging. |
| ACCESS PENDING | Real instructor materials/lecture PDFs — Professor Alawini / material owner | Needed for actual page/chunk provenance and concept review; only public/licensed or synthetic PDFs are currently appropriate. | Real-material evaluation is blocked. Request specific files and processing/retention scope over an approved channel; verify rights and handling before ingest. Keep private PDFs and extracted text out of Git. |
| REQUEST NEEDED | Question-to-concept tag conventions and representative SQL questions — Professor Alawini | Needed to validate reviewed mappings against course assessment tags; local examples are synthetic. | Use synthetic tags temporarily. Request sanitized guide/questions; verify ID matching, reviewed non-identity mappings, collisions and assignment scope. |
| REQUEST NEEDED | Grading configuration and external-grader details/IDs — Professor Alawini / PrairieLearn administrator | Needed to compare local grades with course contracts; real grader settings are not approved. | Synthetic deterministic grader only. Request sanitized settings and test credentials via approved secret storage; verify grades, bounded execution and errors in staging. |
| ACCESS PENDING | Real submissions or suitably de-identified dataset — Professor Alawini / data steward | Needed for history/feedback evaluation; no authentic dataset is authorized. | Authentic-data evaluation is blocked; synthetic records are temporary. First establish secure transfer/storage and minimization; request only approved de-identified data and verify scope/access logs. Never send identifiable records insecurely. |
| REQUEST NEEDED | Student-record permission/scope and FERPA, IRB or institutional review guidance — Professor Alawini with relevant offices | Required before collecting or researching interactions; no determination/approval is established. | Do not ingest authentic records meanwhile. Obtain documented guidance; verify approvals, notice/consent as applicable, retention/deletion, access and research-use conditions. |
| REQUEST NEEDED | Approved test cohort or explicitly approved synthetic stand-in — Professor Alawini | Needed for repeatable cohort criteria; repository demos exist, but no professor-approved cohort/dataset is established. | Existing synthetic fixtures are engineering fixtures only. Agree on dataset, assignments and criteria; verify reproducibility and absence of unauthorized identities. |
| REQUEST NEEDED | Review of representative generated KG relations — Professor Alawini | Needed for pedagogical acceptance; no faculty review/approval is claimed. | Relations remain candidates; simulated review is not Professor Alawini approval. Agree on sample/rubric and record reviewer, evidence, decisions and graph version. |
| REQUEST NEEDED | Student/instructor feedback acceptance criteria — Professor Alawini | Needed to assess usefulness, accuracy, non-revelation and uncertainty; B6 **FAIL** is current evidence, not course acceptance. | Preserve safeguards and report failure. Define rubric/cases, then verify both views use shared trusted records and preserve uncertainty/provenance. |
| REQUEST NEEDED | Final course integration and handoff — Professor Alawini / course administrator | Needed for authorized deployment, ownership, support and rollback; no production deployment is authorized. | Real deployment is a separate phase. Agree on staging-to-course criteria, operator/support roles and rollback; verify access revocation and handoff checklist. |

### Scope and completion boundaries

- **Current Local Engineering:** Verified `ORIGINAL_INSTRUCTKG_CHUNK_ONLY` workflow, PDF-byte provenance, original concepts/roles and chunk evidence/relation judgment, reviewed KG versions, Question-to-Concept Mapping, cross-assignment student profile/history, deterministic grading and shared feedback/instructor analytics. The detailed report records P1–P16 separately. Unreviewed KG pedagogical quality and B6 feedback quality failed; engineering execution does not establish production or research acceptance.
- **Research Reproduction Backlog:** Complete official MiniLM weights and pinned embedding config; original UMAP/HDBSCAN and semantic clustering outputs; original Year 1 backend/model artifacts and API/schema comparisons; PostgreSQL/Neo4j behavior comparison; lawful source/test artifacts; and full original-pipeline evaluation. Do not fabricate clusters or replace the original algorithm.
- **Real-Course Integration Backlog:** Authorized PrairieLearn environment/roles, real instructor materials, institutional authentication/deployment, approved assessment/grader configuration, privacy-reviewed student records, instructor graph review and course acceptance/handoff.
- **Deferred Research Objectives:** EM expansion, personalized-project research, non-programming assignments, four-course deployment and formal learning-outcome studies remain outside current local acceptance. Existing repository features or past demos do not mean those research objectives passed evaluation.
