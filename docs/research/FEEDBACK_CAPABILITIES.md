# Feedback capability claims and evidence

These are separate capabilities, not interchangeable labels:

| Capability | What it means | Current implemented/verified behavior |
|---|---|---|
| Question-specific | Uses current question, SQL and deterministic execution observations | PASS in actual PL UI and deterministic tests |
| Concept-aware | Maps observed outcomes to explicitly configured candidate concepts | PASS mechanically; mappings/diagnosis are hypotheses, not validated knowledge of a learner |
| KG-grounded | A response is supported by identified graph relationships and source evidence | KG context/provisional prerequisite hints are implemented; original graph is unreviewed; semantic grounding/instructor alignment is NOT established |
| Historically personalized | Prior subject-specific evidence changes feedback for the same current attempt | PASS for the local post-submission synthetic service: contrasting histories produce different rule feedback and minimized provider contexts |

The immediate PL hook remains history-free. It neither knows a trusted student identity nor invokes the post-submission principal service. Do not call it historically personalized. The API synchronizer is contract/mock verified; actual authenticated PL API polling and hosted learner delivery remain unverified. The actual PL browser E2E uses supported CSV import.

The deterministic history sentence uses prior-only Beta heuristic evidence and explicitly qualifies uncertainty. It is not an LLM inference result or a validated pedagogical improvement. Mocked provider transport success is not a live model experiment. All actual feedback/model inference remains BLOCKED.

KG context includes preserved original judgments and separately labeled developer provisional edges. Unreviewed relationships are never instructor-aligned ground truth. Citation presence or an available graph context is not proof that a generated response is supported by an edge. Instructor review, evidence-level human ratings and a controlled study remain necessary. Existing source provenance and new CPU chunks remain separate; no new relations or approved curriculum are fabricated.
