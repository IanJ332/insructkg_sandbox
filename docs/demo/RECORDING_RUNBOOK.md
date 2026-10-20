# SIIP professor demonstration recording runbook

This runbook records the existing local dashboard through real Playwright interactions. It does
not reset a database, seed hidden success records, call demonstrated-phase mutation APIs directly,
or publish anything. Before opening the browser, it explicitly calls the repository's
`seed_fixture_histories()` preparation contract. That contract grades and persists three stable,
locally authored prior attempts for S001/S002 through the normal submission repository. The runner
exports the receipt, classification, and actual persisted attempts as
`outputs/student_profiles/00_fixture_history_preparation.json`; they are demonstration fixtures,
not empirical records or injected mastery values. Every run uses unique lesson and assignment
identifiers so repeated recordings can coexist; the stable history fixture IDs are idempotent.
The current dashboard permits one EM reflection per student/question in its visible feedback UI.
If S001 already has a `sql_join_04` reflection, the runner stops and reports that exact limitation
rather than fabricating a second reflection or bypassing the browser. Use an isolated synthetic demo
database for a full repeat that must include the reflection action; preserve any existing research
database unchanged.

## Scientific and platform boundaries

- The dashboard's generated candidate graph is an explicitly labelled **synthetic fixture**. The
  upstream InstructKG extractor is unavailable in this checkout; the recording must not describe
  this fixture as actual InstructKG extraction.
- Assignment publication is **LOCAL SIIP ASSIGNMENT PUBLICATION — SYNTHETIC DEMO**. It is not
  native PrairieLearn instructor publication. The practice submission does execute the existing
  PrairieLearn Python grading bridge and deterministic SQL grader.
- Feedback provenance comes from the completed feedback-job record. If it reports deterministic
  fallback, the recording and handoff must say so; do not call it live LLM inference.
- S001/S002, their histories, the lesson, and all course activity are synthetic.
- The current project UI uses the student's stored synthetic interest profile; it does not offer a
  free-form interest picker. The runner demonstrates profile-informed generation without claiming
  an interactive interest-selection control.

## Preflight

Use a fresh PowerShell window from the repository root. Keep the existing databases; do not invoke
reset targets.

```powershell
$env:SIIP_ENV = 'development'
$env:SIIP_ALLOW_SYNTHETIC_AUTH = '1'
$env:SIIP_ASYNC_FEEDBACK = '1'
$env:SIIP_DB_PATH = (Resolve-Path 'artifacts/synthetic.sqlite3')
$env:SIIP_FEEDBACK_JOBS_DB = (Resolve-Path 'artifacts').Path + '\jobs\feedback_jobs.sqlite3'
$env:SIIP_FEEDBACK_SERVICE_URL = 'http://127.0.0.1:8080'
$env:SIIP_DASHBOARD_PORT = '8080'
New-Item -ItemType Directory -Force (Split-Path $env:SIIP_FEEDBACK_JOBS_DB) | Out-Null
.\.venv\Scripts\python.exe scripts\dashboard.py
```

In a second PowerShell window, set the same database variables and start the worker:

```powershell
$env:SIIP_DB_PATH = (Resolve-Path 'artifacts/synthetic.sqlite3')
$env:SIIP_FEEDBACK_JOBS_DB = (Resolve-Path 'artifacts').Path + '\jobs\feedback_jobs.sqlite3'
$env:SIIP_FEEDBACK_PROVIDER = 'local'
.\.venv\Scripts\python.exe scripts\feedback_worker.py --poll-interval 0.25
```

Verify the service without changing state:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
.\.venv\Scripts\python.exe scripts\record_professor_demo.py --help
```

The dashboard and worker must use the same `SIIP_DB_PATH` and `SIIP_FEEDBACK_JOBS_DB`. A feedback
timeout usually means those processes point at different files or the worker is not running.

## Record

The preferred output directory is outside Git and all video/image extensions are ignored by this
repository.

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\AI\Cache\Playwright'
.\.venv\Scripts\python.exe scripts\record_professor_demo.py `
  --base-url http://127.0.0.1:8080 `
  --lesson-path demo_materials\SYNTHETIC_SQL_JOINS_LESSON.md `
  --output-dir D:\AI\SIIP\demo\2026-10-20 `
  --dwell-seconds 20 `
  --headless
```

`--dwell-seconds` controls how long each named, already-verified evidence state remains readable
after capture. The default is 1.5 seconds for engineering smoke tests; 20–25 seconds is appropriate
for the professor-facing run. This changes presentation time only, not mutations or timestamps.

Use `--no-headless` for a visible dress rehearsal. Use `--ffmpeg C:\path\to\ffmpeg.exe` to select a
full FFmpeg build. The runner also discovers Playwright's bundled encoder. That bundled Windows
binary commonly decodes/encodes WebM/VP9 but lacks an MP4 muxer and concat filter. In that case the
runner preserves and probes the original instructor/student WebMs, records the exact limitation in
`run_manifest.json`, and does **not** claim an MP4 exists.

## What the runner proves

The instructor and student operate in separate 1920×1080 browser contexts. Browser forms perform
all mutations. After every mutation, the runner checks persisted state through an authenticated
read-only API or a rendered-state assertion before appending a completed event:

1. Instructor login, lesson upload, stored source provenance.
2. Fixture KG generation, at least two nodes and one directed edge, edge approval, saved version.
3. Local assignment draft and publication.
4. S001 assignment visibility and incorrect INNER JOIN submission to `sql_join_04`.
5. Deterministic 0% grade, queued job, completed async feedback and provenance.
6. S001 profile/history/recommendation and the actual S002 fixture-history recommendation.
7. Optional reflection persisted as `PROPOSED`.
8. Cohort analytics and instructor acceptance of the exact new EM evidence.
9. S001 project generation, instructor approval, and learner answer-key concealment.
10. A lineage/timeline generated only from operations that passed those assertions.

The phase slates, clicks, submissions, state changes, failures, and retries remain in the original
Playwright WebMs. `video_chapters.txt` is written only after both recording contexts close and is
derived from measured source-video-relative action markers—not from the suggested storyboard.

## Evidence layout and acceptance

Inspect these first:

- `run_manifest.json`: run status, record IDs, provider, encoder capability, probes, limitations.
- `README_DEMO.md`: concise factual handoff.
- `videos/`: preserved actor WebMs and, only when conversion validates, the two required MP4s.
- `screenshots/`: named phase-boundary browser captures.
- `outputs/`: API- or browser-backed JSON for all nine phases.
- `timeline/system_event_log.jsonl`: exact-schema actual timestamps.
- `timeline/video_action_markers.json` and `video_chapters.txt`: measured video mapping.
- `architecture/data_lineage.json`, `data_flow.mmd`, and `data_flow.png`: executed-record lineage.

A run is accepted only when `run_manifest.json` says `completed`, the required JSON/screenshots
exist, each raw video probe is valid with nonzero duration and 1920×1080 resolution, and any MP4
listed in the manifest also has a valid probe. A missing MP4 is a reported packaging limitation,
not permission to rename a WebM or declare success.

Run the focused contract check without launching a browser:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\e2e\test_professor_demo_script.py -q
```
