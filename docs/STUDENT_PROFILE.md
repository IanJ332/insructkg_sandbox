> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Synthetic student profiles

Five artificial identifiers S001–S005 represent different scripted trajectories. Twenty-one timestamped fixtures are generated locally. Correctness is derived from actual SQL evaluation. S001 is consistently correct; S002 struggles with outer JOIN/NULL; S003 improves; S004 struggles with missing matches; S005 repeatedly fails. Five actual local Dev User PL submissions are independently exported and mapped to S003 for integration demonstration.

## Stored records

`SubmissionRepository` creates schema_version=1 and an attempts table indexed by student/timestamp. Primary key attempt_id makes fixture and export imports idempotent. An ID collision with differing student, question or SQL is rejected. Each JSON record preserves:

- Synthetic student, question, assessment and attempt IDs; source and UTC timestamp.
- Submitted SQL and dataset version.
- Actual execution status and dataset-level result evidence.
- Observed error, candidate concepts and diagnosis source/confidence.
- Linked question concepts.
- Feedback mode, output, inference/model/prompt metadata.
- External submission references/score when present; unavailable external fields are not invented.

Course/reference data and graph metadata remain separate from the record database. Only synthetic records belong here. The raw local PL CSV is excluded from Git tracking and normalized records omit name/UID/UIN.

## Mastery heuristic

For each student/concept, keep the latest **executed** correct/semantic-error attempt for each linked question. Let n be the number of distinct such questions and c the number of latest answers that are correct:

`estimate = (1 + c) / (2 + n)`

This is Beta(1,1) smoothing of latest-question correctness, not a validated knowledge-tracing model. If n=0 the estimate is 0.5 (unobserved prior). Repeating the same question does not enlarge n; improvements replace that question's previous outcome. Compilation, execution and unsupported-query failures remain visible in history and error counts but do not enter the concept mastery denominator.

The profile separately reports all linked attempt counts, correct/incorrect counts, most recent timestamp, related questions, error frequencies and the full score trajectory. Possible prerequisite gaps are computed only where a prerequisite has a linked estimate below 0.5; otherwise prerequisite context is observed or unobserved. A missing observation is never called a confirmed gap. One linked correct question yields 2/3, never certainty.

All timestamps require an explicit timezone and normalize to UTC. Records sort by timestamp then attempt ID, making recalculation reproducible even when imports arrive out of order. SQL queries parameterize student identity, preventing cross-student mixing. Tests cover isolation, persistence, timestamp normalization, improved retries, collision handling and data integrity.

## Updating and inspection

`make seed` idempotently loads fixtures. The dashboard Students → S003 displays history, prerequisites and estimates. Its explicit synthetic-attempt form uses the same evaluation/feedback package and updates persistent analytics. Actual PL submissions update those profiles through the narrow authorized export importer; they do not silently acquire a guessed UID inside server.py.

`refresh_records.py` retains a timestamped backup and re-evaluates fixtures plus the current local export after engine changes. It is a development rebuild command, not a migration policy for real research records. Future authorized persistent research must version recalculations rather than overwrite evidence.
