# Main release report

Classification: **Integrated Synthetic Research Sandbox**. This baseline is not a production classroom release.

The candidate preserves the complete 47-commit engineering ancestry and adds scoped authorization, feedback-quality, data-consistency, portability, reproducibility and documentation corrections. Individual outcomes and file/commit inventories are in `FINAL_PR_AUDIT.md` and `AUDITED_COMMIT_INVENTORY.md`; consolidation policy is in `PR_CONSOLIDATION_AUDIT.md`.

Pre-release main/rollback: `2288d9dde881490e1effdf130496524dcc8c08d7`. Complete implementation parent: `793cd0d383849ff74742b7211cefbb2307ead8df`. Final candidate and resulting main are determined only after the exact-head checks and merge complete. The annotated release tag and final handoff identify that resulting main SHA; this report does not invent a future merge SHA.

See `RELEASE_TEST_EVIDENCE.md` for exact observed totals and failures, `REPOSITORY_CLEANUP_REPORT.md` for retained/deleted-file classification, `CLEAN_ROOM_SETUP.md` for independent Windows reproduction, and `INTEGRATION_CONTRACTS.md` for adapter/publication/identity boundaries.

PR #1/#2/#3 remain open until successful consolidation and ancestry verification. No remote branches or local worktrees are automatically deleted. Preserve original checkout changes and external professor-video/failure evidence.

Next research tracks: original upstream InstructKG; authorized native PrairieLearn deployment; human feedback-quality evaluation; approved classroom instruments/study. `NEXT_PHASE_BLOCKERS.md` defines completion evidence. No learning improvement or faculty endorsement is claimed.

## Engineering acceptance snapshot

- Consolidation: [PR #4](https://github.com/IanJ332/insructkg_sandbox/pull/4), targeting main; 47 inherited commits plus scoped release corrections, preserved without squash/cherry-pick duplication.
- Tested runtime SHA: `5c726930894b24104b38f7205c9573f5aab06cf1`. PASS: 330 unit/integration tests, 7 distinct browser tests including restart, static/build/dependency/security checks. Native PrairieLearn final-head CI remains a mandatory separate gate.
- G6 and tag: after successful merge, independently clone main, install into a new environment, run health/auth/full-browser/restart checks, verify all supplied heads are ancestors, then create annotated `siip-sandbox-v1.0` if unused. `git show siip-sandbox-v1.0` is the durable final SHA/workflow/fresh-clone receipt. No tag exists merely because this procedure is committed.
- Reports: final `MAIN_RELEASE_REPORT.md`, `PR_CONSOLIDATION_AUDIT.md`, `REPOSITORY_CLEANUP_REPORT.md`, `RELEASE_TEST_EVIDENCE.md` and `NEXT_PHASE_BLOCKERS.md` are delivered together in the completed release handoff. Their measured post-merge results supplement these pre-merge repository records.
