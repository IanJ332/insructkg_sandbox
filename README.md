# SIIP Integrated Synthetic Research Sandbox

Phase 4's [research and live-model acceptance report](docs/release/PHASE4_ACCEPTANCE.md) withholds release-candidate status: **B6 FAIL**. The final run completed twelve persisted submission lifecycles with eight actual Qwen calls, six accepted outputs, two quality fallbacks, and four separate nonsemantic bypasses. [Research traceability](docs/release/PHASE4_RESEARCH_TRACEABILITY.md) and [representative legacy-stage execution](docs/release/PHASE4_LEGACY_STAGES.md) distinguish observed reuse from incomplete reproduction.

SIIP connects instructor lesson upload, source-grounded graph review, local SQL assignment publication, deterministic grading, asynchronous feedback, prior-only learner profiles, entrepreneurial mindset (EM) reflections, personalized projects, and instructor analytics. Four native PrairieLearn SQL question hooks are also included.

This is a **synthetic research sandbox**. Local `PUBLISHED_LOCAL_DEMO` publication does not publish an assessment inside PrairieLearn. All demo identities and histories are artificial. Local Ollama extraction is labeled `LOCAL_LLM_ASSISTED_EXTRACTION`, separate from original InstructKG. Original upstream extraction, institutional authentication, native dynamic publication, authentic student-data delivery, faculty endorsement, and classroom outcomes are not established. Hosted dashboard startup is refused because trusted institutional authentication is not implemented.

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
