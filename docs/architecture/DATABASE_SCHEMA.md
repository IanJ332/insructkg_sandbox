# Persistent data model

The integration's `SubmissionRepository` uses `artifacts/synthetic.sqlite3` (override SIIP_DB_PATH for isolated tests). PrairieLearn's PostgreSQL is a separate Docker volume at `/var/postgres` and is never used as an arbitrary injection API.

```mermaid
erDiagram
  SCHEMA_VERSION { integer version PK }
  ATTEMPTS {
    text attempt_id PK
    text student_id
    text question_id
    text timestamp
    text source
    text assessment_id
    text record
  }
```

`schema_version` is currently 1; Phase 2 does not require a destructive migration. The attempts(student_id,timestamp) index supports histories. JSON retains grade/evidence/diagnosis/concepts, feedback/version metadata and available external submission links. Original identity columns are not copied. Required fields and allowed external numeric ID fields are checked before insertion; unsupported extras are rejected.

Attempt IDs are immutable idempotency keys. Collision checks include identity, question, SQL, normalized timestamp, source, assessment and external scope/score. Preparation occurs outside the write transaction; BEGIN IMMEDIATE then rechecks existing rows to resolve concurrent duplicate writers. Any insert/collision exception rolls the whole batch back. Connections are closed explicitly; no provider call is performed while holding the write lock.

Records sort by UTC timestamp then attempt ID. Mastery uses the latest correct/semantic-error result per linked question, with Beta(1,1) smoothing. Ingestion does not convert compilation failures into concept mastery evidence. As-of retrieval avoids using future persisted attempts in earlier feedback.

SQLite is suitable for this local synthetic scale. Multi-user deployment needs an approved repository backend, concurrency/retention policy and transactional integration design. Future PostgreSQL migration should preserve immutable event provenance, not copy an uncontrolled JSON dump of identities.
