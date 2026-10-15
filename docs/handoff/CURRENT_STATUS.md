# Current status — Phase 4.2 Engineering Closure

Snapshot date: 2026-10-15, America/Chicago. Implementation snapshot: **07b1b16a0f7020e2eaafd347ba210222e8577c88** on `engineering/windows-migration`, targeting `engineering/phase2-hardening`. All 188 distinct public tests pass (56.71s). All GitHub Actions workflows (CI, Security, Local platform integration) are verified green.

| Area | Status | Actual result/evidence | Boundary |
|---|---|---|---|
| Public deterministic suite | PASS | 188/188, 0 fail/skip, 56.71s | Includes authorization, submission identity, queue topology, and personalization suites |
| Cryptographic authorization | PASS | HMAC-SHA256 signed tickets (?ticket=...) and session tokens; zero identity disclosure on 401/403 | Local synthetic authentication; production SSO remains an institutional requirement |
| Submission identity & idempotency | PASS | Distinct provisional attempts (prov-{student}-{qid}-{uuid}); idempotent authoritative (pl-{id}); reconciliation API | Live PL hooks generate provisional attempts; reconciled during ingestion |
| Single-owner SQLite queue | PASS | Durable host SQLite queue; WAL mode + PRAGMA busy_timeout; monotonic lease_token fencing | Windows host owns DB; Docker container communicates via HTTP POST /api/queue/enqueue |
| Historical personalization | PASS | Worker auto-queries prior mastery (as_of < created_at); distinct low/high guidance; clean unpersonalized labeling | Pedagogical KG grounding decoupled from learner attempt history |
| Async browser delivery | PASS | Playwright test (1.55s) verifies PL submit -> deterministic grade -> queue -> worker -> browser retrieval -> 403 check | Mock worker inference in fast automated test; live Ollama verified in canary |
| Live local GPU canary | PASS | 1 bounded Qwen3 8B canary on RTX 5070 Ti: live_success, 10.28s latency, 107 completion tokens | Model qwen3:8b Q4_K_M on 127.0.0.1:11434; citations ['public:lesson:2'] |
| Remote CI / Security / Integration | PASS | [CI (38687222671)](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38687222671), [Security (38687222662)](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38687222662), [Integration (38687222773)](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38687222773) | 100% green on commit 07b1b16 |
| Hosted learner pilot | BLOCKED | Institutional SSO, IRB approval, authorized course materials | Technical architecture frozen and ready for offline research evaluation |

## What personalization means here

Immediate PL hints use the current question/grade and configured concept/KG context. They are not historically personalized. The separate local service uses an explicitly authorized synthetic subject and strictly prior evidence to produce different **deterministic** hints. Relevant model contexts differ too, tested with fake providers; live personalized LLM quality remains unverified. KG context does not establish semantically grounded or instructor-approved truth. See [capability distinctions](../research/FEEDBACK_CAPABILITIES.md) and [lifecycle](../architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md).

Feedback provenance is explicit: `prairielearn_hook_immediate`, `local_analytics_recomputed`, and `authorized_post_submission_replay`. Import recomputes analytics feedback; it is not a copy of the original PL hint. Older preserved records may lack the new origin field. Batch-ingestion hints use previously persisted history; the post-submission service recomputes after commit against all strictly earlier persisted events without overwriting grades or original feedback.

## Executed evidence and meaningful failures

Local evidence stays under ignored artifacts/followup/. Actual E2E submits five new attempts 16–20 and imports37→42 records;20 PL IDs survive restart. Original E2E evidence was retained separately in accepted-e2e-evidence/. Public CI uses a distinct synthetic graph/lesson, not the469-record local research graph. Source revisions/upstream pins are preserved.

A local restart initially failed because the official image retained a PostgreSQL socket lock in its writable layer. PG logs confirmed it; an owned-container recreation using the same named volume recovered all history. manage.py now stops ready bundled PostgreSQL through the official script before Compose stop. Two isolated regression tests and the actual exact-record restart pass. No PID/lock file or volume was blindly deleted.

An initial replay test compared an in-memory tuple to its persisted JSON array, and the first shutdown tests failed on macOS /var→/private/var path normalization. Those assertions were corrected and rerun; source behavior was not weakened. Historical failure logs remain local. The original 600s extraction failure is retained; the named CPU variant is a separately recorded successful experiment.

The apps remain local at http://localhost:3000/pl and http://127.0.0.1:8080/. The prototype is ready for technical review, not hosted learner delivery or a real pilot.

Fresh CI evidence: the disposable runner's synthetic fixture store went 21→26 records through 5actual PL submissions and supported CSV import; exact 5 PL IDs/26 record hashes survived clean restart. This is separate from the local 42record/20 PL-submission research-data run. No real graph/course PDF is uploaded to CI.
