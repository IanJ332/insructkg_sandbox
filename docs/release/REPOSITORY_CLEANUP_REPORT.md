# Repository cleanup inventory

Status: PASS for scoped source-tree reconciliation; historical evidence preserved.

| Class | Disposition |
|---|---|
| Active runtime | Preserve `siip` package, dashboard/worker, native PL hooks and launch/manage commands |
| Current tests | Preserve all existing tests; add release security/quality/data regressions and dashboard restart verification |
| Research infrastructure | Preserve benchmark adapters, dataset manifest, upstream schema/ingestion/evaluation tools |
| Current documentation | Root README and `docs/release` become authoritative for this baseline |
| Historical reports | Retain Phase 2–5 reports at stable paths with historical banners and current-release links; avoid breaking citations |
| Generated artifacts | Remain ignored; extend exclusions for SQLite sidecars and model-weight formats |
| Duplicate/unused scripts | None removed: static similarity alone does not prove safe supersession |

Deletion inventory: **no runtime, test, research, report or evidence files deleted**. README content is replaced to remove stale three-question/121-test/current-inference-blocked claims. No large directory restructuring was justified. No branches/worktrees are automatically removed.

Portability: replace fixed output/cache drive assumptions; default launcher to deterministic/no GPU; preserve explicit browser/model configuration; isolate submission/job/EM/project databases; add receipt-verified stop command. Current data/model/video files remain external. Publication scan checks prospective files and all reachable Git history; raw scan output stays ignored.

Retirement proposals after successful consolidation: PR #1/#2/#3 source branches and the authoring/extraction/verification worktrees may be reviewed for retirement only after ancestry and clean-state checks. The original checkout has uncommitted prototype work and is **not eligible** for automatic retirement. Preserve every dirty worktree. The full-sandbox worktree and external professor video remain useful rollback/evidence references.
