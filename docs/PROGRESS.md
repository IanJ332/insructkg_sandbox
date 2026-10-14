# Progress

- Phase 0: repositories retrieved, commits matched, real artifact schema/counts audited; implementation architecture selected. Docker Desktop started. Official PrairieLearn image pulling.
- Phases 1–12: in progress. No runtime, browser or inference success claimed yet.

- Phases 1–5: actual official PrairieLearn image starts; course and assessment sync; all three student questions render and grade. UI evidence: Q1 correct (submission 1), Q2 incorrect then correct (2,3), Q3 NULL-only incorrect then correct (4,5). Custom feedback and history displayed. All reference solutions remain server-side.
- Phases 7–8: 21 fixture attempts processed; 5 real local PL attempts exported through supported instructor CSV and imported to explicitly designated synthetic S003. Total 26 normalized records with sources kept separate. Dashboard running on loopback.
- Phase 4: original graph parsed (469/319/150), 121 concepts, 9 flagged records, no instructor-approved edges. Eight developer provisional dependencies, separate provenance. Review queue written.
- Phase 6/9: live inference and fresh KG extraction BLOCKED by unavailable authorized model resources. Host optional dependency dry-run also fails: no compatible torch wheel for macOS Intel Python 3.13. No upstream model calls made; no fresh graph claimed.
- Phase 10: 63 paired deterministic feedback outputs generated, 0 live inference successes. Human feedback-quality rating pending.
- Phase 11: 40 tests pass after fixes for macOS extension-loading API and classification of unsupported functions. SQL safety and timeout checks executed. Persistence volume migration/restart verification in progress.

- Local database persistence correction completed: backup retained, PostgreSQL restored while the app was stopped, correct /var/postgres volume used. Container recreation retained the five actual UI submissions. Initial restoration with a running app encountered transient schema dependencies; corrected by a clean stopped-app restore. No unrelated databases were touched.
- Dashboard browser checks passed: source-separated history, original edge inspection, three clearly labeled fallback outputs. One new synthetic form submission increased records 26 → 27, correct 12 → 13; S003 history updated. This additional attempt is not a PrairieLearn submission.
- Documentation and commands delivered; final complete test and normal stop/start checks underway. Live provider inference, fresh upstream extraction and hosted/real-data connectivity remain blocked/unverified as documented.

- Final verification: 43 automated tests pass; five live HTTP checks pass; normal stop/start preserves all five real PL submissions and all 27 synthetic profile records. Browser rechecked assessment at 3/3 after restart. Upstream checkouts remain unmodified and pinned.
- Acceptance delivery: 18 PASS, 2 BLOCKED (live model feedback and fresh extraction), 0 FAIL, 0 NOT_RUN in the mandatory local matrix. Full definition of done has not been reached because the model/resource blockers remain. Hosted access and real-data experiments remain intentionally unperformed.
