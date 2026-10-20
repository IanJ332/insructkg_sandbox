"""Persisted event timelines and data lineage for the local SIIP demonstration.

The repository is deliberately passive: it records only operations reported by
its caller.  It never manufactures phase-completion or success events.  All
state lives below a caller-supplied directory, making it suitable for an
isolated demonstration artifact bundle and for tests.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

ACTOR_TYPES = frozenset({"instructor", "student", "system"})
EVENT_STATUSES = frozenset({"started", "completed", "failed"})
SOURCE_TYPES = frozenset({"actual_execution", "synthetic_fixture"})

# The phase vocabulary is also the ordering used in the lineage view.  KG
# extraction and instructor review are separate because review is an explicit
# scientific boundary in this demonstration.
LINEAGE_PHASES = (
    "source",
    "knowledge_graph",
    "graph_review",
    "assignment",
    "submission",
    "grade",
    "diagnosis",
    "history",
    "feedback",
    "em",
    "analytics",
    "project",
)
PHASES = frozenset(LINEAGE_PHASES)

EVENT_TYPES = frozenset(
    {
        "instructor_uploaded_lesson",
        "kg_extraction_requested",
        "kg_extraction_completed",
        "kg_reviewed",
        "assignment_published",
        "assignment_opened",
        "sql_submitted",
        "grading_completed",
        "concept_diagnosis_completed",
        "profile_updated",
        "feedback_job_queued",
        "feedback_generation_started",
        "feedback_generation_completed",
        "feedback_viewed",
        "em_reflection_submitted",
        "em_evidence_reviewed",
        "instructor_analytics_viewed",
        "personalized_project_generated",
        "project_approved",
    }
)

_EXPECTED_PHASE = {
    "instructor_uploaded_lesson": "source",
    "kg_extraction_requested": "knowledge_graph",
    "kg_extraction_completed": "knowledge_graph",
    "kg_reviewed": "graph_review",
    "assignment_published": "assignment",
    "assignment_opened": "assignment",
    "sql_submitted": "submission",
    "grading_completed": "grade",
    "concept_diagnosis_completed": "diagnosis",
    "profile_updated": "history",
    "feedback_job_queued": "feedback",
    "feedback_generation_started": "feedback",
    "feedback_generation_completed": "feedback",
    "feedback_viewed": "feedback",
    "em_reflection_submitted": "em",
    "em_evidence_reviewed": "em",
    "instructor_analytics_viewed": "analytics",
    "personalized_project_generated": "project",
    "project_approved": "project",
}

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_ARTIFACT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$")
_SCHEMA_FIELDS = (
    "event_id",
    "timestamp_utc",
    "actor_type",
    "actor_id",
    "phase",
    "event_type",
    "entity_id",
    "correlation_id",
    "status",
    "artifact_path",
    "source_type",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field} is not a valid non-empty identifier")
    return value


def _enum(value: str, field: str, choices: frozenset[str]) -> str:
    if value not in choices:
        raise ValueError(f"{field} must be one of {sorted(choices)}")
    return value


def _timestamp(value: str | datetime) -> tuple[str, datetime]:
    if isinstance(value, str):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp_utc must be an ISO-8601 timestamp") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("timestamp_utc must be a string or datetime")
    offset = parsed.utcoffset() if parsed.tzinfo is not None else None
    if offset is None:
        raise ValueError("timestamp_utc must include a UTC offset")
    if offset.total_seconds() != 0:
        raise ValueError("timestamp_utc must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _artifact_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact_path must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix().startswith("/"):
        raise ValueError("artifact_path must stay within the caller's artifact directory")
    return path.as_posix()


@dataclass(frozen=True)
class DemoEvent:
    """One exact-schema, caller-reported demo event."""

    event_id: str
    timestamp_utc: str
    actor_type: str
    actor_id: str
    phase: str
    event_type: str
    entity_id: str
    correlation_id: str
    status: str
    artifact_path: str
    source_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> "DemoEvent":
        if set(record) != set(_SCHEMA_FIELDS):
            raise ValueError(f"event must contain exactly these fields: {list(_SCHEMA_FIELDS)}")
        return _validated_event(**dict(record))


def _validated_event(
    *,
    event_id: str,
    timestamp_utc: str | datetime,
    actor_type: str,
    actor_id: str,
    phase: str,
    event_type: str,
    entity_id: str,
    correlation_id: str,
    status: str,
    artifact_path: str,
    source_type: str,
) -> DemoEvent:
    try:
        parsed_uuid = uuid.UUID(event_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("event_id must be a UUID") from exc
    normalized_timestamp, _ = _timestamp(timestamp_utc)
    phase = _enum(phase, "phase", PHASES)
    event_type = _enum(event_type, "event_type", EVENT_TYPES)
    expected = _EXPECTED_PHASE[event_type]
    if phase != expected:
        raise ValueError(f"event_type {event_type!r} belongs to phase {expected!r}")
    return DemoEvent(
        event_id=str(parsed_uuid),
        timestamp_utc=normalized_timestamp,
        actor_type=_enum(actor_type, "actor_type", ACTOR_TYPES),
        actor_id=_identifier(actor_id, "actor_id"),
        phase=phase,
        event_type=event_type,
        entity_id=_identifier(entity_id, "entity_id"),
        correlation_id=_identifier(correlation_id, "correlation_id"),
        status=_enum(status, "status", EVENT_STATUSES),
        artifact_path=_artifact_path(artifact_path),
        source_type=_enum(source_type, "source_type", SOURCE_TYPES),
    )


class DemoObservabilityRepository:
    """Append-only JSONL repository and renderer for one demo artifact directory."""

    def __init__(
        self,
        artifact_dir: Path | str,
        *,
        clock: Callable[[], str | datetime] = _utc_now,
    ) -> None:
        self.artifact_dir = Path(artifact_dir).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.event_log_path = self.artifact_dir / "system_event_log.jsonl"
        self.lineage_path = self.artifact_dir / "data_lineage.json"
        self.mermaid_path = self.artifact_dir / "data_flow.mmd"
        self.timeline_path = self.artifact_dir / "instructor_timeline.html"
        self._clock = clock
        self._lock = threading.RLock()
        self.event_log_path.touch(exist_ok=True)
        self.list_events()  # Fail closed immediately if an existing log is invalid.

    def record_event(
        self,
        *,
        actor_type: str,
        actor_id: str,
        phase: str,
        event_type: str,
        entity_id: str,
        correlation_id: str,
        status: str,
        artifact_path: str,
        source_type: str,
        timestamp_utc: str | datetime | None = None,
        event_id: str | None = None,
    ) -> DemoEvent:
        """Append exactly one caller-reported event; no related event is inferred."""

        event = _validated_event(
            event_id=event_id or str(uuid.uuid4()),
            timestamp_utc=self._clock() if timestamp_utc is None else timestamp_utc,
            actor_type=actor_type,
            actor_id=actor_id,
            phase=phase,
            event_type=event_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            status=status,
            artifact_path=artifact_path,
            source_type=source_type,
        )
        encoded = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            existing = self.list_events(chronological=False)
            if any(item.event_id == event.event_id for item in existing):
                raise ValueError(f"duplicate event_id: {event.event_id}")
            with self.event_log_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return event

    # Friendly aliases for HTTP handlers and recording automation.
    append_event = record_event
    log_event = record_event

    def list_events(self, *, chronological: bool = True) -> list[DemoEvent]:
        with self._lock:
            try:
                lines = self.event_log_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(f"cannot read event log: {self.event_log_path}") from exc
            events: list[DemoEvent] = []
            seen: set[str] = set()
            for line_number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    if not isinstance(raw, dict):
                        raise ValueError("event is not an object")
                    event = DemoEvent.from_dict(raw)
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    raise ValueError(f"invalid event log line {line_number}") from exc
                if event.event_id in seen:
                    raise ValueError(f"duplicate event_id on event log line {line_number}")
                seen.add(event.event_id)
                events.append(event)
        if chronological:
            # ``sort`` is stable, so events with the same real timestamp retain
            # their append order rather than acquiring an arbitrary UUID order.
            events.sort(key=lambda item: _timestamp(item.timestamp_utc)[1])
        return events

    def operation_durations(self) -> list[dict[str, Any]]:
        """Pair reported starts with the next terminal event in the same operation."""

        pending: dict[tuple[str, str, str], list[DemoEvent]] = {}
        pairs: list[dict[str, Any]] = []
        for event in self.list_events():
            key = (event.correlation_id, event.phase, event.entity_id)
            if event.status == "started":
                pending.setdefault(key, []).append(event)
                continue
            starts = pending.get(key, [])
            if not starts:
                continue
            started = starts.pop(0)
            start_time = _timestamp(started.timestamp_utc)[1]
            end_time = _timestamp(event.timestamp_utc)[1]
            if end_time < start_time:
                continue
            pairs.append(
                {
                    "started_event_id": started.event_id,
                    "terminal_event_id": event.event_id,
                    "terminal_status": event.status,
                    "duration_seconds": (end_time - start_time).total_seconds(),
                }
            )
        return pairs

    def build_lineage(self, *, write: bool = True) -> dict[str, Any]:
        """Build referential lineage solely from persisted, caller-reported events."""

        events = self.list_events()
        stage_index = {stage: index for index, stage in enumerate(LINEAGE_PHASES)}
        duration_by_terminal = {
            pair["terminal_event_id"]: pair for pair in self.operation_durations()
        }
        nodes = []
        for event in events:
            node: dict[str, Any] = {
                "node_id": f"event:{event.event_id}",
                **event.to_dict(),
            }
            if event.event_id in duration_by_terminal:
                node["operation_duration_seconds"] = duration_by_terminal[event.event_id][
                    "duration_seconds"
                ]
            nodes.append(node)

        by_workflow: dict[str, list[DemoEvent]] = {}
        for event in events:
            by_workflow.setdefault(event.correlation_id, []).append(event)

        edges: list[dict[str, str]] = []
        workflows: list[dict[str, Any]] = []
        for correlation_id, workflow_events in sorted(by_workflow.items()):
            ordered = sorted(
                workflow_events,
                key=lambda item: (
                    stage_index[item.phase],
                    _timestamp(item.timestamp_utc)[1],
                ),
            )
            for source, target in zip(ordered, ordered[1:]):
                edges.append(
                    {
                        "edge_id": f"{source.event_id}:{target.event_id}",
                        "from_node_id": f"event:{source.event_id}",
                        "to_node_id": f"event:{target.event_id}",
                        "relationship": "precedes_in_workflow",
                        "correlation_id": correlation_id,
                    }
                )
            present = {event.phase for event in ordered}
            workflows.append(
                {
                    "correlation_id": correlation_id,
                    "event_ids": [event.event_id for event in ordered],
                    "present_phases": [phase for phase in LINEAGE_PHASES if phase in present],
                    "missing_phases": [phase for phase in LINEAGE_PHASES if phase not in present],
                    "complete": all(phase in present for phase in LINEAGE_PHASES),
                }
            )

        manifest = {
            "schema_version": 1,
            "event_log": self.event_log_path.name,
            "stage_order": list(LINEAGE_PHASES),
            "nodes": nodes,
            "edges": edges,
            "workflows": workflows,
        }
        if write:
            self._write_json(self.lineage_path, manifest)
        return manifest

    def render_mermaid(self) -> Path:
        manifest = self.build_lineage(write=True)
        lines = ["flowchart LR"]
        node_names: dict[str, str] = {}
        for index, node in enumerate(manifest["nodes"]):
            mermaid_id = f"n{index}"
            node_names[node["node_id"]] = mermaid_id
            label = "<br/>".join(
                (
                    str(node["phase"]),
                    str(node["event_type"]),
                    str(node["entity_id"]),
                    str(node["status"]),
                    str(node["source_type"]),
                )
            ).replace('"', "&quot;")
            lines.append(f'    {mermaid_id}["{label}"]')
            if node["source_type"] == "synthetic_fixture":
                lines.append(f"    class {mermaid_id} synthetic")
        for edge in manifest["edges"]:
            source = node_names[edge["from_node_id"]]
            target = node_names[edge["to_node_id"]]
            lines.append(f"    {source} --> {target}")
        lines.extend(
            (
                "    classDef synthetic fill:#fff4cc,stroke:#9a6b00,stroke-dasharray: 5 3",
                "    classDef default fill:#eaf3ff,stroke:#24558a,color:#13233a",
            )
        )
        self.mermaid_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.mermaid_path

    def render_timeline_html(self) -> Path:
        """Render a readable, self-contained timeline from persisted events."""

        events = self.list_events()
        durations = {
            pair["terminal_event_id"]: pair["duration_seconds"]
            for pair in self.operation_durations()
        }
        rows = []
        for event in events:
            duration = durations.get(event.event_id)
            duration_text = "—" if duration is None else f"{duration:.3f} s"
            artifact = html.escape(event.artifact_path)
            rows.append(
                "<tr>"
                f"<td><time>{html.escape(event.timestamp_utc)}</time></td>"
                f"<td>{html.escape(event.actor_type)}<br><small>{html.escape(event.actor_id)}</small></td>"
                f"<td>{html.escape(event.phase)}</td>"
                f"<td>{html.escape(event.event_type)}</td>"
                f'<td><span class="status {html.escape(event.status)}">'
                f"{html.escape(event.status)}</span></td>"
                f"<td>{duration_text}</td>"
                f"<td><code>{html.escape(event.entity_id)}</code></td>"
                f"<td><code>{html.escape(event.correlation_id)}</code></td>"
                f"<td><code>{artifact}</code></td>"
                f'<td><span class="source {html.escape(event.source_type)}">'
                f"{html.escape(event.source_type)}</span></td>"
                "</tr>"
            )
        document = (
            """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIIP Instructor Event Timeline</title>
