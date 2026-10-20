"""Real browser lifecycle with isolated services and persisted evidence.

Run explicitly with SIIP_RUN_FULL_BROWSER=1; no shared service is mutated.
All run artifacts, including failed browser videos, remain under artifacts/.
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "full_sandbox_recorder", ROOT / "scripts/record_professor_demo.py"
)
assert SPEC and SPEC.loader
RECORDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RECORDER
SPEC.loader.exec_module(RECORDER)


@unittest.skipUnless(
    os.environ.get("SIIP_RUN_FULL_BROWSER") == "1",
    "Set SIIP_RUN_FULL_BROWSER=1 for real Chromium lifecycle",
)
class FullSandboxBrowserTests(unittest.TestCase):
    def test_browser_lifecycle_persists_every_transition(self):
        output = (
            ROOT / "artifacts" / f"full-browser-{RECORDER.timestamp_slug()}-{uuid.uuid4().hex[:6]}"
        )
        output.mkdir(parents=True)
        port = None
        for candidate in range(8890, 8990):
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", candidate))
                    port = candidate
                    break
                except OSError:
                    continue
        self.assertIsNotNone(port, "No isolated local test port available")
        base = f"http://127.0.0.1:{port}"
        environment = dict(
            os.environ,
            SIIP_ENV="development",
            SIIP_ALLOW_SYNTHETIC_AUTH="1",
            SIIP_ASYNC_FEEDBACK="1",
            SIIP_DB_PATH=str(output / "synthetic.sqlite3"),
            SIIP_FEEDBACK_JOBS_DB=str(output / "jobs.sqlite3"),
            SIIP_DASHBOARD_PORT=str(port),
            SIIP_FEEDBACK_SERVICE_URL=base,
            SIIP_FEEDBACK_PROVIDER="deterministic",
            SIIP_DATA_DIR=str(output / "public-data"),
            SIIP_DEMO_STATE_DIR=str(output / "demo-state"),
            SIIP_DEMO_ARTIFACT_DIR=str(output / "backend-timeline"),
        )
        initialized = subprocess.run(
            [sys.executable, str(ROOT / "scripts/init_public.py"), str(output / "public-data")],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        (output / "fixture-preparation.log").write_text(
            initialized.stdout + initialized.stderr, encoding="utf-8"
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        processes = []
        handles = []
        try:
            for name, arguments in (
                ("dashboard", []),
                ("feedback_worker", ["--poll-interval", "0.1"]),
            ):
                handle = (output / f"{name}.log").open("w", encoding="utf-8")
                handles.append(handle)
                processes.append(
                    subprocess.Popen(
                        [sys.executable, str(ROOT / f"scripts/{name}.py"), *arguments],
                        cwd=ROOT,
                        env=environment,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                    )
                )
            deadline = time.monotonic() + 45
            while True:
                try:
                    with urlopen(base + "/health", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        self.fail(f"Isolated dashboard did not start; logs: {output}")
                    time.sleep(0.25)
            args = RECORDER.build_parser().parse_args(
                [
                    "--base-url",
                    base,
                    "--output-dir",
                    str(output / "evidence"),
                    "--dwell-seconds",
                    "0",
                    "--require-course-graph",
                ]
            )
            with patch.dict(os.environ, environment):
                try:
                    manifest = RECORDER.run(args)
                except RuntimeError as exc:
                    if (
                        str(exc)
                        != "Workflow completed but recording acceptance failed; inspect run_manifest.json"
                    ):
                        raise
                    manifest = json.loads(
                        (output / "evidence/run_manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(manifest["status"], "workflow_completed_recording_incomplete")
                    packaging = manifest["video_packaging"]
                    encoder = packaging.get("encoder") or {}
                    self.assertFalse(
                        all(
                            encoder.get(key)
                            for key in (
                                "has_mp4_muxer",
                                "has_trim_filter",
                                "has_setpts_filter",
                                "has_concat_filter",
                            )
                        )
                        and (encoder.get("has_h264_encoder") or encoder.get("has_vp9_encoder")),
                        "A full encoder must satisfy the original MP4 recording gate",
                    )
                    self.assertTrue(packaging.get("limitations"))
                    probes = packaging.get("raw_probes", {})
                    self.assertEqual(set(probes), {"instructor", "student"})
                    self.assertTrue(all(probe.get("valid") for probe in probes.values()))
                    self.assertTrue(
                        all(probe.get("resolution") == "1920x1080" for probe in probes.values())
                    )
                    self.assertFalse(manifest["recording_acceptance"]["accepted"])
                    self.assertIsNone(packaging.get("professor_mp4"))
                    self.assertIsNone(packaging.get("uncut_mp4"))
                    print(
                        "Browser workflow verified with valid WebM evidence; optional MP4 packaging unavailable.",
                        flush=True,
                    )
                else:
                    self.assertEqual(manifest["status"], "completed")
                    self.assertTrue(manifest["recording_acceptance"]["accepted"])
            self.assertEqual(
                manifest["course_graph_consumption"]["classification"], "REAL_PIPELINE_VERIFIED"
            )
            self.assertTrue(manifest["records"]["course_id"])
            self.assertTrue(manifest["records"]["module_id"])
            self.assertTrue(manifest["records"]["attempt_id"])
            self.assertTrue(manifest["records"]["evidence_id"])
            self.assertTrue(manifest["records"]["project_id"])
            self.assertTrue(
                (
                    output / "evidence/outputs/submissions/04_persisted_attempt_and_profile.json"
                ).is_file()
            )
            # Restart the dashboard against the same isolated persisted stores.
            processes[0].terminate()
            processes[0].wait(timeout=10)
            processes[0] = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/dashboard.py")],
                cwd=ROOT,
                env=environment,
                stdout=handles[0],
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urlopen(base + "/health", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                    break
                except OSError:
                    self.assertIsNone(processes[0].poll(), f"Restart failed: {output}")
                    self.assertLess(time.monotonic(), deadline, f"Restart unavailable: {output}")
                    time.sleep(0.1)
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                RECORDER.login(page, base, "instructor_alawini")
                page.goto(base + "/assignments", wait_until="networkidle")
                self.assertIn(manifest["records"]["assignment_id"], page.content())
                browser.close()
            print(f"Full browser evidence: {output}", flush=True)
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    unittest.main()
