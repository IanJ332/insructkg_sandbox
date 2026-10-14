# Architecture decision record index

| ADR | Decision and reason | Consequence/review trigger |
|---|---|---|
| 001 | Keep modular Python package inside serverFilesCourse; supported PL lifecycle and shared host tests | Avoid core fork; revisit only for hosted runtime restrictions |
| 002 | SQLite teaching databases + separate analytics SQLite | Small reproducible local demo; course-scale locking/security needs benchmark and possible database migration |
| 003 | Deterministic grade authoritative; feedback optional and labeled | Model failure cannot change score; current bounded synchronous latency still needs hosted review |
| 004 | Explicit authorized CSV identity map | Avoid guessing UID or undocumented server hook; production adapter requires approved identity/API contract |
| 005 | Preserve raw graph direction/evidence and separate review/provisional overlays | Contradictions remain visible; no silent promotion to instructor truth |
| 006 | Synthetic-only records and loopback services | Public CI is reproducible without protected materials; no public dashboard deployment |
| 007 | Existing InstructKG reused unmodified in separate CPU image | Resolve platform dependency without algorithm change; larger runtime/weight downloads and timeout remain |
| 008 | Literal config + deterministic default + explicit paid sentinel | Credentials alone never authorize costs; user currently forbids all inference |
| 009 | Restrict wheel and Git contents independently; no blanket license | Rights ambiguity remains local; original code can still be published as authorized |
| 010 | Fast CI and security on pushes/PRs; slow actual PL separately | Real integration stays testable without forcing every edit through container startup |
| 011 | Atomic batch import, prepare/validate before BEGIN IMMEDIATE | No partial writes; batched feedback does not include earlier uncommitted rows |
| 012 | Strict mypy scoped to three new boundaries | Honest incremental adoption; do not claim whole-codebase typing |

These are retrospective decisions supported by current code and the baseline audit, not a fabricated prior ADR history. Hosted deployment and empirical learner claims are intentionally deferred pending actual resources and approvals.
