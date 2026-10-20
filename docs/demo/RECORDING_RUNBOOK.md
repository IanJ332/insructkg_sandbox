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

- The dashboard labels the actual graph extraction mode: local extraction or an explicitly
  labelled **synthetic fixture** fallback. Upstream InstructKG execution must be independently
  verified before making that claim; a local fallback never constitutes upstream execution.
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
  --dwell-seconds 30 `
  --minimum-professor-seconds 480 `
  --require-course-graph `
  --feedback-timeout 240 `
  --headless
```

`--dwell-seconds` controls how long each named, already-verified evidence state remains readable
after capture. The default is 1.5 seconds for engineering smoke tests; 30 seconds across the current evidence captures produces approximately 9–11 minutes and is appropriate
for the professor-facing run. This changes presentation time only, not mutations or timestamps.

Use `--no-headless` for a visible dress rehearsal. Use `--ffmpeg C:\path\to\ffmpeg.exe` to select a
full FFmpeg build. The runner prefers the optional installed `imageio_ffmpeg` full build before Playwright's bundled encoder. The verified local full encoder is `C:\Users\ian\Desktop\PROJECT\insructkg_sandbox\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe`. No encoder download is required in this environment. That bundled Windows
binary commonly decodes/encodes WebM/VP9 but lacks an MP4 muxer and concat filter. In that case the
runner preserves and probes the original instructor/student WebMs, records the exact limitation in
`run_manifest.json`, and does **not** claim an MP4 exists.

## What the runner proves

The instructor and student operate in separate 1920×1080 browser contexts. Browser forms perform
all mutations. After every mutation, the runner checks persisted state through an authenticated
read-only API or a rendered-state assertion before appending a completed event:

1. Instructor login, fresh course/module creation, lesson upload associated to both, stored source hash.
2. Labelled KG generation/fallback, at least two nodes and one directed edge, edge approval, saved version.
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
.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p test_professor_demo_script.py -v
```


## Required files and actual acceptance

The exact deliverables are `videos/SIIP_Professor_Full_Sandbox_Demo.mp4` and
`videos/SIIP_Uncut_Engineering_Verification.mp4`. The professor cut concatenates measured completed
action segments; phase slates act as concise captions. `--minimum-professor-seconds 480` rejects a
short recording. Choose 30 seconds dwell for the full run and inspect the resulting duration;
no frozen synthetic frames or manufactured timecodes are appended to reach the requested duration.
The completed status requires both MP4s, decoded valid raw videos at 1920×1080, and the minimum.

The engineering MP4 concatenates the **complete instructor context, then the complete student
context**. The contexts execute concurrently; this is explicitly not a chronological composite.
It retains login, idle waits, all action failures, and recording tails. Original actor WebMs and
`videos/uncut_segments.json` preserve the exact sources and segment durations. Failed runs preserve
videos, screenshots, action statuses, logs, and a failed manifest; reruns use a new output directory.

`--require-course-graph` is mandatory for the final integrated recording. It verifies that the
completed feedback's actual grounding identifiers equal this run's uploaded source SHA, source ID,
selected graph, saved version, and published assignment. An absent integration is labelled
`NOT_CONNECTED` in short compatibility runs and fails the final strict run. Extraction classification
comes from the actual graph record and may be local extraction or explicitly labelled fixture
fallback. Neither is claimed to be original upstream InstructKG execution.

The recorder reads the same SQLite database as the services to assert the exact newly submitted
attempt and its deterministic grade, exactly one additional S001 attempt, and a persisted concept
profile. A DOM history row from a previous attempt cannot satisfy this check. Nested learner JSON
is inspected for hidden reference SQL before and after project approval.

## Isolated complete browser test

This test starts its own dashboard and feedback worker on a free port in 8890–8989, uses a fresh
synthetic database and independently initialized labelled public contract fixtures, and preserves artifacts under `artifacts/full-browser-*`. It does not mutate a
shared demo service. Run it in the original or integration checkout using the available Python:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\AI\Cache\Playwright'
$env:SIIP_RUN_FULL_BROWSER = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p test_full_sandbox_browser.py -v
```

In a worktree without its own virtual environment, substitute the original checkout's absolute
`.venv\Scripts\python.exe` path. The test requires the integrated course graph consumption path and uses zero presentation dwell while retaining the same
browser mutations and persisted assertions. Its short recordings are engineering test evidence,
not the 8–12 minute professor deliverable. Run the strict final command against the running final
service only after integrating the graph consumption changes.
