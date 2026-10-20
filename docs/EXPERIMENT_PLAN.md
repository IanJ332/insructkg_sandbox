> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# Proposed learning-impact study — not approved or started

This document proposes a future Fall 2026 pilot. Synthetic technical checks are not evidence of learning effects. No real students have been assigned, randomized or measured.

## Readiness prerequisites

Professor/IRB coordination, an approved teaching module/course, appropriate permissions, a reviewed knowledge graph, approved model/data handling, and informed participation requirements must be resolved first. Fix fresh extraction/provider verification blockers and complete instructor evaluation of teaching guidance before offering treatment feedback.

## Design

Compare standard feedback (control) with KG-enhanced feedback (treatment); optionally include lecture-RAG as a third arm if feasible sample size supports it. Use the same base model, generation settings, deterministic grader, task difficulty, instruction time and grading policy. The instructional context is the intended experimental difference. Predefine whether assignment is by student or section to address contamination and section/instructor effects. No assignment code is implemented in this prototype.

Use an equivalent-form pretest on JOIN/NULL concepts; formative practice with logged attempts; a matched-difficulty posttest; and a delayed transfer question including unmatched non-NULL references. Ensure test items and rubric are reviewed independently of the graph/feedback authors. Students should have equivalent opportunities and standard support, with a plan for access and accommodations.

## Outcomes and analysis

Pre-register one primary endpoint, such as adjusted posttest concept score controlling for pretest score. Secondary endpoints may include delayed transfer, number of executed attempts, time on task, revision success, answer leakage reports, and student/instructor feedback surveys. Technical failure, latency and feedback validity are implementation outcomes, not learning gains.

Use an analysis appropriate to assignment level and score distribution: for example ANCOVA or a multilevel regression with pretest adjustment and section effects if justified. Specify intention-to-treat handling, missing-data policy, multiple-comparison correction for secondary outcomes, effect sizes/confidence intervals and sensitivity analyses before examining outcomes. Determine sample size from a defensible power analysis using prior evidence; do not invent a target effect from these fixtures.

Define a blinded instructor rating rubric for feedback specificity, concept relevance, evidence fidelity, observed-error support and solution leakage. Calibrate raters and report agreement. Log model versions, prompts, graph review revision, question versions, dataset versions and analysis code. Record safety/technical failures and provide a standard-feedback fallback policy.

## Data governance and limits

Use study pseudonyms, segregate identity linkage, minimize fields, define retention and permitted access, and obtain all necessary approvals before collection. Do not infer mental states from single errors or present the MVP mastery heuristic as validated knowledge tracing. Feedback could differ in verbosity/helpfulness beyond context despite matched prompts; measure this as a confound. Results from one module may not generalize to other SQL topics, instructors or student populations.
