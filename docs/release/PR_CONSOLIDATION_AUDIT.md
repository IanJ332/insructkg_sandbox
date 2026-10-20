# PR consolidation audit

Strategy: one audited history-preserving PR from `codex/siip-sandbox-release` to current main. Its parent is complete sandbox `793cd0d383849ff74742b7211cefbb2307ead8df`; the 47 existing commits include all supplied Phase 2, Windows, Phase 5 and Full Sandbox heads. No squash of the engineering history, duplicate cherry-picks, retargeting or forced main update is used.

Pre-merge remote main: `2288d9dde881490e1effdf130496524dcc8c08d7`. Rollback reference: this pre-release main SHA; operational rollback must use reviewed revert/restoration rather than force-pushing main. Preserve local runtime databases separately.

Mandatory pre-merge checks: fetch again; verify main/head SHA and zero unexpected divergence; recheck reviews/rules; require successful CI, Security and Local platform integration on the final candidate. Any changed main requires reconciliation and new exact-candidate validation. Failed gates leave the consolidation PR open.

Only after successful integration and G6 fresh-main verification may PR #1, #2 and #3 be closed as superseded, linking the merged consolidation and confirming each source head is an ancestor. Preserve discussions and all branches/worktrees. Release tag creation follows successful fresh-clone validation and uses an annotated synthetic-sandbox label.

This committed audit specifies the gate protocol. The final main SHA, PR URL, workflow URLs, tag and clean-room outcome are recorded in the final release handoff/annotated tag, after those operations actually complete. See `FINAL_PR_AUDIT.md` for individual findings and `RELEASE_TEST_EVIDENCE.md` for measured local evidence.

Consolidation URL: https://github.com/IanJ332/insructkg_sandbox/pull/4. Runtime snapshot 5c72693 passes 330 unit/integration and 7 browser tests. Final documentation-head checks, resulting main SHA, fresh-main validation and old-PR dispositions are recorded only after completion in the annotated tag/final handoff.
