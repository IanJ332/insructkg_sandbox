# Integration contracts

| Boundary | Input/output | Failure semantics |
|---|---|---|
| `grade(qid, sql)` | Known question ID + SQL → status, authoritative 0/1 score, dataset evidence, observation | Bounded worker failure becomes execution_error; broken reference is an application error |
| `generate_feedback(...)` | Safe grade plus selected context → text, mode, model/prompt, citations, latency, status, usage | Provider/validation/context failure is labeled fallback; never changes score |
| `ConceptGraph(path, provenance, reviews)` | Original A/B JSONL → records/nodes/errors/warnings | Missing file raises; malformed records are reported; no direction repair is hidden |
| `process_many(records)` | Strict normalized synthetic records → committed/reused output records | All validation/score checks before commit; transaction rollback on any collision/insert failure |
| `import_local_csv(repo,path)` | Only artificial Dev User/HW1/known QIDs → same repository | Rejects unknown identities/schema/score mismatch; no partial write |

## Local dashboard HTTP

`GET /health` returns synthetic=true, storage, KG availability, provider configuration and llm=not_probed. Health never calls a paid model. `GET /api/analytics` returns aggregate counts/question/concept/source summaries. `/students?id=S003`, `/graph` and `/compare` are local human-readable views.

`POST /api/attempts` requires JSON with exactly student_id, question_id and sql. Optional Idempotency-Key is an alphanumeric/dash/underscore token of at most 100 characters. A committed response (201) contains attempt_id, grading_status, score, feedback_status, persistence_status and request correlation_id. Retries with the same key reuse an immutable record; changed input is rejected. POST work is serialized locally around key lookup and ingestion to avoid generated-timestamp races.

Invalid payload/IDs return 400, untrusted Host/Origin 403, unknown routes 404, missing length 411, excessive body 413, wrong media type 415, storage/internal failures 503. Responses include Content-Length, Connection: close, X-Request-ID, no-store and a restrictive CSP. The dashboard is loopback synthetic tooling, not an authenticated public API.

Authorized PL API read adapter uses only documented GET endpoints and explicit identity mapping. It requires authorization, HTTPS outside loopback, and refuses credential-bearing redirects. Hosted connectivity remains unverified.

## Follow-up contracts

`feedback_for_attempt(repo, attempt_id, principal)` accepts only a trusted synthetic principal, queries attempt AND subject together, and returns feedback plus a minimized prior-only evidence receipt; it never overwrites grade/history. Untrusted dictionaries, cross-subject and missing attempts fail with the same access-denied error. `generate_feedback` now minimizes mastery to relevant bounded aggregates; metadata reports whether any history was supplied. PL calls it without history.

`SubmissionSynchronizer.sync_once()` validates the full supported GET array, defers null grades, deduplicates and commits attempts/checkpoint atomically; it returns counts only. No cursor is invented. Missing permissions/API/schema/scope failures cause no progress; stale checkpoint CAS requires refetch. CSV/API overlap requires explicit scoped reconciliation. See SUBMISSION_SYNCHRONIZATION.md.
