"""Focused, browser-free contracts for the professor recording runner."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
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

    def test_nested_learner_payload_rejects_hidden_answer_keys(self) -> None:
        with self.assertRaisesRegex(AssertionError, "reference_sql"):
            MODULE.assert_learner_payload({"project": {"milestones": [{"reference_sql": "SELECT 1"}]}})
        MODULE.assert_learner_payload({"submitted_sql": "SELECT 1", "grading": {"score": 0}})

    def test_profile_verification_requires_new_exact_persisted_attempt(self) -> None:
        store = Mock()
        record = {"question_id": "sql_join_04", "submitted_sql": MODULE.INCORRECT_SQL,
                  "grading": {"score": 0}}
        store.attempt_for_student.return_value = record
        store.profile.return_value = {"concepts": {"LEFT_OUTER_JOIN": {"attempt_count": 1}}}
        store.records.return_value = [record]
        self.assertEqual(MODULE.assert_persisted_attempt(store, "attempt-a", 0)["attempt_count_after"], 1)
        with self.assertRaisesRegex(AssertionError, "exactly one"):
            MODULE.assert_persisted_attempt(store, "attempt-a", 1)

    def test_required_deliverable_names_and_uncut_semantics(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("SIIP_Professor_Full_Sandbox_Demo.mp4", source)
        self.assertIn("SIIP_Uncut_Engineering_Verification.mp4", source)
        self.assertIn("uncut_segments = [(actor, 0.0, None) for actor in raw_videos]", source)
        self.assertIn('"uncut_semantics"', source)


if __name__ == "__main__":
    unittest.main()
