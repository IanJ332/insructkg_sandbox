# Remaining work after Phase 4.2 Engineering Closure

Completed in Phase 4.2:
- Cryptographic learner authorization with HMAC-SHA256 signed tickets and session tokens; zero identity disclosure.
- Authoritative submission identity and unique provisional attempt generation (`prov-{student}-{qid}-{uuid}`); idempotent reconciliation.
- Single-owner SQLite queue architecture on Windows host with monotonic lease fencing tokens (`lease_token`).
- Prior-only historical personalization in `FeedbackWorker` scoped strictly before attempt creation time.
- Playwright end-to-end async browser validation and bounded local Qwen3 8B canary inference (`live_success`, 10.28s).
- All 188 tests passing; CI, Security, and Local Platform Integration workflows 100% green on GitHub.

| Priority | Recommended Next Milestone | Current Dependency | Acceptance Criteria |
|---|---|---|---|
| **P0** | **Offline Research Evaluation Benchmark** | Authentic anonymized student SQL corpus | Offline comparison of Baseline LLM vs. Lecture RAG vs. KG-grounded feedback across correctness, concept relevance, hallucination rate, and actionability. |
| **P1** | **Instructor Concept & Pedagogical Validation** | Instructor review packet | Verification of generated knowledge graph concepts, relation edges, and prerequisite hierarchy against syllabus. |
| **P2** | **Institutional Readiness & Pilot Permissions** | IRB approval, institutional SSO integration, FERPA consent | Institutional approval for live student study; production SSO boundary integration. |

The engineering implementation baseline is **frozen**. No further architectural refactoring or queue rebuilds are required prior to research evaluation.
