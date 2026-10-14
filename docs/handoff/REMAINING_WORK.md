# Remaining work

The [next implementation plan](NEXT_IMPLEMENTATION_PLAN.md) contains files, tests, acceptance gates and risks for each item. No working component is scheduled for a cosmetic rebuild.

| Priority | Work | Blocker/dependency | Expected change and acceptance |
|---|---|---|---|
| P0.1 | Actual Baseline/RAG/KG inference | Explicit user no-inference instruction | Authorized future canary in feedback.py/evaluate.py; actual output/usage and unchanged scores |
| P0.2 | Fresh actual InstructKG stages | Ingest600s timeout; later model access forbidden | Profile extraction wrapper/container; actual stage metadata/counts and reviewable graph |
| P1.1 | Hosted feedback latency | Hosted runtime facts, model authorization | Measure hook budget; async service only if needed; bounded correct-attempt feedback |
| P1.2 | Load/containment/restore validation | Defined target workload | Worker/storage/tests/CI and documented limits; isolated restore hashes pass |
| P2.1 | Authorized hosted course and identity | Institutional access/policy | Versioned source adapter; synthetic hosted E2E with no existing course changes |
| P2.2 | Legacy backend assessment | Repository/rights unknown | Evaluate reusable boundaries against synthetic regression; documented reuse decision |
| P3.1 | Instructor graph/profile validation | Instructor judgments and labeled evidence | Versioned review/calibration; no unreviewed authority claims |
| P3.2 | Learning study, later EM/projects | Research approval, design and sample | Preregistered outcomes and reproducible analysis; EM separate future scope |

Current user action is not needed to maintain the local deterministic demo. See HUMAN_ACTION_REQUIRED.md only when pursuing the blocked research/deployment stages.
