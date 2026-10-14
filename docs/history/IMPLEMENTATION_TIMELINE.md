# Implementation timeline

All dates below are 2026-10-14 unless the evidence explicitly says otherwise. No invented release chronology is assigned to earlier work.

1. Phase 1 artifacts/source documented a local three-question PL integration, shared SQL/KG/feedback package, five synthetic profiles and 43 tests. The Phase 2 baseline independently reproduced 43 tests, five HTTP checks, real assessment history and 27 records; earlier root-level docs remain the historical record.
2. Baseline source ZIP, SQLite backup and PostgreSQL dump were saved locally. Destination visibility and existing README commit 2288d9d were checked. Root Git history was initialized from that remote and preserved in recovery commit 581c5e4 on engineering/phase2-hardening. Nested upstream checkouts were preserved.
3. Concrete persistence/API/graph/feedback defects were hardened; 40 tests added and two real-data tests explicitly separated from public fixtures. Typed configuration/ingestion/logging boundaries, packaging and security checks were introduced.
4. Actual browser E2E first encountered cold PL compilation readiness, then a whitespace-sensitive score selector after five successful submissions. Fixes retained prior attempts; final run completed five further submissions and imported ten new records (37 total). No failed run was relabeled as a passed full E2E.
5. CPU Linux extraction image resolved the Mac import incompatibility. Unmodified upstream import check passed without network. Actual PDF ingestion downloaded public parsing models but timed out after 600 seconds with no output chunks. No model-dependent graph stage was fabricated.
6. Exact-record restart verification, public publication audit, organized engineering/research/handoff documents and GitHub workflows complete this phase. Final commit/run links are recorded in verification.json; live inference remains blocked by explicit user direction.
