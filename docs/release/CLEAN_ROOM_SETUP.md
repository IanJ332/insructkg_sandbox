# Clean-room Windows reproduction

1. Clone current main into a new directory. With Python 3.11 or 3.13 create a new `.venv`, install `requirements-dev.txt`, and run `python -m pip check`. No existing environment/state is required.
2. Run `python -m playwright install chromium`. Use the standard browser cache or explicitly configure `PLAYWRIGHT_BROWSERS_PATH` on this computer.
3. Run `scripts/start_full_sandbox.ps1 -Python <absolute-new-venv-python> -Deterministic -OutputRoot <new-output-folder> -Port 8810`. It generates synthetic fixtures and starts dashboard/worker with submission/EM/project database and separate job store. `runtime/launch.json` records owned processes, environment and output paths.
4. Poll `/health`, open `/login`, choose the simulated instructor, create a course/module, upload the supplied lesson, review/save a graph, and publish locally. Choose S001 to submit SQL and inspect grading/feedback. Root README covers EM/projects/analytics.
5. Run the full browser test with `SIIP_RUN_FULL_BROWSER=1` as shown in README. It initializes its own data, drives both roles, verifies lineage, restarts the dashboard, and confirms persisted assignment visibility after fresh login. Evidence goes to ignored `artifacts/full-browser-*`.
6. Stop launcher services with `scripts/stop_full_sandbox.ps1 -OutputRoot <same-output-folder>`. It verifies checkout/script identity before stopping recorded PIDs. Restart with identical arguments and inspect the same assignment, attempt/profile and feedback. Never delete stores as an error-recovery shortcut.
7. Optionally stop and restart with `-LocalModel` after installing Ollama/model independently. Configure `SIIP_LLM_BASE_URL` and `SIIP_LLM_MODEL`; the launcher queries installed model metadata and never downloads weights or assumes a GPU.

Linux/macOS: use `.venv/bin/python` and explicitly configure development auth flags plus `SIIP_DATA_DIR`, `SIIP_DB_PATH`, `SIIP_FEEDBACK_JOBS_DB`, `SIIP_DEMO_STATE_DIR` and `SIIP_DEMO_ARTIFACT_DIR` under a new ignored run root. Initialize public data, then run `scripts/dashboard.py` and `scripts/feedback_worker.py` in separate terminals on loopback. Stop owned processes with SIGTERM.

Docker Desktop/Compose is required only for native PrairieLearn: `scripts/manage.py start`, `smoke.py`, `tests/e2e/prairielearn_flow.py --ack-local-synthetic`, persistence probe, then stop. Do not point synthetic commands at an institutional course/database.

The professor video stays an external historical artifact. Fresh verification must not depend on its databases, paths, model or recordings. Its unreviewed feedback is not validated teaching material.

MP4 packaging is optional for the browser smoke test. Playwright's minimal encoder can preserve and decode the original instructor/student WebMs but cannot necessarily mux/concatenate MP4. The test verifies all UI/persistence/restart assertions in this case and records MP4 acceptance as false. To create a new professor MP4 package, separately provide a full FFmpeg build (PATH or recorder `--ffmpeg`), as documented in `docs/demo/RECORDING_RUNBOOK.md`. No encoder/model download is required for the deterministic application or browser acceptance.
