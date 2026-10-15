# Current status — Phase 2 cross-validation follow-up

Snapshot date: 2026-10-14, America/Chicago. Implementation snapshot: **47626e6c0326fb0cee59e61beceaebd76f071c6a** on `engineering/phase2-hardening`, [draft PR1](https://github.com/IanJ332/insructkg_sandbox/pull/1), unmerged. Documentation-only commits may follow; [verification.json](verification.json) keys executed CI to exact source SHAs. All accepted 83distinct tests are retained.

| Area | Status | Actual result/evidence | Boundary |
|---|---|---|---|
| Public deterministic suite | PASS |119/119,0fail/skip,47.941s; artifacts/followup/public-tests-final.log | Mock API/model transports; original public fixtures |
| Real existing graph suite | PASS |2/2; research-tests-final.log | Actual469 judgments/121 nodes; original graph unreviewed |
| Local personalized feedback | PASS, synthetic | Same current SQL/grade, contrasting S001/S002 prior histories produce different feedback; demo + regressions | Post-submission service only; no learner-login/learning-effect claim |
| Privacy/temporal boundaries | PASS, synthetic | Subject-scoped attempt query, explicit principal, exclusive cutoff, relevant numeric aggregates, cross-subject denial tests | Principal factory is local trusted code, not institutional authentication |
| Immediate PL feedback | PASS, history-free | Actual 3 questions/5 new browser submissions, feedback/retry and CSV import | No trusted identity/history in hook; no unauthorized lookup |
| API synchronization | PASS contract / live NOT_RUN | Mapping/dedup/late/incremental/profile/permissions/errors/rollback/CAS/CSV reconciliation tests | Local mock HTTP only; no PL token created or live API queried |
| CSV fallback | PASS | Verified actual PL export/import preserved | CSV remains explicit and supported |
| Local store/analytics | PASS |5 synthetic students;42 records,22 correct/20 incorrect;22 fixture +20 PL-export records | Synthetic only; profiles descriptive, not validated mastery |
| Restart/persistence | PASS | Exact20 PL submission IDs and42 record hashes survive clean stop/start | Own sandbox only; no volume deletion |
| Non-generative fresh ingestion | PASS, named CPU variant | Native13 chunks/163.01s; guarded Tesseract13 chunks/268.25s,16 cited pages, zero generation attempts | Original upstream serialization/chunker; enrichment disabled externally |
| Original-settings600s failure | Historical FAIL | Preserved logs; exact stage attribution unproven | Generative enrichment intentionally not rerun |
| Fresh concepts/roles/clusters/pairs/relations | BLOCKED / NOT_RUN | No generative inference permitted | Fresh chunks are not a completed KG or automatically promoted RAG corpus |
| Local endpoint/backend readiness | PASS contracts | Configurable endpoint/model/JSON mode/limits/errors; dry-run plans need no paid key for local backends | Actual Ollama/vLLM/GPU execution NOT_RUN |
| Windows GPU deployment | NOT_RUN; guide ready | Official-release pins, read-only readiness script and documented Windows/WSL2 recipes | Future hardware/driver/model unknown; no installations/serving |
| Live generative inference | BLOCKED | Explicit user instruction; zero actual generative calls | Mock transport success is not live inference |
| CI/security/publication | PASS | [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38662343534), [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38662343514), [actual PL E2E/restart](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38662337887) passed on implementation snapshot; 26-file code-only 0.2.1 wheel | No raw research/material/runtime artifacts published |
| Hosted learner integration / pilot | BLOCKED | Identity/auth/data/research/instructor permissions unavailable | No CS418, real records, production deployment or merge |

## What personalization means here

Immediate PL hints use the current question/grade and configured concept/KG context. They are not historically personalized. The separate local service uses an explicitly authorized synthetic subject and strictly prior evidence to produce different **deterministic** hints. Relevant model contexts differ too, tested with fake providers; live personalized LLM quality remains unverified. KG context does not establish semantically grounded or instructor-approved truth. See [capability distinctions](../research/FEEDBACK_CAPABILITIES.md) and [lifecycle](../architecture/PERSONALIZED_FEEDBACK_LIFECYCLE.md).

Feedback provenance is explicit: `prairielearn_hook_immediate`, `local_analytics_recomputed`, and `authorized_post_submission_replay`. Import recomputes analytics feedback; it is not a copy of the original PL hint. Older preserved records may lack the new origin field. Batch-ingestion hints use previously persisted history; the post-submission service recomputes after commit against all strictly earlier persisted events without overwriting grades or original feedback.

## Executed evidence and meaningful failures

Local evidence stays under ignored artifacts/followup/. Actual E2E submits five new attempts 16–20 and imports37→42 records;20 PL IDs survive restart. Original E2E evidence was retained separately in accepted-e2e-evidence/. Public CI uses a distinct synthetic graph/lesson, not the469-record local research graph. Source revisions/upstream pins are preserved.

A local restart initially failed because the official image retained a PostgreSQL socket lock in its writable layer. PG logs confirmed it; an owned-container recreation using the same named volume recovered all history. manage.py now stops ready bundled PostgreSQL through the official script before Compose stop. Two isolated regression tests and the actual exact-record restart pass. No PID/lock file or volume was blindly deleted.

An initial replay test compared an in-memory tuple to its persisted JSON array, and the first shutdown tests failed on macOS /var→/private/var path normalization. Those assertions were corrected and rerun; source behavior was not weakened. Historical failure logs remain local. The original 600s extraction failure is retained; the named CPU variant is a separately recorded successful experiment.

The apps remain local at http://localhost:3000/pl and http://127.0.0.1:8080/. The prototype is ready for technical review, not hosted learner delivery or a real pilot.

Fresh CI evidence: the disposable runner's synthetic fixture store went 21→26 records through 5actual PL submissions and supported CSV import; exact 5 PL IDs/26 record hashes survived clean restart. This is separate from the local 42record/20 PL-submission research-data run. No real graph/course PDF is uploaded to CI.
