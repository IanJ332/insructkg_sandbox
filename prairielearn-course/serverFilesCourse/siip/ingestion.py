"""Narrow, atomic local export import; no production identity inference."""

import csv
import json
from pathlib import Path
from typing import Any

from .grader import QUESTIONS
from .store import SubmissionRepository


def read_local_csv(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("UID") != "dev@example.com" or row.get("Question") not in QUESTIONS:
                raise ValueError(
                    "Export contains identity/question outside the local demo allowlist"
                )
            if row.get("Assessment") != "Homework 1":
                raise ValueError("Export is outside local demo HW1")
            try:
                answer = json.loads(row["Submitted answer"])
                record = {
                    "attempt_id": "local-pl-" + row["submission_id"],
                    "student_id": "S003",
                    "question_id": row["Question"],
                    "timestamp": row["Submission date"],
                    "submitted_sql": answer["sql"],
                    "assessment_id": "sql-sandbox",
                    "source": "local_prairielearn_export",
                    "external_links": {
                        "submission_id": row["submission_id"],
                        "assessment_instance_number": row["Assessment instance"],
                        "variant_number": row["Variant"],
                    },
                    "external_score": float(row["Score"]),
                }
                records.append(SubmissionRepository.normalize(record))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Malformed or incomplete local export row") from exc
    return records


def import_local_csv(repo: SubmissionRepository, path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = repo.process_many(read_local_csv(path))
    return result
