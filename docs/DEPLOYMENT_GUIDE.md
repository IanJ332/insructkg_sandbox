> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Authorized hosted deployment guide

No public or hosted deployment was performed. The local official PL container and separate analytics dashboard are the verified environments. An existing CS418 course must not be reused or inspected for this study.

## Required resources and access

1. A newly approved PrairieLearn sandbox Course Space for this research, its intended pilot module/instructor, and an authorized Git repository.
2. Course content Editor permission to author/sync questions. Separately, instance Student data viewer permission for approved read/export research access; Student data editor only if independently required. Editor alone does not authorize student records.
3. Instructor review/approval of question-concept mappings and every teaching edge; retain original judgments and signed/revisioned overlay decisions.
4. Approved model hosting/API and explicit permitted usage, budget, data policy and credentials. No local success implies provider/network availability in hosted question execution.
5. Research/data governance and IRB coordination, pseudonym mapping/retention plan, participant protections and institutional security review before any real study.
6. Access to any private prior SQL Feedback System repository if reuse is expected. This public-source implementation does not claim that absent system was integrated.

## Prepare a reviewable course change

Use the existing `prairielearn-course` package as the starting artifact, with no PL core patch. Preview all three questions against the actual hosted runtime before publishing. Ensure its Python environment supports subprocess execution and the needed SQLite controls; if it does not, use the supported external-grader mechanism and validate its bounded worker environment. Do not assume internal-question or external-grader networks can reach an LLM API. Default deterministic feedback requires no inference network.

Copy server-side modules, exercise schemas and reviewed graph artifacts to the approved repository. Exclude local database dumps, raw student exports, Dev User mappings, `.env`, runtime caches and unauthorized course PDF redistribution. Place any institution-approved course evidence in a server-only location with appropriate permissions. Review solution/hidden-data exposure in question params, correct_answers, feedback and client files.

The local course uses a deterministic module with unlimited same-variant retries and development publishing dates. The instructor must deliberately choose real dates, policies, access rules and grading weight. Create the intended Course Instance and Assessment through supported course files/UI, sync Git content and confirm the sync job succeeds. Preview as a student, verify correct and common wrong queries, and configure instance publishing/self-enrollment only within authorized scope.

## Data ingestion

Use the documented read endpoints with a scoped authorized account/PAT, only for the approved course instance. Adapter field names are mapped from the source schema, but hosted endpoint access has not been tested. Verify actual returned fields, permissions, missing identity/team cases, pagination if the deployed interface introduces it, and timestamp/score semantics before collection. Unsupported mappings must remain blockers.

The default repository accepts only synthetic IDs. A future production repository and approved linkage service must be implemented intentionally; do not remove the safety allowlist simply to load real records. Use study-specific HMAC pseudonyms and isolate the key/mapping. Do not expose UID/UIN to question templates or rely on nonexistent question-code identity fields.

## Deployment gates

Local smoke tests, actual hosted preview submissions, a reviewed KG version, provider timeout/leakage tests, data authorization and infrastructure review must all be documented. Deploy private instructor analytics behind institutional authentication and approved hosting; the current loopback dashboard is not a hosted product. Add operational backups, least-privilege service identities, monitoring and concurrency/resource controls suited to the intended pilot.

After authorization, use a draft course Git change reviewed by the instructor, sync only the new sandbox, run actual hosted submission verification and retain rollback content. This guide does not grant approval or request modification to any existing course.
