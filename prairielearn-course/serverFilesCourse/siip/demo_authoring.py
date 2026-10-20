"""Local-only instructor authoring records for the SIIP synthetic demonstration.

This module deliberately does not write to PrairieLearn or any SIIP database.  A
caller supplies an isolated directory, and the registry stores a JSON index plus
content-addressed lesson files below that directory.  ``publish_assignment``
means *visible to the local SIIP demo UI*, not native PrairieLearn publication.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

SYNTHETIC_PROVENANCE_LABEL = "SYNTHETIC COURSE MATERIAL — LOCAL RESEARCH DEMONSTRATION"
LOCAL_PUBLICATION_LABEL = "LOCAL SIIP ASSIGNMENT PUBLICATION — SYNTHETIC DEMO"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PROCESSING_STATUSES = frozenset({"UPLOADED", "PROCESSING", "PROCESSED", "FAILED"})
_MAX_FILENAME_LENGTH = 255
_MAX_GRADING_CONFIG_BYTES = 32 * 1024
DEFAULT_MAX_LESSON_BYTES = 8 * 1024 * 1024


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must start with an alphanumeric character and contain only "
            "letters, digits, '.', '_', ':', or '-' (maximum 128 characters)"
        )
    return value


def _validate_filename(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_FILENAME_LENGTH:
        raise ValueError("original_filename must contain 1 to 255 characters")
    if Path(value).name != value or value in {".", ".."}:
        raise ValueError("original_filename must be a basename, not a path")
    if any(ord(char) < 32 for char in value):
        raise ValueError("original_filename must not contain control characters")
    return value


def _json_object(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain only JSON-compatible values") from exc
    if len(encoded.encode("utf-8")) > _MAX_GRADING_CONFIG_BYTES:
        raise ValueError(f"{field_name} exceeds {_MAX_GRADING_CONFIG_BYTES} bytes")
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):  # Defensive; Mapping should always encode as an object.
        raise ValueError(f"{field_name} must encode to a JSON object")
    return decoded


def _id_tuple(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be an iterable of IDs, not a string")
    result = tuple(_validate_id(value, field_name) for value in values)
    if not result:
        raise ValueError(f"{field_name} must contain at least one ID")
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} must not contain duplicate IDs")
    return result


@dataclass(frozen=True)
class LessonRecord:
    """Immutable metadata for one uploaded lesson version."""

    source_document_id: str
    original_filename: str
    course_id: str
    upload_timestamp_utc: str
    sha256: str
    version: int
    synthetic_provenance_label: str
    processing_status: str
    stored_content_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LessonRecord":
        return cls(**dict(value))


@dataclass(frozen=True)
class AssignmentRecord:
    """A local demo assignment and its explicit publication boundary."""

    assignment_id: str
    course_id: str
    question_ids: tuple[str, ...]
    kg_node_ids: tuple[str, ...]
    created_at_utc: str
    grading_config: dict[str, Any]
    publication_status: str
    publication_timestamp_utc: str | None
    publication_label: str
    publication_channel: str
    native_prairielearn_publication: bool

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["question_ids"] = list(self.question_ids)
        result["kg_node_ids"] = list(self.kg_node_ids)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssignmentRecord":
        data = dict(value)
        data["question_ids"] = tuple(data["question_ids"])
        data["kg_node_ids"] = tuple(data["kg_node_ids"])
        return cls(**data)


class DemoAuthoringRegistry:
    """Persist synthetic lesson and local assignment records in an isolated directory.

    The caller should point ``storage_dir`` at a demonstration-artifact directory,
    never at PrairieLearn's course tree or a production data directory.  All public
    methods reload the index before mutation so separate request handlers observe
    each other's completed writes.  The lock protects threads in one process; this
    small demo registry is not intended as a multi-process database.
    """

    _SCHEMA_VERSION = 1

    def __init__(
        self,
        storage_dir: Path | str,
        *,
        max_lesson_bytes: int = DEFAULT_MAX_LESSON_BYTES,
        clock: Callable[[], str] = _now_utc,
    ) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        if max_lesson_bytes < 1:
            raise ValueError("max_lesson_bytes must be positive")
        self.max_lesson_bytes = max_lesson_bytes
        self._clock = clock
        self._lock = threading.RLock()
        self._index_path = self.storage_dir / "demo_authoring_registry.json"
        self._content_dir = self.storage_dir / "lesson_content"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._content_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if not self._index_path.exists():
                self._save(self._empty_index())
            else:
                self._load()

    @classmethod
    def _empty_index(cls) -> dict[str, Any]:
        return {"schema_version": cls._SCHEMA_VERSION, "lessons": [], "assignments": []}

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid demo authoring registry: {self._index_path}") from exc
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != self._SCHEMA_VERSION
            or not isinstance(data.get("lessons"), list)
            or not isinstance(data.get("assignments"), list)
        ):
            raise ValueError(f"Unsupported demo authoring registry schema: {self._index_path}")
        return data

    def _save(self, data: Mapping[str, Any]) -> None:
        temporary = self.storage_dir / f".demo_authoring_registry.{uuid.uuid4().hex}.tmp"
        payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self._index_path)
        finally:
            temporary.unlink(missing_ok=True)

    def upload_lesson(
        self,
        source: bytes | bytearray | memoryview | Path | str,
        *,
        source_document_id: str,
        course_id: str,
        original_filename: str | None = None,
    ) -> LessonRecord:
        """Register bytes or a file path as the next version of a synthetic lesson.

        Byte uploads require ``original_filename``.  Path uploads derive it from
        the path unless supplied.  The required provenance banner must occur in
        the uploaded bytes so an arbitrary document cannot silently be relabeled
        as synthetic demonstration material.
        """

        source_document_id = _validate_id(source_document_id, "source_document_id")
        course_id = _validate_id(course_id, "course_id")
        if isinstance(source, (bytes, bytearray, memoryview)):
            content = bytes(source)
            if original_filename is None:
                raise ValueError("original_filename is required when uploading bytes")
        else:
            path = Path(source)
            if not path.is_file():
                raise ValueError(f"lesson source is not a regular file: {path}")
            if path.stat().st_size > self.max_lesson_bytes:
                raise ValueError(f"lesson exceeds the {self.max_lesson_bytes}-byte limit")
            content = path.read_bytes()
            original_filename = original_filename or path.name

        original_filename = _validate_filename(original_filename)
        if not content:
            raise ValueError("lesson content must not be empty")
        if len(content) > self.max_lesson_bytes:
            raise ValueError(f"lesson exceeds the {self.max_lesson_bytes}-byte limit")
        if SYNTHETIC_PROVENANCE_LABEL.encode("utf-8") not in content:
            raise ValueError("lesson content must include the synthetic provenance label")

        digest = hashlib.sha256(content).hexdigest()
        relative_content_path = (Path("lesson_content") / f"{digest}.bin").as_posix()
        content_path = self.storage_dir / Path(relative_content_path)

        with self._lock:
            data = self._load()
            matching = [
                LessonRecord.from_dict(item)
                for item in data["lessons"]
                if item.get("source_document_id") == source_document_id
            ]
            if matching and any(item.course_id != course_id for item in matching):
                raise ValueError("a source_document_id cannot be reused across courses")
            version = max((item.version for item in matching), default=0) + 1
            if content_path.exists():
                if hashlib.sha256(content_path.read_bytes()).hexdigest() != digest:
                    raise ValueError("stored lesson content failed its SHA-256 integrity check")
            else:
                content_path.write_bytes(content)

            record = LessonRecord(
                source_document_id=source_document_id,
                original_filename=original_filename,
                course_id=course_id,
                upload_timestamp_utc=self._clock(),
                sha256=digest,
                version=version,
                synthetic_provenance_label=SYNTHETIC_PROVENANCE_LABEL,
                processing_status="UPLOADED",
                stored_content_path=relative_content_path,
            )
            data["lessons"].append(record.to_dict())
            self._save(data)
            return record

    def get_lesson(self, source_document_id: str, version: int | None = None) -> LessonRecord | None:
        source_document_id = _validate_id(source_document_id, "source_document_id")
        if version is not None and version < 1:
            raise ValueError("version must be positive")
        records = [
            item
            for item in self.list_lessons()
            if item.source_document_id == source_document_id
            and (version is None or item.version == version)
        ]
        return max(records, key=lambda item: item.version) if records else None

    def list_lessons(self, *, course_id: str | None = None) -> list[LessonRecord]:
        if course_id is not None:
            course_id = _validate_id(course_id, "course_id")
        with self._lock:
            records = [LessonRecord.from_dict(item) for item in self._load()["lessons"]]
        if course_id is not None:
            records = [item for item in records if item.course_id == course_id]
        return sorted(records, key=lambda item: (item.upload_timestamp_utc, item.version), reverse=True)

    def read_lesson_bytes(self, source_document_id: str, version: int | None = None) -> bytes:
        record = self.get_lesson(source_document_id, version)
        if record is None:
            raise KeyError(f"lesson not found: {source_document_id} version {version or 'latest'}")
        path = (self.storage_dir / record.stored_content_path).resolve()
        if path.parent != self._content_dir:
            raise ValueError("lesson content path escapes the registry content directory")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError("stored lesson content failed its SHA-256 integrity check")
        return content

    def set_lesson_processing_status(
        self, source_document_id: str, version: int, status: str
    ) -> LessonRecord:
        """Update extraction progress without changing immutable upload metadata."""

        source_document_id = _validate_id(source_document_id, "source_document_id")
        if status not in _PROCESSING_STATUSES:
            raise ValueError(f"status must be one of {sorted(_PROCESSING_STATUSES)}")
        with self._lock:
            data = self._load()
            for index, item in enumerate(data["lessons"]):
                current = LessonRecord.from_dict(item)
                if current.source_document_id == source_document_id and current.version == version:
                    updated = replace(current, processing_status=status)
                    data["lessons"][index] = updated.to_dict()
                    self._save(data)
                    return updated
        raise KeyError(f"lesson not found: {source_document_id} version {version}")

    def create_assignment(
        self,
        *,
        assignment_id: str,
        course_id: str,
        question_ids: Iterable[str],
        kg_node_ids: Iterable[str],
        grading_config: Mapping[str, Any],
    ) -> AssignmentRecord:
        """Create a draft in the local demo registry; no PrairieLearn write occurs."""

        assignment_id = _validate_id(assignment_id, "assignment_id")
        course_id = _validate_id(course_id, "course_id")
        questions = _id_tuple(question_ids, "question_ids")
        nodes = _id_tuple(kg_node_ids, "kg_node_ids")
        config = _json_object(grading_config, "grading_config")
        record = AssignmentRecord(
            assignment_id=assignment_id,
            course_id=course_id,
            question_ids=questions,
            kg_node_ids=nodes,
            created_at_utc=self._clock(),
            grading_config=config,
            publication_status="DRAFT",
            publication_timestamp_utc=None,
            publication_label=LOCAL_PUBLICATION_LABEL,
            publication_channel="LOCAL_SIIP_DEMO_REGISTRY",
            native_prairielearn_publication=False,
        )
        with self._lock:
            data = self._load()
            if any(item.get("assignment_id") == assignment_id for item in data["assignments"]):
                raise ValueError(f"assignment already exists: {assignment_id}")
            data["assignments"].append(record.to_dict())
            self._save(data)
        return record

    def publish_assignment(self, assignment_id: str) -> AssignmentRecord:
        """Mark an assignment visible in the local SIIP demo registry only."""

        assignment_id = _validate_id(assignment_id, "assignment_id")
        with self._lock:
            data = self._load()
            for index, item in enumerate(data["assignments"]):
                current = AssignmentRecord.from_dict(item)
                if current.assignment_id != assignment_id:
                    continue
                if current.publication_status == "PUBLISHED_LOCAL_DEMO":
                    return current
                published = replace(
                    current,
                    publication_status="PUBLISHED_LOCAL_DEMO",
                    publication_timestamp_utc=self._clock(),
                )
                data["assignments"][index] = published.to_dict()
                self._save(data)
                return published
        raise KeyError(f"assignment not found: {assignment_id}")

    def get_assignment(self, assignment_id: str) -> AssignmentRecord | None:
        assignment_id = _validate_id(assignment_id, "assignment_id")
        for item in self.list_assignments():
            if item.assignment_id == assignment_id:
                return item
        return None

    def list_assignments(
        self, *, course_id: str | None = None, published_only: bool = False
    ) -> list[AssignmentRecord]:
        if course_id is not None:
            course_id = _validate_id(course_id, "course_id")
        with self._lock:
            records = [AssignmentRecord.from_dict(item) for item in self._load()["assignments"]]
        if course_id is not None:
            records = [item for item in records if item.course_id == course_id]
        if published_only:
            records = [item for item in records if item.publication_status == "PUBLISHED_LOCAL_DEMO"]
        return sorted(records, key=lambda item: item.created_at_utc, reverse=True)