<style>
:root{font-family:system-ui,sans-serif;color:#18202a;background:#f4f7fb}body{margin:0;padding:2rem}
main{max-width:1500px;margin:auto;background:white;padding:1.5rem;border-radius:12px;box-shadow:0 3px 18px #18304a22}
h1{margin:.1rem 0}.boundary{padding:.7rem 1rem;background:#fff4cc;border-left:5px solid #9a6b00}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{padding:.65rem;border-bottom:1px solid #dde5ee;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#eaf3ff}
code{white-space:nowrap}.status,.source{display:inline-block;padding:.15rem .42rem;border-radius:.4rem;font-weight:650}.completed,.actual_execution{background:#dff5e5;color:#155a2f}.started{background:#eaf3ff;color:#24558a}.failed{background:#fee4e2;color:#8c231c}.synthetic_fixture{background:#fff0bd;color:#735000}small{color:#566575}
</style></head><body><main><h1>SIIP System Event Timeline</h1>
<p>Chronological operations reported by the local research demonstration.</p>
<p class="boundary"><strong>Scientific boundary:</strong> yellow source labels identify synthetic fixtures. This page does not infer or create successful operations.</p>
<div class="table-wrap"><table><thead><tr><th>UTC timestamp</th><th>Actor</th><th>Phase</th><th>Event</th><th>Status</th><th>Duration</th><th>Entity</th><th>Workflow</th><th>Artifact</th><th>Source</th></tr></thead><tbody>
"""
            + "\n".join(rows)
            + """
</tbody></table></div></main></body></html>
"""
        )
        self.timeline_path.write_text(document, encoding="utf-8")
        return self.timeline_path

    def render_all(self) -> dict[str, Path]:
        """Regenerate all views without appending any event."""

        self.build_lineage(write=True)
        return {
            "event_log": self.event_log_path,
            "lineage": self.lineage_path,
            "mermaid": self.render_mermaid(),
            "timeline": self.render_timeline_html(),
        }

    def export_actual_records(
        self,
        filename: str,
        records: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
        *,
        source_type: str,
    ) -> Path:
        """Export supplied cohort/concept records without computing invented values."""

        _enum(source_type, "source_type", SOURCE_TYPES)
        if not _ARTIFACT_NAME_PATTERN.fullmatch(filename) or filename in {self.lineage_path.name}:
            raise ValueError("filename must be a simple .json artifact name")
        normalized = []
        for record in records:
            if not isinstance(record, Mapping):
                raise TypeError("each exported record must be a mapping")
            normalized.append(dict(record))
        payload = {
            "source_type": source_type,
            "record_count": len(normalized),
            "records": normalized,
        }
        path = self.artifact_dir / filename
        self._write_json(path, payload)
        return path

    def export_cohort_summary(
        self,
        records: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
        *,
        source_type: str,
    ) -> Path:
        """Export caller-supplied cohort rows under the required demo filename."""

        return self.export_actual_records(
            "08_cohort_summary.json", records, source_type=source_type
        )

    def export_concept_gap_analytics(
        self,
        records: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
        *,
        source_type: str,
    ) -> Path:
        """Export caller-supplied concept-gap rows without deriving claims."""

        return self.export_actual_records(
            "08_concept_gap_analytics.json", records, source_type=source_type
        )

    @staticmethod
    def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


# Shorter name for integration code.
EventRepository = DemoObservabilityRepository
