# PrairieLearn component

The official image digest is pinned in `infrastructure/compose.yaml`; course mount is read-only and port 3000 binds loopback. The image/source commit are recorded independently. `infoCourse.json`, Fall2026 instance and sql-sandbox Homework configure three questions with unlimited single-variant retries.

Each question calls `siip.pl_bridge`. The hook sets the deterministic score before optional feedback work and assigns a correlation ID/grading timing. Feedback contains only safe guidance, possible concepts, references and explicit inference status. An empty built-in correct answer avoids exposing reference SQL; the custom hook overrides element grading.

`tests/e2e/prairielearn_flow.py --ack-local-synthetic` is an actual isolated browser test. It loads the course through PL, submits correct and wrong SQL, checks displayed feedback/retries, downloads the supported instructor CSV, atomically imports it and checks analytics agreement. It is not a direct-grader substitute. Browser traces remain local.

Hosted runtime capabilities and student identity are not assumed. Internal worker process restrictions and approved external-grader alternatives must be verified on the actual hosted sandbox. No CS418 or existing course is touched. See deployment/handoff docs for institutional gates.
