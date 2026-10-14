# PrairieLearn integration

Official interfaces inspected on 2026-10-14: [local installation](https://docs.prairielearn.com/installing/), [question server lifecycle](https://docs.prairielearn.com/question/server/), [string input](https://docs.prairielearn.com/elements/pl-string-input/), [external grading](https://docs.prairielearn.com/externalGrading/), [API](https://docs.prairielearn.com/api/). Checked-out source: eaaa91843807411918d260475e0a9188bcc2c979; the running image is independently pinned by digest f030faf735fdbb80c0307cc1b599d0757bb76a2f4573fbab9a7303adad4275ac. Its Git SHA is unavailable, so no source/image SHA equivalence is asserted. The selected hooks were exercised against the actual image.

## Course files and lifecycle

`infoCourse.json` defines SIIP SQL and timezone America/Chicago. `courseInstances/Fall2026/infoCourseInstance.json` defines the synthetic instance and publishing window. `assessments/sql-sandbox/infoAssessment.json` defines the Homework assessment and three questions. Each `info.json` uses type v3 and singleVariant=true: unlimited same-variant retries for these deterministic exercises.

The questions are sql_join_01 (matching employees), sql_join_02 (every employee), sql_join_03 (missing department matches). A multiline pl-string-input captures the SQL as data[submitted_answers][sql]. An empty built-in correct answer satisfies the element contract without exposing a reference solution. The custom grade hook overrides element grading and sets data[score], data[partial_scores][sql] and data[feedback]. Mustache output in pl-submission-panel is escaped. pl-answer-panel withholds the full solution.

The shared `serverFilesCourse/siip` package contains the evaluator and graph/feedback adapters. SQLite executes only SQL, never Python student code. Hidden dataset B contains a non-NULL unmatched foreign key and an empty department. The actual row outputs are retained in offline/internal grading evidence but never passed to the student or LLM.

## Actual browser verification

PrairieLearn ran at localhost:3000. Course sync jobs reported success. The assessment rendered with all three questions. Real local Dev User submissions were created through Save & Grade:

| Submission | Question | Query behavior | Displayed result |
|---|---|---|---|
| 1 | sql_join_01 | Correct INNER JOIN | 100% |
| 2 | sql_join_02 | INNER JOIN omits unmatched employees | 0%, conceptual guidance |
| 3 | sql_join_02 | Corrected LEFT JOIN retry | 100%, old attempt retained |
| 4 | sql_join_03 | Checks only NULL employee foreign key | 0%, distinguishes reference vs match |
| 5 | sql_join_03 | Corrected missing-match query | 100%, old attempt retained |

Screenshots and DOM snapshots are in artifacts/pl-*.png and .txt. The assessment reached 3/3. These five UI submissions are separate from the 21 offline fixture attempts. Local runtime/restart checks are recorded in VERIFICATION_REPORT.md.

## Profiles and supported exports

PrairieLearn owns stable assessment/variant/submission history. Question code does not assume student identity fields. The instructor's Downloads → all_submissions.csv path was exercised for this sandbox. `scripts/import_pl.py` accepts only artificial Dev User/HW1/known QIDs, maps to S003, stores source=local_prairielearn_export, retains available stable submission references, and checks recomputed score against the actual exported score. It omits private identity fields from normalized records. CSV exports provide instance/variant numbers; do not invent absent database IDs.

API `SubmissionDataSchema` in `apps/prairielearn/src/api/v1/endpoints/courseInstanceAssessmentInstances/index.ts` was inspected for field names. The API adapter uses only documented GET course_instances/:id/assessment_instances/:id/submissions with Private-Token authentication and an explicit identity map. Runtime production authorization and team mappings remain unverified. No submission injection, grade override write, course sync POST or hosted course access was performed.

## Why internal grading

The exercise needs a small SQL read engine, not an arbitrary code runner. Internal grading avoids Docker socket mounting and external-grader network assumptions. External grading remains an alternative if later limits require dedicated process/container isolation; it uses documented grader input/results files and needs the official jobs/socket setup. No external grader was configured or falsely marked verified.

## Hosted workflow

Obtain a new approved sandbox Course Space and course Editor permissions. Separately obtain instance student-data permissions for authorized export/API research access. Copy only reviewed course files to its authorized Git repository, sync through supported UI/API, preview questions, configure instance publishing and assessment access, and verify the deployed runtime. Do not copy local dev identity mapping, raw research PDFs/exports or Docker volume data. See DEPLOYMENT_GUIDE.md. Existing CS418 and unrelated courses remain untouched.
