# Final independent PR audit — 2026-10-20

## Source integrity and strategy

Fetched origin before branch creation. Remote main remained `2288d9dde881490e1effdf130496524dcc8c08d7`. Every adjacent merge-base test returned success and every left divergence count was zero: Phase 2 +13, Windows +10, Phase 5 +13, Full Sandbox +11 = 47 commits. The dedicated `codex/siip-sandbox-release` candidate starts from the complete `793cd0d383849ff74742b7211cefbb2307ead8df` descendant. No commits are cherry-picked or duplicated. Use a history-preserving merge PR targeting main, conditional on its exact-head gates.

Five pre-existing worktrees were inspected. The primary Phase 5 checkout has uncommitted prototype edits/untracked source and remains untouched. Full Sandbox, authoring, extraction and verification worktrees were clean at audit. No worktree/branch removal or destructive reset/clean is authorized by this report.

GitHub evidence: PR #1/#2/#3 were individually fetched, open and Draft. All three had zero inline review threads and zero review submissions. main branch API reported protection disabled; repository rulesets were empty. Recheck these conditions before merge. Historical green checks are not candidate acceptance evidence.

## PR #1 — PARTIAL; preserve and consolidate

- Source `engineering/phase2-hardening` → target `main`.
- Range `2288d9d..61c60d2a5e73fc60175e94246c061ff34503dcc3`: 13 commits, 146 files, +9,813/−1 lines.
- Reviewed implementation: bounded SQL subprocess, public-grade projection, scoped synthetic profiles, identity-free immediate hooks, supported CSV/API snapshot synchronization, atomic checkpoints, source/research provenance, packaging/publication and CI.
- Security: explicit synthetic export allowlist, authorized API scope, group/missing identity fails closed, bounded HTTP responses, no internal PL database mutation in adapters. Hosted authentication and authentic learner ingestion remain unimplemented.
- Tests: historical Phase 2 counts are phase evidence, not current release totals. Latest head [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38664346582) and [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38664346502) succeeded. Current suite revalidates inherited behavior.
- Outstanding reviews: none observed. Dependency: foundation for Windows and all descendants. Disposition: include full ancestry; supersede only after merged main contains its head.

## Windows migration — PARTIAL; preserve with portability corrections

- Source `engineering/windows-migration`; no separate numbered PR in the supplied set.
- Range `61c60d2..ec81b84a10b29ef29d9fa0187974f0a8cbc7742a`: 10 commits, 45 files, +11,279/−111 lines.
- Reviewed implementation: cross-platform process/path support, durable queue, trusted identity resolution, evidence registry, upstream schema tests and scientific-readiness infrastructure.
- Defects in later demo tooling: fixed D: output/cache assumptions, default local-model dependency, and nonisolated EM/project paths. Release launcher defaults deterministic, uses configurable ignored output and independent stores; explicit installed local model remains optional.
- No original InstructKG execution or institutional deployment is established by Windows compatibility. Docker is unavailable on this audit workstation; native PL execution must pass on GitHub.
- Dependency: Phase 2; entirely included in Phase 5/Full Sandbox. Disposition: retain ancestry without separate cherry-picks.

## PR #2 — PARTIAL; preserve with authorization/history corrections

- Source `feature/phase5-integrated-prototype` → target `engineering/windows-migration`.
- Range `ec81b84..5d1a3ece81b1009207054593971595ad6095e215`: 13 commits, 36 files, +8,023/−86 lines.
- Reviewed implementation: EM reflections/review, adaptive projects/recommendation, evaluation instruments, concurrency/reliability tools, role authorization and portal/browser flows.
- Confirmed defects: synthetic auth default-development OR opt-in, missing hosted startup rejection, key byte stripping, incomplete durable review history, optional-evidence reconciliation mismatch. Scoped release fixes and negative regressions cover these paths.
- Latest historical [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38863828115), [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38863828092), [native integration](https://github.com/IanJ332/insructkg_sandbox/actions/runs/38863828325) succeeded.
- Outstanding reviews: none observed. Dependency: Windows + Phase 2. Disposition: included in descendant, supersede after complete ancestry verification on merged main. Instruments are infrastructure, not validated learning/mindset measurements.

## PR #3 — PARTIAL; complete descendant selected, release fixes required

- Source `codex/demo-full-sandbox-2026-10-20` → target `engineering/windows-migration`.
- PR range `ec81b84..793cd0d383849ff74742b7211cefbb2307ead8df`: 24 commits, 73 files, +16,801/−107 lines. Increment beyond PR #2: 11 commits, 44 files, +8,822/−65 lines.
- Reviewed implementation: course/module/lesson authoring, local-model extraction or labeled fallback, immutable reviewed graph versions, explicit assignment/source grounding, learner lifecycle, analytics/lineage, complete professor recorder and legacy-route ownership hardening.
- P0-B reproduced in external stored qwen3:8b feedback: INNER JOIN correctly identified, then unsupported COUNT/NULL advice despite valid `COUNT(e.employee_id)`. Historical prompt v3, measured 3687.953ms, graph `kg-81073e9f38be2c2c:v1`. Original evidence remains external and unchanged. Prompt v4 prohibits speculative extra errors; bounded COUNT/grouping guards fall back visibly; accepted model output remains unreviewed. Reference SQL is unchanged.
- Additional release fixes: concurrent saved-version replacement, incomplete graph/source version binding, async current-attempt history leakage, double-escaped JSON presentation, durable instructor review audit, fresh-key login instability.
- Latest historical [CI](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39370907703), [Security](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39370907681), [integration](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39370907715) succeeded. Earlier [push integration failed](https://github.com/IanJ332/insructkg_sandbox/actions/runs/39370903331) waiting for first instructor login. Binary signing-key whitespace trimming deterministically reproduces token invalidation and is corrected; the historical log alone cannot prove which generated bytes caused that run.
- The complete browser test already existed as a separate CI step; the older explicit four-file browser list is not the entire workflow. Release runs the isolated full test twice and tests restart, preserving its original test and bounded waits.
- Outstanding reviews: none observed. Dependencies: all 47 commits. Disposition: base consolidation on this complete head; do not merge inherited defects without release fixes/gates.

## Test/security acceptance and limitations

See `RELEASE_TEST_EVIDENCE.md` for actual candidate totals, exact-head CI, publication/dependency/Bandit/package checks and fresh-clone status. Missing external credentials/dependencies do not become fabricated successes. No original InstructKG, native dynamic publication, real learners, SSO, semantic quality guarantee or production readiness is claimed. The integration contract and next-phase blockers scope those tasks explicitly.

`AUDITED_COMMIT_INVENTORY.md` records complete commit boundaries and filename inventories generated directly from Git for all four ranges.
