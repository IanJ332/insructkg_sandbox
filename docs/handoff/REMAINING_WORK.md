> Historical phase evidence. Current release status: [release audit](../release/FINAL_PR_AUDIT.md) and [test evidence](../release/RELEASE_TEST_EVIDENCE.md). Earlier pending/completion claims are preserved as history.

# Remaining work after Phase 4.3 Security Closure & Research Handoff

Completed in Phase 4.3:
- Dynamic uncommitted HMAC secret generation (`auth_secret.key`) replacing static embedded keys.
- Strict service-to-service key authentication (`X-SIIP-Service-Key`) on `/api/queue/enqueue` and `/api/queue/reconcile`.
- Development-only gating (`SIIP_ALLOW_SYNTHETIC_AUTH=1`) and loopback/service caller checks on `/api/auth/synthetic-session`.
- Default server bind host hardened to loopback `127.0.0.1`.
- Reconciliation provenance validation checking student and question evidence (409 Conflict on mismatch) and preserving submission timestamps.
- Authentic SQL benchmark curation from ANU corpus (12,899 submissions, 393 students) to 25 benchmark cases across 8 exercises (raw datasets isolated on `D:\AI\Datasets\SIIP\`).
- Controlled experimental evaluation protocol supporting Conditions A-E, blinded review generation, and automated metrics analysis.
- 191/191 tests passing; 100% clean across Ruff, Mypy, Bandit (0 issues), and Publication Audit (0 secrets, 0 restricted paths).

| Priority | Recommended Next Milestone | Current Dependency | Acceptance Criteria |
|---|---|---|---|
| **P0** | **Execute Controlled 25-Case Inference Run** | Instructor authorization for local GPU run | Run `scripts/experiment_runner.py` with warm Qwen3 8B (~20 min, $0.00 cost) to generate model outputs across Conditions A-E. |
| **P1** | **Blind Pedagogical Review & Rubric Scoring** | Course TA / Instructor scoring | Evaluate randomized blinded review packet across correctness, concept relevance, hallucination rate, and actionability using `scripts/analyze_results.py`. |
| **P2** | **Institutional Readiness & Pilot Permissions** | IRB approval, institutional SSO integration, FERPA consent | Institutional approval for live student study; production SSO boundary integration. |

The engineering implementation baseline is **complete and frozen**.

