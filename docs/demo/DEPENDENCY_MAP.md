# SIIP professor demonstration dependency map

Snapshot: 2026-10-19. Branch `feature/phase5-integrated-prototype`, baseline commit
`5d1a3ece81b1009207054593971595ad6095e215`.

## Existing executable components

| Demonstration need | Existing implementation | Current integration boundary |
|---|---|---|
| Synthetic authentication | `scripts/dashboard.py`, `siip.identity` | Instructor/student signed local sessions exist. |
| SQL question and submission | PrairieLearn course under `prairielearn-course/` | Native PL browser questions exist; dashboard also has a clearly labelled synthetic practice path. |
| Deterministic SQL grading | `siip.grader`, `siip.sql_worker`, `siip.pl_bridge` | Bounded SQLite grading is independent of model inference. |
| Concept diagnosis and graph context | `siip.feedback`, `siip.graph`, InstructKG schema/data | Existing graph evidence is unreviewed; no claim of fresh extraction is permitted. |
| Asynchronous feedback | `siip.jobs`, `scripts/feedback_worker.py`, dashboard queue routes | Persistent job lifecycle exists. Provider defaults to deterministic fallback. |
| Learner history and recommendation | `siip.store`, `siip.recommender`, dashboard student pages | Synthetic histories and history-derived recommendations exist. |
| EM reflection and review | `siip.em_*`, dashboard reflection/review routes | PROPOSED evidence and instructor state transitions exist. |
| Personalized projects | `siip.project_*`, dashboard project routes | Validated template generation and instructor review exist. |
| Instructor analytics | dashboard overview/students/graph/EM/projects and cohort JSON | Useful pieces exist across separate pages. |
| Browser verification | `tests/e2e/` and Playwright dependency | Existing tests cover PL, async feedback, EM, and dashboards but not the requested unified recording. |

## Smallest missing integration path

1. Add a local-only instructor authoring registry and upload form with hash/version/provenance.
2. Add an explicitly labelled synthetic-fixture KG extraction/review flow bound to that source.
3. Add local SIIP assignment authoring/publication records bound to approved graph nodes.
4. Surface the published assignment in the synthetic student journey and route its SQL through the existing deterministic grader/job/profile machinery.
5. Add event logging and data-lineage endpoints that reference persisted records rather than invented successes.
6. Add a focused professor-demo Playwright runner with separate instructor/student contexts, video, screenshots, JSON evidence, and post-run state assertions.
7. Assemble/probe the professor and uncut videos using an available encoder; preserve WebM and report honestly if MP4 encoding is unavailable.

## Ownership boundaries

- Agent A: instructor/course authoring backend and synthetic lesson asset; no dashboard or recording edits.
- Agent B: KG extraction-fixture/review backend and KG tests; no dashboard or authoring edits.
- Agent C: student journey audit and backend adapters/tests; no dashboard, KG, or recording edits.
- Agent D: analytics, lineage, and event-log backend/templates after A-C land; no recording automation.
- Agent E: browser automation, screenshots, timelines, and video packaging only after the integrated UI is stable.
- Main agent: dashboard/UI integration, service execution, conflict resolution, final verification, and acceptance report.

## Runtime facts to verify before recording

- Docker/PrairieLearn and dashboard health on ports 3000/8080.
- Actual Ollama model availability/digest and one bounded inference result, or labelled deterministic fallback.
- NVIDIA adapter and VRAM from `nvidia-smi`.
- Playwright browser availability.
- Video encoder/probe availability and D: output capacity.
