# Documentation index

Start with [current status](handoff/CURRENT_STATUS.md), [external review packet](handoff/EXTERNAL_REVIEW_PACKET.md) and [next implementation plan](handoff/NEXT_IMPLEMENTATION_PLAN.md).

- Architecture: [system](architecture/SYSTEM_OVERVIEW.md), [data flow](architecture/DATA_FLOW.md), [contracts](architecture/INTEGRATION_CONTRACTS.md), [schema](architecture/DATABASE_SCHEMA.md), [security boundaries](architecture/SECURITY_MODEL.md).
- Components: [PrairieLearn](components/PRAIRIELEARN.md), [SQL grader](components/SQL_GRADER.md), [InstructKG](components/INSTRUCTKG.md), [feedback](components/LLM_FEEDBACK.md), [analytics](components/STUDENT_ANALYTICS.md).
- Engineering: [setup](engineering/LOCAL_SETUP.md), [CI/CD](engineering/CI_CD.md), [tests](engineering/TEST_STRATEGY.md), [operations](engineering/OPERATIONS.md), [dependencies](engineering/DEPENDENCIES.md), [security audit](engineering/SECURITY_AUDIT.md).
- Research: [context](research/RESEARCH_CONTEXT.md), [experiment](research/EXPERIMENT_DESIGN.md), [graph review](research/GRAPH_VALIDATION.md), [feedback evaluation](research/FEEDBACK_EVALUATION.md), [limitations](research/RESEARCH_LIMITATIONS.md).
- History: [baseline audit](audits/BASELINE_AUDIT.md), [timeline](history/IMPLEMENTATION_TIMELINE.md), [decisions](history/DECISION_LOG.md), [issues](history/ISSUE_LOG.md).
- Handoff: [remaining work](handoff/REMAINING_WORK.md), [human decisions](handoff/HUMAN_ACTION_REQUIRED.md), [legacy reuse](handoff/LEGACY_SYSTEM_INTEGRATION.md), [machine-readable verification](handoff/verification.json).

Local evidence is under `artifacts/phase2/` and intentionally absent from GitHub. Published summaries never substitute synthetic graph tests for real graph/extraction evidence. Earlier root-level documents are retained as Phase 1 records; their counts and blocked dependency findings describe that earlier state.
