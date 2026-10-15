# Current status — Phase 4.3 Security Boundary Closure & Research Evaluation Handoff

Snapshot date: 2026-10-15, America/Chicago. Branch: `engineering/windows-migration`, targeting `engineering/phase2-hardening`. All 191 distinct public tests pass (49.14s). Code formatting, linting, Mypy strict typing, Bandit security scan (0 issues), and publication audit (0 secrets, 0 restricted paths) are 100% clean.

| Area | Status | Actual result/evidence | Boundary |
|---|---|---|---|
| Public deterministic suite | PASS | 191/191, 0 fail/skip, 49.14s | Includes authorization, submission identity, queue topology, and personalization suites |
| Hardened service boundary | PASS | Enforced `X-SIIP-Service-Key` on `/api/queue/enqueue` and `/api/queue/reconcile`; default listen `127.0.0.1` | Queue mutations require service key; 401 Unauthorized for callers without key |
| Isolated dev-only auth gate | PASS | `/api/auth/synthetic-session` gated to `SIIP_ALLOW_SYNTHETIC_AUTH=1` + loopback/service caller check; 403 otherwise | Production/hosted environments strictly require institutional SSO |
| Dynamic uncommitted HMAC secret | PASS | `get_auth_secret()` dynamically generates 32-byte secret (`auth_secret.key`, gitignored); no static default secret in repo | Zero hardcoded cryptographic secrets in source |
| Provenance & conflict check | PASS | `jobs.py` `reconcile()` enforces student/question evidence match (409 Conflict on mismatch); separates submission time | Prevents cross-student or cross-question attempt collision |
| Authentic SQL benchmark | PASS | ANU authentic student corpus (12,899 submissions, 393 students) curated to 25 benchmark cases across 8 exercises | Raw datasets stored strictly on `D:\AI\Datasets\SIIP\`; zero C: drive leakage |
| Blind evaluation protocol | PASS | `experiment_runner.py` dry-run verified; generates blinded review packets across Conditions A-E | Local GPU resource estimate: ~19.8 min, 125 inferences, $0.00 cost |
| Playwright E2E browser suite | PASS | 5/5 browser submissions PASS (26s); actual PL UI on port 3000 -> CSV export -> analytics import | End-to-end integration verified against live local container |
| Remote CI / Security / Integration | PASS | GitHub Actions workflows green on verified baseline | Pre-push verification complete for Phase 4.3 |
| Hosted learner pilot | BLOCKED | Institutional SSO, IRB approval, authorized course materials | Technical architecture frozen; handoff to offline research evaluation |

## What personalization means here

Immediate PL hints use the current question/grade and configured concept/KG context. They are not historically personalized. The separate local service uses an explicitly authorized synthetic subject and strictly prior evidence to produce different **deterministic** hints. Relevant model contexts differ too, tested with fake providers; live personalized LLM quality remains unverified. KG context does not establish semantically grounded or instructor-approved truth. See [capability distinctions](../research/FEEDBACK_CAPABILITIES.md) and [lifecycle](../architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md).

Feedback provenance is explicit: `prairielearn_hook_immediate`, `local_analytics_recomputed`, and `authorized_post_submission_replay`. Import recomputes analytics feedback; it is not a copy of the original PL hint. Older preserved records may lack the new origin field. Batch-ingestion hints use previously persisted history; the post-submission service recomputes after commit against all strictly earlier persisted events without overwriting grades or original feedback.

## Executed evidence and meaningful failures

Local evidence stays under ignored artifacts/followup/. Actual E2E submits five new attempts 16–20 and imports37→42 records;20 PL IDs survive restart. Original E2E evidence was retained separately in accepted-e2e-evidence/. Public CI uses a distinct synthetic graph/lesson, not the469-record local research graph. Source revisions/upstream pins are preserved.

A local restart initially failed because the official image retained a PostgreSQL socket lock in its writable layer. PG logs confirmed it; an owned-container recreation using the same named volume recovered all history. manage.py now stops ready bundled PostgreSQL through the official script before Compose stop. Two isolated regression tests and the actual exact-record restart pass. No PID/lock file or volume was blindly deleted.

An initial replay test compared an in-memory tuple to its persisted JSON array, and the first shutdown tests failed on macOS /var→/private/var path normalization. Those assertions were corrected and rerun; source behavior was not weakened. Historical failure logs remain local. The original 600s extraction failure is retained; the named CPU variant is a separately recorded successful experiment.

The apps remain local at http://localhost:3000/pl and http://127.0.0.1:8080/. The prototype is ready for technical review, not hosted learner delivery or a real pilot.

Fresh CI evidence: the disposable runner's synthetic fixture store went 21→26 records through 5actual PL submissions and supported CSV import; exact 5 PL IDs/26 record hashes survived clean restart. This is separate from the local 42record/20 PL-submission research-data run. No real graph/course PDF is uploaded to CI.
