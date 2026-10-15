"""Snapshot polling with idempotent writes and an atomic, compare-and-set checkpoint.

The documented PL endpoint has no incremental cursor. Never drop an attempt by
date/high-water ID: complete snapshots are reconciled and only new IDs are inserted.
"""

import hashlib
import json

from .sources import AuthorizedPrairieLearnAPISource


class SubmissionSynchronizer:
    def __init__(self, repo, source, *, legacy_attempt_ids=None):
        if not isinstance(source, AuthorizedPrairieLearnAPISource) or source.assessment_id is None:
            raise ValueError("Explicit authorized assessment scope required")
        self.repo, self.source = repo, source
        # Optional instructor-supplied reconciliation of CSV IDs in this exact API
        # scope. Never guess that a CSV instance NUMBER equals a database ID.
        self.legacy_attempt_ids = legacy_attempt_ids or {}

    def sync_once(self):
        previous = self.repo.checkpoint_state(self.source.scope)
        records, deferred_count = self.source.read_snapshot()  # validate before writes
        unique = {}
        for record in records:
            aid = record["attempt_id"]
            if aid in unique and unique[aid] != record:
                raise ValueError("Conflicting duplicate API submission")
            unique[aid] = record
        records = sorted(unique.values(), key=lambda r: (r["timestamp"], r["attempt_id"]))
        fingerprint = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        prepared = []
        aliases = 0
        existing_csv = [
            r for r in self.repo.records() if r["source"] == "local_prairielearn_export"
        ]
        for record in records:
            submission_id = record["external_links"]["submission_id"]
            legacy = self.legacy_attempt_ids.get(submission_id)
            if legacy is None and any(
                r["student_id"] == record["student_id"]
                and r.get("external_links", {}).get("submission_id") == submission_id
                for r in existing_csv
            ):
                raise ValueError(
                    "Ambiguous CSV/API overlap; explicit scope reconciliation required"
                )
            if legacy is not None:
                saved = self.repo.attempt_for_student(legacy, record["student_id"])
                if saved["source"] != "local_prairielearn_export":
                    raise ValueError("Only an explicitly scoped CSV event can be reconciled")
                for key in ["question_id", "submitted_sql", "timestamp", "external_score"]:
                    if saved.get(key) != record[key]:
                        raise ValueError("CSV/API reconciliation mismatch")
                if saved.get("external_links", {}).get("submission_id") != submission_id:
                    raise ValueError("CSV/API submission identifier mismatch")
                # Preserve the original immutable CSV source/scope. The configured
                # alias is an observation of the same event, not a second attempt.
                record = self.repo.normalize(
                    {
                        k: v
                        for k, v in saved.items()
                        if k
                        in {
                            "attempt_id",
                            "student_id",
                            "question_id",
                            "timestamp",
                            "submitted_sql",
                            "assessment_id",
                            "source",
                            "external_links",
                            "external_score",
                        }
                    }
                )
                aliases += 1
            prepared.append(record)
        state = {
            "snapshot_sha256": fingerprint,
            "completed_count": len(records),
            "deferred_count": deferred_count,
            "reconciled_csv_count": aliases,
            "latest_timestamp": max((r["timestamp"] for r in records), default=None),
            "policy": "full_snapshot_reconcile_v1; no high_water_filter",
        }
        committed = self.repo.process_many(
            prepared,
            sync_checkpoint={"scope": self.source.scope, "previous": previous, "state": state},
            include_commit_stats=True,
        )
        return {
            "status": "committed",
            "completed_count": len(records),
            "inserted_count": committed["inserted_count"],
            "deferred_count": deferred_count,
            "reconciled_csv_count": aliases,
            "live_inference_calls": 0,
        }
