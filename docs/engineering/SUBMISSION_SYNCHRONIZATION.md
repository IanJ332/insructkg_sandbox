# Local submission synchronization

Implementation: `siip.sources.AuthorizedPrairieLearnAPISource`, `siip.synchronization.SubmissionSynchronizer`, `SubmissionRepository.process_many`, and `scripts/sync_pl.py`. See the [lifecycle](../architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md) for identity/privacy and event-time semantics.

The current CLI is **local synthetic only**. It never reads a hosted course. The API contract is tested with local mock HTTP servers; no PL token was created and no authenticated live API poll is claimed. The independently verified actual-PL CSV fallback remains supported.

Copy `infrastructure/local-pl-scope.example.json` to ignored `artifacts/local-pl-scope.json`, verify the local course/assessment/instance IDs and explicit synthetic identity map, and put a future approved local token in ignored `.env` as SIIP_PL_API_TOKEN. Do not put it in the scope JSON or argv. Do not run this against any course with real records. No token is necessary for deterministic tests.

```sh
.venv/bin/python scripts/sync_pl.py --scope-file artifacts/local-pl-scope.json --ack-local-synthetic-api
# Optional finite repeated polls; no scheduler is installed:
.venv/bin/python scripts/sync_pl.py --scope-file artifacts/local-pl-scope.json --ack-local-synthetic-api --polls 3 --interval 10
```

There is no undocumented since/date cursor, automatic course discovery or guess at student UID. Full snapshots are bounded to 8 MiB / 10,000 rows. Redirects and unexpected pagination fail closed. HTTP 401/403 produce a sanitized permission error; transport/HTTP/schema errors abort without writes/checkpoint movement. Model/provider generation is never part of synchronization.

Each successful response reports inserted/completed/deferred/reconciled counts only. Insert counts are computed inside the write transaction. The repository's additive schema migration records version 2 and creates sync_checkpoints; all existing attempts remain unchanged. A failed checkpoint write rolls back attempt inserts. Stale concurrent checkpoints require a fresh poll. Partial imports and deleting absent remote records are not supported.

CSV→API transitions require explicit `legacy_attempt_ids` scoped to the configured endpoint. Empty aliases are appropriate only when no overlapping CSV history exists. Ambiguous overlap, changed immutable submissions or score disagreement stops the poll for review. Preserve the CSV source metadata; an API observation is not a second learner attempt.

Tests cover subject mapping/minimization, identical/conflicting duplicates, late lower IDs, event-time profiles, incremental new inserts, pending grades, unknown subjects/teams/scope, permissions, malformed/failed/redirected API responses, concurrent polls, atomic checkpoint failure, replay/restart and explicit CSV reconciliation. Hosted credentials, live PL API connectivity and production identity handling remain NOT_RUN/BLOCKED.
