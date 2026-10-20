"""Record the local SIIP professor demonstration with browser-backed evidence.

This runner intentionally drives the nine demonstrated phases through the existing
dashboard UI in separate instructor and student browser contexts.  Before those
actions, it explicitly prepares the repository's three labelled synthetic prior-
history fixture attempts so S001/S002 exercise contrasting real recommender paths;
it exports those persisted attempts and never treats them as measured outcomes. It
does not reset data, call phase mutation APIs directly, or claim that the fixture
graph is an InstructKG extraction. Read-only API requests are used after browser
mutations to prove that state was persisted.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

VIEWPORT = {"width": 1920, "height": 1080}
INCORRECT_SQL = (
    "SELECT d.department_name, COUNT(e.employee_id) AS employee_count "
    "FROM Departments d INNER JOIN Employees e "
    "ON d.department_id = e.department_id "
    "GROUP BY d.department_id, d.department_name ORDER BY d.department_name;"
)
REFLECTION = (
    "Missing records can hide departments from an operational report, causing a company "
    "to allocate staff or funding using an incomplete picture. Preserving unmatched rows "
    "makes the limitation visible before a decision is made."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def artifact_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def safe_entity(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._:@/-]", "-", value).strip("-./")
    return (value or "unknown")[:256]


def parse_duration(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_timecode(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


@dataclass
class ActionMarker:
    phase: str
    actor: str
    source_video: str
    started_utc: str
    completed_utc: str
    start_seconds: float
    end_seconds: float
    status: str

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


class RecorderClock:
    """Track real wall-clock and source-video-relative action boundaries."""

    def __init__(self) -> None:
        self.video_origins: dict[str, float] = {}
        self.actions: list[ActionMarker] = []

    def start_video(self, actor: str) -> None:
        self.video_origins[actor] = time.monotonic()

    @contextmanager
    def action(self, phase: str, actor: str) -> Iterator[None]:
        if actor not in self.video_origins:
            raise RuntimeError(f"video clock not started for {actor}")
        origin = self.video_origins[actor]
        start_monotonic = time.monotonic()
        started_utc = utc_now()
        status = "completed"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            self.actions.append(
                ActionMarker(
                    phase=phase,
                    actor=actor,
                    source_video=actor,
                    started_utc=started_utc,
                    completed_utc=utc_now(),
                    start_seconds=max(0.0, start_monotonic - origin),
                    end_seconds=max(0.0, time.monotonic() - origin),
                    status=status,
                )
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record and verify the local SIIP professor browser demonstration."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--lesson-path",
        type=Path,
        default=ROOT / "demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"D:\AI\SIIP\demo\2026-10-20"),
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headlessly (use --no-headless for a visible recording run).",
    )
    parser.add_argument(
        "--ffmpeg",
        type=Path,
        default=None,
        help="Optional FFmpeg executable. Auto-discovery includes Playwright's bundled binary.",
    )
    parser.add_argument("--feedback-timeout", type=float, default=90.0)
    parser.add_argument(
        "--dwell-seconds",
        type=float,
        default=1.5,
        help="Seconds to keep each named evidence state visible after its screenshot.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
        "host.docker.internal",
    }:
        raise ValueError("--base-url must identify the local SIIP service")
    args.base_url = args.base_url.rstrip("/")
    args.lesson_path = args.lesson_path.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.lesson_path.is_file():
        raise FileNotFoundError(f"lesson file not found: {args.lesson_path}")
    if args.feedback_timeout <= 0:
        raise ValueError("--feedback-timeout must be positive")
    if args.dwell_seconds < 0:
        raise ValueError("--dwell-seconds must be nonnegative")


def discover_ffmpeg(explicit: Path | None) -> Path | None:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        return candidate if candidate.is_file() else None
    on_path = shutil.which("ffmpeg")
    if on_path:
        return Path(on_path).resolve()
    roots = []
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured and configured != "0":
        roots.append(Path(configured))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "ms-playwright")
    roots.append(Path(r"D:\AI\Cache\Playwright"))
    for root in roots:
        if not root.is_dir():
            continue
        candidates = sorted(root.glob("ffmpeg-*/ffmpeg*.exe"), reverse=True)
        if candidates:
            return candidates[0].resolve()
    return None


def ffmpeg_capabilities(executable: Path) -> dict[str, Any]:
    def output(*arguments: str) -> str:
        result = subprocess.run(
            [str(executable), "-hide_banner", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout + result.stderr

    encoders = output("-encoders")
    formats = output("-formats")
    filters = output("-filters")
    return {
        "path": str(executable),
        "has_vp9_encoder": "libvpx-vp9" in encoders,
        "has_h264_encoder": any(name in encoders for name in ("libx264", "h264_nvenc")),
        "has_mp4_muxer": bool(re.search(r"^\s*E\s+.*\bmp4\b", formats, re.MULTILINE)),
        "has_concat_filter": bool(re.search(r"\bconcat\b", filters)),
        "has_trim_filter": bool(re.search(r"\btrim\b", filters)),
        "has_setpts_filter": bool(re.search(r"\bsetpts\b", filters)),
    }


def probe_video(executable: Path, video_path: Path) -> dict[str, Any]:
    if not video_path.is_file():
        return {
            "path": str(video_path.resolve()),
            "exists": False,
            "size_bytes": 0,
            "duration_seconds": None,
            "resolution": None,
            "codec": None,
            "decoder_exit_code": None,
            "valid": False,
        }
    result = subprocess.run(
        [str(executable), "-hide_banner", "-i", str(video_path), "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    details = result.stdout + result.stderr
    duration_match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", details)
    resolution_match = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", details)
    codec_match = re.search(r"Video:\s*([^,]+)", details)
    decoder_exit_code = result.returncode
    # Playwright's deliberately small FFmpeg build has no null muxer.  When
    # metadata inspection cannot decode to null, perform a full same-encoder
    # WebM transcode and discard only that temporary probe output.
    if decoder_exit_code != 0:
        probe_target = video_path.with_name(f".{video_path.name}.{uuid.uuid4().hex}.probe.webm")
        try:
            decode = subprocess.run(
                [
                    str(executable),
                    "-hide_banner",
                    "-y",
                    "-i",
                    str(video_path),
                    "-an",
                    "-c:v",
                    "libvpx-vp9",
                    "-deadline",
                    "realtime",
                    "-cpu-used",
                    "8",
                    str(probe_target),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=600,
            )
            decoder_exit_code = decode.returncode
        finally:
            probe_target.unlink(missing_ok=True)
    return {
        "path": str(video_path.resolve()),
        "exists": video_path.is_file(),
        "size_bytes": video_path.stat().st_size if video_path.is_file() else 0,
        "duration_seconds": parse_duration(duration_match.group(1)) if duration_match else None,
        "resolution": (
            f"{resolution_match.group(1)}x{resolution_match.group(2)}"
            if resolution_match
            else None
        ),
        "codec": codec_match.group(1).strip() if codec_match else None,
        "decoder_exit_code": decoder_exit_code,
        "valid": bool(
            duration_match
            and resolution_match
            and video_path.stat().st_size > 0
            and decoder_exit_code == 0
        ),
    }


def click_and_wait(page: Any, locator: Any) -> None:
    with page.expect_navigation(wait_until="networkidle"):
        locator.click()


def show_slate(page: Any, phase: str, actor: str, action: str) -> None:
    page.set_content(
        f"""<!doctype html><html><head><meta charset='utf-8'><style>
        body{{margin:0;background:#102c3c;color:white;font-family:system-ui;display:grid;
        place-items:center;height:100vh}}main{{max-width:1200px;text-align:center;padding:80px}}
        .phase{{color:#65d6c5;font-size:30px;text-transform:uppercase;letter-spacing:.12em}}
        h1{{font-size:66px;margin:28px 0}}p{{font-size:30px;color:#d9e7ed}}
        .boundary{{font-size:21px;color:#ffd477;margin-top:55px}}
        </style></head><body><main><div class='phase'>{phase}</div><h1>{action}</h1>
        <p>Actor: {actor}</p><p class='boundary'>Synthetic identities and local research data only</p>
        </main></body></html>"""
    )
    page.wait_for_timeout(900)


def login(page: Any, base_url: str, principal: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.get_by_role("heading", name="Research Demo Login").wait_for()
    page.locator("select[name='principal']").select_option(principal)
    click_and_wait(page, page.get_by_role("button", name="Sign In to Demo Session"))
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.get_by_text(f"Logged in as {principal}").wait_for()


def get_json(context: Any, url: str, expected_status: int = 200) -> Any:
    response = context.request.get(url)
    if response.status != expected_status:
        raise AssertionError(f"GET {url} returned {response.status}, expected {expected_status}")
    return response.json()


def table_records(page: Any, index: int) -> list[dict[str, str]]:
    table = page.locator("table").nth(index)
    return table.evaluate(
        """table => {
          const headers = [...table.querySelectorAll('thead th')].map(x => x.innerText.trim());
          return [...table.querySelectorAll('tbody tr')].map(row => Object.fromEntries(
            [...row.querySelectorAll('td')].map((cell, i) => [headers[i] || `column_${i}`, cell.innerText.trim()])
          ));
        }"""
    )


def profile_from_page(page: Any, base_url: str, sid: str) -> dict[str, Any]:
    page.goto(f"{base_url}/students?id={sid}", wait_until="networkidle")
    page.get_by_role("heading", name=f"{sid} · synthetic learning history").wait_for()
    tables = page.locator("table")
    if tables.count() < 2:
        raise AssertionError(f"profile for {sid} did not render concept and history tables")
    return {
        "student_id": sid,
        "captured_at_utc": utc_now(),
        "capture_method": "browser_rendered_tables",
        "concepts": table_records(page, 0),
        "attempt_history": table_records(page, 1),
    }


def screenshot(page: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)


def save_api_json(context: Any, url: str, path: Path) -> Any:
    payload = get_json(context, url)
    write_json(path, payload)
    return payload


def make_flow_html(lineage: dict[str, Any], path: Path) -> Path:
    nodes = lineage.get("nodes", [])
    cards = []
    for node in nodes:
        fixture = node.get("source_type") == "synthetic_fixture"
        css_class = "fixture" if fixture else "actual"
        cards.append(
            "<article class='"
            + css_class
            + "'><small>"
            + str(node.get("timestamp_utc", ""))
            + "</small><h2>"
            + str(node.get("phase", ""))
            + "</h2><p>"
            + str(node.get("event_type", ""))
            + "</p><code>"
            + str(node.get("entity_id", ""))
            + "</code><b>"
            + str(node.get("source_type", ""))
            + "</b></article>"
        )
    document = """<!doctype html><html><head><meta charset='utf-8'><style>
    body{font-family:system-ui;background:#eff5f8;color:#153245;margin:0;padding:30px}
    h1{text-align:center;font-size:44px}.note{text-align:center;font-size:20px;margin-bottom:30px}
    main{display:flex;gap:18px;align-items:stretch;overflow-x:auto;padding:20px}
    article{min-width:275px;background:white;border:3px solid #16786f;border-radius:12px;padding:18px;
    box-shadow:0 4px 12px #16384b22;position:relative}article:not(:last-child):after{content:'→';
    position:absolute;right:-22px;top:42%;font-size:31px;color:#2b627e;z-index:2}.fixture{border-color:#b67b00;
    background:#fff8dd}small,code,b{display:block;margin-top:10px}b{color:#765000}
    </style></head><body><h1>SIIP Executed Data Lineage</h1>
    <p class='note'>Every card is backed by a browser assertion and a persisted output artifact.</p><main>"""
    path.write_text(document + "".join(cards) + "</main></body></html>\n", encoding="utf-8")
    return path


def render_observability(repository: Any, output_dir: Path) -> dict[str, Path]:
    generated = repository.render_all()
    architecture = output_dir / "architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    lineage_target = architecture / "data_lineage.json"
    mermaid_target = architecture / "data_flow.mmd"
    shutil.copy2(generated["lineage"], lineage_target)
    shutil.copy2(generated["mermaid"], mermaid_target)

    events = repository.list_events()
    csv_path = output_dir / "timeline/event_timeline.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(events[0].to_dict()) if events else [])
        if events:
            writer.writeheader()
            writer.writerows(event.to_dict() for event in events)
    return {
        "event_log": generated["event_log"],
        "timeline": generated["timeline"],
        "lineage": lineage_target,
        "mermaid": mermaid_target,
        "csv": csv_path,
    }


def log_event(repository: Any, output_dir: Path, **kwargs: str) -> None:
    path = Path(kwargs["artifact_path"])
    if path.is_absolute():
        kwargs["artifact_path"] = artifact_rel(output_dir, path)
    repository.record_event(**kwargs)


def package_videos(
    ffmpeg: Path | None,
    raw_videos: dict[str, Path],
    actions: list[ActionMarker],
    output_dir: Path,
) -> dict[str, Any]:
    videos_dir = output_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "encoder": None,
        "raw_recordings": {},
        "professor_mp4": None,
        "uncut_mp4": None,
        "limitations": [],
    }
    for actor, source in raw_videos.items():
        target = videos_dir / f"SIIP_Uncut_End_to_End_Verification.{actor}.webm"
        shutil.copy2(source, target)
        result["raw_recordings"][actor] = str(target.resolve())
    if ffmpeg is None:
        result["limitations"].append(
            "No FFmpeg executable was found; original Playwright WebM recordings were preserved "
            "but could not be independently decoded and probed."
        )
        return result

    capabilities = ffmpeg_capabilities(ffmpeg)
    result["encoder"] = capabilities
    result["raw_probes"] = {
        actor: probe_video(ffmpeg, Path(path))
        for actor, path in result["raw_recordings"].items()
    }
    required = (
        capabilities["has_concat_filter"]
        and capabilities["has_trim_filter"]
        and capabilities["has_setpts_filter"]
        and capabilities["has_mp4_muxer"]
        and (capabilities["has_h264_encoder"] or capabilities["has_vp9_encoder"])
    )
    if not required:
        result["limitations"].append(
            "The discovered encoder cannot both trim/concatenate and mux MP4. "
            "Playwright WebM evidence is preserved and no MP4 success is claimed."
        )
        return result

    all_segments = [a for a in actions if a.duration_seconds > 0.05]
    professor_segments = [a for a in all_segments if a.status == "completed"]
    if not professor_segments:
        result["limitations"].append("No completed video action segments were available.")
        return result
    encoder = "libx264" if "libx264" in subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout else "libvpx-vp9"
    def compile_segments(target: Path, segments: list[ActionMarker]) -> tuple[int, str]:
        inputs: list[str] = []
        filters: list[str] = []
        for index, action in enumerate(segments):
            inputs.extend(["-i", str(raw_videos[action.source_video])])
            filters.append(
                f"[{index}:v]trim=start={action.start_seconds:.3f}:end={action.end_seconds:.3f},"
                f"setpts=PTS-STARTPTS[v{index}]"
            )
        filters.append(
            "".join(f"[v{index}]" for index in range(len(segments)))
            + f"concat=n={len(segments)}:v=1:a=0[outv]"
        )
        command = [
            str(ffmpeg),
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            encoder,
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
        conversion = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=1800
        )
        return conversion.returncode, conversion.stderr[-1000:]

    outputs = (
        ("professor", videos_dir / "SIIP_Complete_Prototype_Demo.mp4", professor_segments),
        ("uncut", videos_dir / "SIIP_Uncut_End_to_End_Verification.mp4", all_segments),
    )
    for label, target, segments in outputs:
        exit_code, stderr = compile_segments(target, segments)
        result[f"{label}_conversion_exit_code"] = exit_code
        if exit_code != 0 or not target.is_file():
            target.unlink(missing_ok=True)
            result["limitations"].append(
                f"{label.title()} MP4 conversion failed; original WebMs remain authoritative. "
                + stderr
            )
            continue
        probe = probe_video(ffmpeg, target)
        result[f"{label}_probe"] = probe
        if not probe["valid"]:
            target.unlink(missing_ok=True)
            result["limitations"].append(f"The generated {label} MP4 failed validation.")
            continue
        result[f"{label}_mp4"] = str(target.resolve())
    return result


def write_video_chapters(actions: list[ActionMarker], output_dir: Path) -> Path:
    path = output_dir / "timeline/video_chapters.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    elapsed = 0.0
    lines = ["# Derived after browser contexts closed from measured action boundaries."]
    for action in actions:
        if action.status != "completed" or action.duration_seconds <= 0.05:
            continue
        lines.append(
            f"{format_timecode(elapsed)} {action.phase} — {action.actor} "
            f"(source {action.start_seconds:.3f}–{action.end_seconds:.3f}s)"
        )
        elapsed += action.duration_seconds
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        output_dir / "timeline/video_action_markers.json",
        [asdict(action) | {"duration_seconds": action.duration_seconds} for action in actions],
    )
    return path


def write_demo_readme(output_dir: Path, manifest: dict[str, Any]) -> None:
    packaging = manifest.get("video_packaging", {})
    provider = manifest.get("feedback_provider", "not observed")
    mp4 = packaging.get("professor_mp4") or "NOT PRODUCED"
    uncut = packaging.get("uncut_mp4") or "NOT PRODUCED; see preserved actor WebMs"
    limitations = packaging.get("limitations", []) + manifest.get("limitations", [])
    text = f"""# SIIP professor demonstration evidence

Run ID: `{manifest['run_id']}`  
Correlation ID: `{manifest['correlation_id']}`  
Started UTC: `{manifest['started_at_utc']}`  
Completed UTC: `{manifest.get('completed_at_utc', 'not completed')}`  
Result: `{manifest['status']}`

## Videos

- Professor MP4: `{mp4}`
- Uncut MP4: `{uncut}`
- Original Playwright recordings: `{packaging.get('raw_recordings', {})}`

Video chapters are derived from measured recording-relative markers after the
instructor and student contexts close; they are not storyboard estimates.

## Scientific boundaries

- The candidate graph is the dashboard's explicitly labelled synthetic fixture,
  not an actual InstructKG extraction.
- Assignment publication is local SIIP demo publication, not native PrairieLearn
  instructor publication.
- Deterministic SQL grading is independent of feedback generation.
- Observed feedback provider/provenance: `{provider}`.
- All principals and course materials are synthetic.

## Limitations

"""
    text += "\n".join(f"- {item}" for item in limitations) or "- None recorded by the runner."
    (output_dir / "README_DEMO.md").write_text(text + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_args(args)
    try:
        from playwright.sync_api import expect, sync_playwright
        from siip.demo_observability import DemoObservabilityRepository
        from siip.demo_student import DemoStudentJourney
        from siip.em_repository import EMRepository
        from siip.jobs import FeedbackJobRepository
        from siip.store import SubmissionRepository
    except ImportError as exc:
        raise RuntimeError(
            "Playwright and the SIIP package are required; install development dependencies first"
        ) from exc

    suffix = f"{timestamp_slug().lower()}-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{suffix}"
    correlation_id = f"siip-demo-{suffix}"
    source_document_id = f"lesson-sql-joins-{suffix}"
    assignment_id = f"assignment-left-join-{suffix}"
    output_dir = args.output_dir
    if (output_dir / "run_manifest.json").exists() or (
        output_dir / "timeline/system_event_log.jsonl"
    ).exists():
        output_dir = output_dir / run_id
    for relative in (
        "videos/raw",
        "screenshots",
        "outputs/lesson",
        "outputs/knowledge_graph",
        "outputs/assignments",
        "outputs/submissions",
        "outputs/grading",
        "outputs/feedback",
        "outputs/student_profiles",
        "outputs/em",
        "outputs/analytics",
        "outputs/projects",
        "timeline",
        "architecture",
    ):
        (output_dir / relative).mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "correlation_id": correlation_id,
        "started_at_utc": utc_now(),
        "status": "running",
        "base_url": args.base_url,
        "lesson_path": str(args.lesson_path),
        "viewport": VIEWPORT,
        "records": {},
        "limitations": [],
    }
    submission_db = Path(
        os.environ.get("SIIP_DB_PATH") or ROOT / "artifacts/synthetic.sqlite3"
    ).resolve()
    jobs_db = Path(
        os.environ.get("SIIP_FEEDBACK_JOBS_DB")
        or ROOT / "artifacts/jobs/feedback_jobs.sqlite3"
    ).resolve()
    submission_store = SubmissionRepository(submission_db)
    fixture_journey = DemoStudentJourney(
        submission_store=submission_store,
        feedback_jobs=FeedbackJobRepository(jobs_db),
        em_store=EMRepository(submission_db),
    )
    fixture_receipt = fixture_journey.seed_fixture_histories()
    fixture_attempt_ids = set(fixture_receipt["attempt_ids"])
    persisted_fixture_attempts = [
        record for record in submission_store.records() if record["attempt_id"] in fixture_attempt_ids
    ]
    if len(persisted_fixture_attempts) != len(fixture_attempt_ids):
        raise AssertionError("not all labelled fixture histories persisted")
    fixture_path = output_dir / "outputs/student_profiles/00_fixture_history_preparation.json"
    write_json(
        fixture_path,
        {
            **fixture_receipt,
            "prepared_at_utc": utc_now(),
            "submission_database": str(submission_db),
            "records": persisted_fixture_attempts,
        },
    )
    manifest["fixture_history"] = {
        "classification": fixture_receipt["classification"],
        "artifact": artifact_rel(output_dir, fixture_path),
        "attempt_ids": sorted(fixture_attempt_ids),
    }
    write_json(output_dir / "run_manifest.json", manifest)
    event_repo = DemoObservabilityRepository(output_dir / "timeline")
    clock = RecorderClock()
    pages: dict[str, Any] = {}
    contexts: dict[str, Any] = {}
    video_handles: dict[str, Any] = {}
    raw_video_paths: dict[str, Path] = {}
    run_error: Exception | None = None

    def event(
        *,
        actor_type: str,
        actor_id: str,
        phase: str,
        event_type: str,
        entity_id: str,
        artifact: Path,
        source_type: str = "actual_execution",
        status: str = "completed",
    ) -> None:
        log_event(
            event_repo,
            output_dir,
            actor_type=actor_type,
            actor_id=actor_id,
            phase=phase,
            event_type=event_type,
            entity_id=safe_entity(entity_id),
            correlation_id=correlation_id,
            status=status,
            artifact_path=artifact,
            source_type=source_type,
        )

    def capture(page: Any, path: Path) -> None:
        screenshot(page, path)
        if args.dwell_seconds:
            page.wait_for_timeout(args.dwell_seconds * 1000)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        try:
            for actor in ("instructor", "student"):
                context = browser.new_context(
                    viewport=VIEWPORT,
                    record_video_dir=str(output_dir / "videos/raw"),
                    record_video_size=VIEWPORT,
                )
                page = context.new_page()
                contexts[actor] = context
                pages[actor] = page
                video_handles[actor] = page.video
                clock.start_video(actor)

            instructor = pages["instructor"]
            student = pages["student"]
            login(instructor, args.base_url, "instructor_alawini")

            with clock.action("01 Instructor upload and provenance", "instructor"):
                show_slate(instructor, "Phase 1", "Synthetic instructor", "Upload teaching material")
                instructor.goto(f"{args.base_url}/authoring", wait_until="networkidle")
                instructor.locator("input[name='source_document_id']").fill(source_document_id)
                instructor.get_by_test_id("lesson-file").set_input_files(str(args.lesson_path))
                click_and_wait(instructor, instructor.get_by_test_id("upload-lesson"))
                expect(instructor.get_by_test_id("authoring-notice")).to_contain_text(
                    source_document_id
                )
                lessons_path = output_dir / "outputs/lesson/01_uploaded_lesson.json"
                lessons = save_api_json(
                    contexts["instructor"], f"{args.base_url}/api/demo/lessons", lessons_path
                )
                lesson = next(
                    (item for item in lessons if item["source_document_id"] == source_document_id),
                    None,
                )
                if not lesson:
                    raise AssertionError("uploaded lesson was not returned by the lesson registry")
                write_json(lessons_path, lesson)
                row = instructor.locator("tr", has_text=source_document_id)
                click_and_wait(instructor, row.get_by_role("link", name="Open stored material"))
                expect(instructor.get_by_test_id("stored-lesson")).to_contain_text(
                    source_document_id
                )
                capture(instructor, output_dir / "screenshots/01_uploaded_lesson.png")
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="source",
                    event_type="instructor_uploaded_lesson",
                    entity_id=source_document_id,
                    artifact=lessons_path,
                )
                manifest["records"]["source_document_id"] = source_document_id

            with clock.action("02 Fixture knowledge graph review", "instructor"):
                show_slate(
                    instructor,
                    "Phase 2",
                    "Synthetic instructor",
                    "Generate and review fixture knowledge graph",
                )
                instructor.goto(f"{args.base_url}/authoring", wait_until="networkidle")
                row = instructor.locator("tr", has_text=source_document_id)
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="knowledge_graph",
                    event_type="kg_extraction_requested",
                    entity_id=source_document_id,
                    artifact=output_dir / "outputs/lesson/01_uploaded_lesson.json",
                    source_type="synthetic_fixture",
                    status="started",
                )
                click_and_wait(instructor, row.get_by_role("button", name="Generate Knowledge Graph"))
                expect(instructor.get_by_test_id("demo-kg-boundary")).to_contain_text(
                    "upstream InstructKG extractor is unavailable"
                )
                if instructor.get_by_test_id("kg-node").count() < 2:
                    raise AssertionError("candidate graph did not render at least two nodes")
                expect(instructor.get_by_test_id("kg-edges")).to_be_visible()
                graph_id = parse_qs(urlparse(instructor.url).query).get("graph_id", [None])[0]
                if not graph_id:
                    raise AssertionError("generated graph URL did not contain graph_id")
                graph_path = output_dir / "outputs/knowledge_graph/02_extracted_kg.json"
                graph = save_api_json(
                    contexts["instructor"],
                    f"{args.base_url}/api/demo/graphs?graph_id={graph_id}",
                    graph_path,
                )
                if graph.get("source_document_id") != source_document_id or not graph.get("edges"):
                    raise AssertionError("graph provenance or edges did not match the uploaded lesson")
                capture(instructor, output_dir / "screenshots/02_graph_before_review.png")
                event(
                    actor_type="system",
                    actor_id="siip-fixture-kg",
                    phase="knowledge_graph",
                    event_type="kg_extraction_completed",
                    entity_id=source_document_id,
                    artifact=graph_path,
                    source_type="synthetic_fixture",
                )

                first_edge_id = graph["edges"][0]["edge_id"]
                edge_row = instructor.locator("tr", has=instructor.locator(
                    f"input[name='edge_id'][value='{first_edge_id}']"
                ))
                edge_row.get_by_label("Review notes").fill(
                    f"Approved during recorded synthetic workflow {run_id}"
                )
                click_and_wait(instructor, edge_row.get_by_role("button", name="Approve"))
                reviewed = get_json(
                    contexts["instructor"],
                    f"{args.base_url}/api/demo/graphs?graph_id={graph_id}",
                )
                reviewed_edge = next(edge for edge in reviewed["edges"] if edge["edge_id"] == first_edge_id)
                if reviewed_edge["review_state"] != "APPROVED":
                    raise AssertionError("edge approval did not persist")
                capture(instructor, output_dir / "screenshots/02_graph_after_review.png")
                click_and_wait(instructor, instructor.get_by_test_id("save-graph"))
                expect(instructor.get_by_test_id("graph-notice")).to_contain_text(
                    "Saved reviewed graph version"
                )
                approval_path = output_dir / "outputs/knowledge_graph/02_instructor_approval.json"
                write_json(
                    approval_path,
                    {
                        "graph_id": graph_id,
                        "edge": reviewed_edge,
                        "saved_notice": instructor.get_by_test_id("graph-notice").inner_text(),
                        "captured_at_utc": utc_now(),
                    },
                )
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="graph_review",
                    event_type="kg_reviewed",
                    entity_id=graph_id,
                    artifact=approval_path,
                    source_type="synthetic_fixture",
                )
                manifest["records"].update({"graph_id": graph_id, "edge_id": first_edge_id})

            with clock.action("03 Local assignment publication", "instructor"):
                show_slate(
                    instructor,
                    "Phase 3",
                    "Synthetic instructor",
                    "Create and publish local SIIP assignment",
                )
                instructor.goto(f"{args.base_url}/assignments", wait_until="networkidle")
                expect(instructor.get_by_test_id("assignment-authoring")).to_contain_text(
                    "LOCAL SIIP"
                )
                instructor.locator("input[name='assignment_id']").fill(assignment_id)
                click_and_wait(instructor, instructor.get_by_test_id("create-assignment"))
                assignment_row = instructor.locator("tr", has_text=assignment_id)
                expect(assignment_row).to_contain_text("DRAFT")
                capture(instructor, output_dir / "screenshots/03_assignment_preview.png")
                click_and_wait(
                    instructor, assignment_row.get_by_role("button", name="Publish assignment")
                )
                assignments_path = output_dir / "outputs/assignments/03_published_assignment.json"
                assignments = save_api_json(
                    contexts["instructor"],
                    f"{args.base_url}/api/demo/assignments",
                    assignments_path,
                )
                assignment = next(
                    (item for item in assignments if item["assignment_id"] == assignment_id), None
                )
                if not assignment or assignment["publication_status"] != "PUBLISHED_LOCAL_DEMO":
                    raise AssertionError("local assignment publication did not persist")
                write_json(assignments_path, assignment)
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="assignment",
                    event_type="assignment_published",
                    entity_id=assignment_id,
                    artifact=assignments_path,
                )
                manifest["records"]["assignment_id"] = assignment_id

            login(student, args.base_url, "S001")
            with clock.action("04 Student assignment and deterministic grade", "student"):
                show_slate(
                    student,
                    "Phase 4",
                    "Synthetic learner S001",
                    "Open assignment and submit INNER JOIN misconception",
                )
                student.goto(f"{args.base_url}/assignments", wait_until="networkidle")
                student_row = student.locator("tr", has_text=assignment_id)
                expect(student_row).to_contain_text("PUBLISHED_LOCAL_DEMO")
                capture(student, output_dir / "screenshots/03_student_assignment_visible.png")
                event(
                    actor_type="student",
                    actor_id="S001",
                    phase="assignment",
                    event_type="assignment_opened",
                    entity_id=assignment_id,
                    artifact=output_dir / "outputs/assignments/03_published_assignment.json",
                )
                click_and_wait(
                    student, student_row.get_by_role("link", name="Open student activity")
                )
                expect(student.get_by_role("heading", name="PrairieLearn Interactive SQL Practice")).to_be_visible()
                expect(student.locator("code", has_text="sql_join_04").first).to_be_visible()
                student.locator("textarea#sql").fill(INCORRECT_SQL)
                capture(student, output_dir / "screenshots/04_student_submission.png")
                click_and_wait(student, student.locator("button#submit-query"))
                expect(student.get_by_role("heading", name="PrairieLearn Grading Receipt")).to_be_visible()
                receipt = student.locator("h3", has_text="PrairieLearn Grading Receipt").locator("..")
                expect(receipt).to_contain_text("Score: 0%")
                expect(student.locator("#ai-feedback-link")).to_be_visible()
                capture(student, output_dir / "screenshots/04_grading_result.png")
                feedback_href = student.locator("#ai-feedback-link").get_attribute("href")
                if not feedback_href:
                    raise AssertionError("grading receipt did not provide an async feedback URL")
                feedback_href = urljoin(args.base_url + "/", feedback_href)
                job_id = parse_qs(urlparse(feedback_href).query).get("job_id", [None])[0]
                if not job_id:
                    raise AssertionError("feedback URL did not contain a job identifier")
                feedback_job = get_json(contexts["student"], feedback_href.replace("/feedback?", "/api/feedback?"))
                if feedback_job.get("submitted_sql") != INCORRECT_SQL:
                    raise AssertionError("persisted feedback job did not retain this browser submission")
                submission_path = output_dir / "outputs/submissions/04_student_submission.json"
                grading_path = output_dir / "outputs/grading/04_grading_result.json"
                write_json(
                    submission_path,
                    {
                        "job_id": job_id,
                        "student_id": "S001",
                        "question_id": feedback_job["question_id"],
                        "submitted_sql": feedback_job["submitted_sql"],
                        "capture_method": "authenticated_feedback_job_and_browser_session",
                    },
                )
                write_json(grading_path, feedback_job["grading"])
                event(
                    actor_type="student",
                    actor_id="S001",
                    phase="submission",
                    event_type="sql_submitted",
                    entity_id=job_id,
                    artifact=submission_path,
                )
                event(
                    actor_type="system",
                    actor_id="siip-deterministic-grader",
                    phase="grade",
                    event_type="grading_completed",
                    entity_id=job_id,
                    artifact=grading_path,
                )
                event(
                    actor_type="system",
                    actor_id="siip-concept-mapper",
                    phase="diagnosis",
                    event_type="concept_diagnosis_completed",
                    entity_id=job_id,
                    artifact=grading_path,
                )
                feedback_job_path = output_dir / "outputs/feedback/05_feedback_job.json"
                write_json(feedback_job_path, feedback_job)
                event(
                    actor_type="system",
                    actor_id="siip-feedback-queue",
                    phase="feedback",
                    event_type="feedback_job_queued",
                    entity_id=job_id,
                    artifact=feedback_job_path,
                    status="started",
                )
                manifest["records"]["job_id"] = job_id

            with clock.action("05 Asynchronous grounded feedback", "student"):
                show_slate(
                    student,
                    "Phase 5",
                    "Synthetic learner S001",
                    "Inspect asynchronous grounded feedback",
                )
                deadline = time.monotonic() + args.feedback_timeout
                api_feedback_url = feedback_href.replace("/feedback?", "/api/feedback?")
                feedback_result = get_json(contexts["student"], api_feedback_url)
                while feedback_result.get("status") in {"pending", "processing"}:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "feedback remained pending; verify scripts/feedback_worker.py is running "
                            "against the same SIIP_FEEDBACK_JOBS_DB"
                        )
                    student.wait_for_timeout(1000)
                    feedback_result = get_json(contexts["student"], api_feedback_url)
                if feedback_result.get("status") != "completed":
                    raise AssertionError(f"feedback completed with {feedback_result.get('status')!r}")
                student.goto(feedback_href, wait_until="networkidle")
                expect(student.get_by_role("heading", name="Personalized AI feedback")).to_be_visible()
                expect(student.get_by_text("COMPLETED", exact=True)).to_be_visible()
                expect(student.get_by_text("Deterministic grading:")).to_be_visible()
                capture(student, output_dir / "screenshots/05_feedback_visible.png")
                attempt_field = student.locator("input[name='attempt_id']")
                if attempt_field.count() == 0:
                    raise AssertionError(
                        "the feedback page did not expose an attempt-scoped EM form; the current "
                        "dashboard permits only one reflection per student/question"
                    )
                attempt_id = attempt_field.get_attribute("value")
                if not attempt_id:
                    raise AssertionError("feedback page did not expose the stable attempt identifier")
                submission_path = output_dir / "outputs/submissions/04_student_submission.json"
                submission_record = json.loads(submission_path.read_text(encoding="utf-8"))
                submission_record["attempt_id"] = attempt_id
                write_json(submission_path, submission_record)
                manifest["records"]["attempt_id"] = attempt_id
                feedback_result_path = output_dir / "outputs/feedback/05_feedback_result.json"
                provenance_path = output_dir / "outputs/feedback/05_feedback_provenance.json"
                write_json(feedback_result_path, feedback_result)
                write_json(provenance_path, feedback_result.get("provenance") or {})
                provider = (feedback_result.get("provenance") or {}).get("model_identifier") or (
                    feedback_result.get("feedback") or {}
                ).get("model_identifier")
                manifest["feedback_provider"] = provider or "not reported"
                event(
                    actor_type="system",
                    actor_id="siip-feedback-worker",
                    phase="feedback",
                    event_type="feedback_generation_completed",
                    entity_id=job_id,
                    artifact=feedback_result_path,
                )
                event(
                    actor_type="student",
                    actor_id="S001",
                    phase="feedback",
                    event_type="feedback_viewed",
                    entity_id=job_id,
                    artifact=output_dir / "screenshots/05_feedback_visible.png",
                )

            with clock.action("06 Profiles and recommendations", "student"):
                show_slate(
                    student,
                    "Phase 6",
                    "Synthetic learner S001",
                    "Inspect history-derived recommendation",
                )
                profile_a = profile_from_page(student, args.base_url, "S001")
                if not any(row.get("Question") == "sql_join_04" for row in profile_a["attempt_history"]):
                    raise AssertionError("S001 profile did not include the completed browser attempt")
                rec_a = get_json(
                    contexts["student"], f"{args.base_url}/api/recommendation?student_id=S001"
                )
                profile_a["recommendation"] = rec_a
                capture(student, output_dir / "screenshots/06_student_profiles.png")
                profile_a_path = output_dir / "outputs/student_profiles/06_student_a_profile.json"
                write_json(profile_a_path, profile_a)
                event(
                    actor_type="system",
                    actor_id="siip-profile-service",
                    phase="history",
                    event_type="profile_updated",
                    entity_id=attempt_id,
                    artifact=profile_a_path,
                )

            with clock.action("06 S002 contrasting fixture history", "instructor"):
                show_slate(
                    instructor,
                    "Phase 6 comparison",
                    "Synthetic instructor",
                    "Compare S002 history-derived recommendation",
                )
                # Instructor authorization is used for the contrasting synthetic fixture history.
                profile_b = profile_from_page(instructor, args.base_url, "S002")
                rec_b = get_json(
                    contexts["instructor"], f"{args.base_url}/api/recommendation?student_id=S002"
                )
                profile_b["recommendation"] = rec_b
                capture(instructor, output_dir / "screenshots/06_student_b_profile.png")
                profile_b_path = output_dir / "outputs/student_profiles/06_student_b_profile.json"
                comparison_path = (
                    output_dir / "outputs/student_profiles/06_recommendation_comparison.json"
                )
                write_json(profile_b_path, profile_b)
                write_json(
                    comparison_path,
                    {
                        "S001": rec_a,
                        "S002": rec_b,
                        "recommendations_differ": (
                            rec_a.get("recommended_question_id")
                            != rec_b.get("recommended_question_id")
                        ),
                        "histories_are_synthetic_fixtures": True,
                        "captured_at_utc": utc_now(),
                    },
                )
                if rec_a.get("recommended_question_id") == rec_b.get(
                    "recommended_question_id"
                ):
                    raise AssertionError(
                        "labelled fixture histories did not produce contrasting actual recommender "
                        "question IDs"
                    )

            with clock.action("07 Optional EM reflection", "student"):
                show_slate(
                    student,
                    "Phase 7",
                    "Synthetic learner S001",
                    "Submit optional Entrepreneurial Mindset reflection",
                )
                student.goto(feedback_href, wait_until="networkidle")
                expect(student.get_by_text("Entrepreneurial Mindset (EM) Reflection").first).to_be_visible()
                reflection_box = student.locator("textarea#reflection_text")
                if reflection_box.count() == 0:
                    raise AssertionError(
                        "an earlier reflection already exists for this question; a new unique attempt "
                        "is required for repeatable EM recording"
                    )
                reflection_box.fill(REFLECTION)
                click_and_wait(student, student.get_by_role("button", name="Submit Reflection"))
                expect(student.get_by_text("Status: PROPOSED", exact=True)).to_be_visible()
                expect(student.get_by_text(REFLECTION, exact=True)).to_be_visible()
                capture(student, output_dir / "screenshots/07_em_student_view.png")
                em_summary = get_json(
                    contexts["student"], f"{args.base_url}/api/em/summary?student_id=S001"
                )
                evidence = next(
                    (
                        record
                        for record in em_summary.get("records", [])
                        if record.get("attempt_id") == attempt_id
                        or record.get("evidence_excerpt") == REFLECTION
                    ),
                    None,
                )
                if not evidence or evidence.get("review_status") != "PROPOSED":
                    raise AssertionError("new EM evidence was not persisted in PROPOSED state")
                reflection_path = output_dir / "outputs/em/07_em_reflection.json"
                evidence_path = output_dir / "outputs/em/07_em_evidence.json"
                write_json(
                    reflection_path,
                    {
                        "student_id": "S001",
                        "attempt_id": attempt_id,
                        "question_id": "sql_join_04",
                        "response_text": REFLECTION,
                        "captured_at_utc": utc_now(),
                    },
                )
                write_json(evidence_path, evidence)
                evidence_id = evidence["evidence_id"]
                event(
                    actor_type="student",
                    actor_id="S001",
                    phase="em",
                    event_type="em_reflection_submitted",
                    entity_id=evidence_id,
                    artifact=evidence_path,
                )
                manifest["records"]["evidence_id"] = evidence_id

            with clock.action("08 Instructor analytics and EM review", "instructor"):
                show_slate(
                    instructor,
                    "Phase 8",
                    "Synthetic instructor",
                    "Review analytics and provisional EM evidence",
                )
                instructor.goto(f"{args.base_url}/", wait_until="networkidle")
                capture(instructor, output_dir / "screenshots/08_instructor_dashboard.png")
                cohort_path = output_dir / "outputs/analytics/08_cohort_summary.json"
                concept_path = output_dir / "outputs/analytics/08_concept_gap_analytics.json"
                cohort = save_api_json(
                    contexts["instructor"], f"{args.base_url}/api/cohort-analytics", cohort_path
                )
                analytics = save_api_json(
                    contexts["instructor"], f"{args.base_url}/api/analytics", concept_path
                )
                if cohort.get("submission_count", 0) < 1 or analytics.get("attempt_count", 0) < 1:
                    raise AssertionError("instructor analytics did not include persisted submissions")
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="analytics",
                    event_type="instructor_analytics_viewed",
                    entity_id=assignment_id,
                    artifact=cohort_path,
                )
                instructor.goto(f"{args.base_url}/em-review", wait_until="networkidle")
                evidence_row = instructor.locator("tr", has_text=evidence_id)
                if evidence_row.count() == 0:
                    evidence_row = instructor.locator("tr", has_text=REFLECTION[:60])
                expect(evidence_row).to_contain_text("PROPOSED")
                evidence_row.locator("input[name='instructor_notes']").fill(
                    f"Accepted during recorded synthetic review {run_id}"
                )
                click_and_wait(
                    instructor, evidence_row.get_by_role("button", name="Accept", exact=True)
                )
                updated_em = get_json(
                    contexts["instructor"], f"{args.base_url}/api/em/summary?student_id=S001"
                )
                updated_evidence = next(
                    record for record in updated_em["records"] if record["evidence_id"] == evidence_id
                )
                if updated_evidence["review_status"] != "ACCEPTED":
                    raise AssertionError("instructor EM review did not persist")
                review_path = output_dir / "outputs/em/08_em_review_decision.json"
                write_json(review_path, updated_evidence)
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="em",
                    event_type="em_evidence_reviewed",
                    entity_id=evidence_id,
                    artifact=review_path,
                )

            with clock.action("09 Personalized project and approval", "student"):
                show_slate(
                    student,
                    "Phase 9",
                    "Synthetic learner S001",
                    "Generate profile-informed healthcare SQL project",
                )
                student.goto(f"{args.base_url}/projects", wait_until="networkidle")
                click_and_wait(student, student.get_by_role("button", name="Generate My Project"))
                project_id = parse_qs(urlparse(student.url).query).get("id", [None])[0]
                if not project_id:
                    raise AssertionError("project generation did not redirect to a project record")
                project_student = get_json(
                    contexts["student"], f"{args.base_url}/api/projects?id={project_id}"
                )
                if project_student.get("student_id") != "S001":
                    raise AssertionError("generated project was not bound to S001")
                if any("reference_sql" in item for item in project_student.get("milestones", [])):
                    raise AssertionError("learner project JSON exposed reference SQL")
                project_path = output_dir / "outputs/projects/09_personalized_project.json"
                write_json(project_path, project_student)
                event(
                    actor_type="system",
                    actor_id="siip-project-generator",
                    phase="project",
                    event_type="personalized_project_generated",
                    entity_id=project_id,
                    artifact=project_path,
                )
                manifest["records"]["project_id"] = project_id

            with clock.action("09 Instructor project review", "instructor"):
                instructor.goto(f"{args.base_url}/projects?id={project_id}", wait_until="networkidle")
                expect(instructor.get_by_role("heading", name="Instructor Review & Approval")).to_be_visible()
                instructor.locator("input[name='notes']").fill(
                    f"Approved for the synthetic professor demonstration {run_id}"
                )
                click_and_wait(
                    instructor, instructor.get_by_role("button", name="Approve Project")
                )
                expect(instructor.get_by_text("Status: APPROVED", exact=True)).to_be_visible()
                project_review = get_json(
                    contexts["instructor"], f"{args.base_url}/api/projects?id={project_id}"
                )
                if project_review.get("instructor_approval_status") != "APPROVED":
                    raise AssertionError("project approval did not persist")
                project_review_path = (
                    output_dir / "outputs/projects/09_project_instructor_review.json"
                )
                write_json(project_review_path, project_review)
                event(
                    actor_type="instructor",
                    actor_id="instructor_alawini",
                    phase="project",
                    event_type="project_approved",
                    entity_id=project_id,
                    artifact=project_review_path,
                )

            with clock.action("09 Approved learner project", "student"):
                student.goto(f"{args.base_url}/projects?id={project_id}", wait_until="networkidle")
                expect(student.get_by_text("Status: APPROVED", exact=True)).to_be_visible()
                learner_html = student.content()
                if "Reference SQL Solution" in learner_html or "Approve Project" in learner_html:
                    raise AssertionError("learner project DOM exposed instructor-only material")
                capture(student, output_dir / "screenshots/09_project_student_view.png")

            with clock.action("10 Executed lineage and timeline", "instructor"):
                show_slate(
                    instructor,
                    "Conclusion",
                    "Synthetic instructor",
                    "Inspect executed data lineage and system timeline",
                )
                instructor.goto(f"{args.base_url}/timeline", wait_until="networkidle")
                expect(
                    instructor.get_by_role("heading", name="SIIP System Event Timeline")
                ).to_be_visible()
                capture(instructor, output_dir / "screenshots/10_instructor_timeline.png")
                dashboard_events = get_json(
                    contexts["instructor"], f"{args.base_url}/api/demo/events"
                )
                run_entities = {
                    source_document_id,
                    graph_id,
                    first_edge_id,
                    assignment_id,
                    job_id,
                    attempt_id,
                    evidence_id,
                    project_id,
                    "instructor-dashboard",
                    "S001",
                }
                matching_dashboard_events = [
                    item for item in dashboard_events if item.get("entity_id") in run_entities
                ]
                write_json(
                    output_dir / "timeline/dashboard_system_events.json",
                    {
                        "capture_method": "authenticated_dashboard_api",
                        "record_count": len(matching_dashboard_events),
                        "records": matching_dashboard_events,
                    },
                )

                paths = render_observability(event_repo, output_dir)
                lineage = json.loads(paths["lineage"].read_text(encoding="utf-8"))
                flow_html = make_flow_html(lineage, output_dir / "architecture/data_flow.html")
                instructor.goto(flow_html.resolve().as_uri(), wait_until="load")
                capture(instructor, output_dir / "architecture/data_flow.png")
                instructor.goto(paths["timeline"].resolve().as_uri(), wait_until="load")
                expect(instructor.get_by_role("heading", name="SIIP System Event Timeline")).to_be_visible()
                capture(instructor, output_dir / "screenshots/10_runner_timeline.png")
        except Exception as exc:
            run_error = exc
            manifest["status"] = "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            for actor, page in pages.items():
                try:
                    screenshot(page, output_dir / f"screenshots/FAILED_{actor}.png")
                except Exception:
                    pass
        finally:
            for actor, context in contexts.items():
                try:
                    context.close()
                    raw_video_paths[actor] = Path(video_handles[actor].path()).resolve()
                except Exception as exc:
                    manifest["limitations"].append(
                        f"Could not close/capture {actor} video cleanly: {type(exc).__name__}: {exc}"
                    )
            browser.close()

    # Chapter derivation and packaging intentionally happen after video contexts close.
    write_video_chapters(clock.actions, output_dir)
    render_observability(event_repo, output_dir)
    ffmpeg = discover_ffmpeg(args.ffmpeg)
    manifest["video_packaging"] = package_videos(
        ffmpeg, raw_video_paths, clock.actions, output_dir
    )
    manifest["completed_at_utc"] = utc_now()
    if run_error is None:
        manifest["status"] = "completed"
    write_json(output_dir / "run_manifest.json", manifest)
    write_demo_readme(output_dir, manifest)
    if run_error is not None:
        raise run_error
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = run(args)
    except Exception as exc:
        print(f"recording failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
