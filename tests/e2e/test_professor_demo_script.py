"""Focused, browser-free contracts for the professor recording runner."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/record_professor_demo.py"
SPEC = importlib.util.spec_from_file_location("record_professor_demo", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProfessorDemoScriptContractTests(unittest.TestCase):
    def test_help_imports_without_starting_browser(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in (
            "--base-url",
            "--lesson-path",
            "--output-dir",
            "--headless",
            "--ffmpeg",
            "--dwell-seconds",
        ):
            self.assertIn(option, result.stdout)

    def test_marker_timecodes_are_measured_not_storyboard_constants(self) -> None:
        marker = MODULE.ActionMarker(
            phase="04 Student assignment",
            actor="student",
            source_video="student",
            started_utc="2026-10-20T01:00:00Z",
            completed_utc="2026-10-20T01:00:02Z",
            start_seconds=1.25,
            end_seconds=3.75,
            status="completed",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = MODULE.write_video_chapters([marker], Path(temporary))
            content = path.read_text(encoding="utf-8")
        self.assertIn("Derived after browser contexts closed", content)
        self.assertIn("source 1.250–3.750s", content)
        self.assertEqual(marker.duration_seconds, 2.5)

    def test_playwright_ffmpeg_discovery_and_probe_are_truthful(self) -> None:
        missing = Path("Z:/definitely-not-present/ffmpeg.exe")
        self.assertIsNone(MODULE.discover_ffmpeg(missing))
        self.assertEqual(MODULE.format_timecode(65.432), "01:05.432")

    def test_script_contains_scientific_boundary_labels(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("upstream InstructKG extractor is unavailable", source)
        self.assertIn("PUBLISHED_LOCAL_DEMO", source)
        self.assertIn("not native PrairieLearn", source)
        self.assertIn("separate", source.lower())


if __name__ == "__main__":
    unittest.main()
