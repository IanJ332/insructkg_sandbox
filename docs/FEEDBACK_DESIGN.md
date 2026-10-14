# Feedback design and comparison

Correctness is always decided by deterministic execution against two independently initialized datasets. LLM output cannot alter score. `public_grade()` strips reference SQL, expected/actual rows and raw engine errors before constructing a model context. Query text is untrusted data, not an instruction source.

## Observed result, inferred gap, mastery

Observed errors describe execution: missing required rows, missing unmatched rows, a missed non-NULL unmatched reference, syntax/execution/unsupported query, or generic result mismatch. Candidate concepts are hypotheses attached only to semantic result failures, not proof of misunderstanding. Syntax and execution failures do not assert JOIN concept gaps. `diagnosis_confidence=null` because no calibrated probability is available. Longitudinal mastery is a separate profile heuristic.

## Three contexts

| Mode | Inputs |
|---|---|
| Baseline | Question, submitted SQL, safe deterministic status/observations |
| Lecture RAG | Baseline plus bounded page text from the actual JOIN/NULL PDF, page IDs and source provenance |
| KG | RAG plus explicit question-concept mapping, candidate diagnosis, bounded provisional prerequisites, student estimates when available, existing unreviewed research judgments/evidence |

The optional compatible provider uses the same model, temperature 0.1 and output budget 350 across all modes. Its HTTP timeout is eight seconds. Local feedback can be enabled in PL by environment configuration; default PL operation remains deterministic. The evaluation harness can exercise a configured local provider; no remote/paid CLI flag is enabled. Existing graph labels may be wrong, so the prompt prohibits claiming instructor approval. The development graph is also explicitly provisional.

The deterministic fallback has different context/evidence exposure by mode but is not LLM inference. KG fallback uses the actual provisional prerequisite neighborhood. RAG fallback adds a retrieved page reference; its generated text is still a rule template, not evidence of retrieval-conditioned model reasoning.

## Schema and output gate

Provider JSON must contain exactly feedback_text, candidate_concepts and evidence_references. Text is bounded to 10–900 characters; concepts must belong to the question's explicit vocabulary; citations must refer to supplied page IDs. The response cannot contain SQL SELECT, reference-table solution fragments, code fences, invented URLs, certain unsupported certainty/approval claims or conflicting instruction patterns. The application adds mode, model identifier, prompt version, latency, usage if provided, cost=null, inference status, validation status and sanitized exception class.

Malformed, leaking or timed-out responses fall back to deterministic feedback while preserving score. Logs distinguish deterministic_fallback, live_success and provider_error_fallback. A fake test provider is only a unit test and never counted as real inference. Credentials and provider response bodies are not copied into error logs.

This rule gate is deliberately conservative and imperfect. It can miss a complete solution expressed without SQL, fabricated prose without an explicit citation, or subtle pedagogical harm; it can also reject innocent use of the word SELECT. Passing the rule gate is not a human safety/quality certification. Human ratings remain necessary before teaching deployment.

## Evaluation run

`scripts/evaluate.py` pairs the same 21 fixture attempts with all three contexts and writes 63 inspectable contexts/outputs. `artifacts/FEEDBACK_COMPARISON.md` reports actual generated-output counts, schema/filter results, timing and **zero successful live calls** for the default run. Usage/cost remain null. Semantic grounding, specificity, concept relevance, diagnosis support and human leakage assessment are marked manual_review_pending. Reference presence alone is not evidence of good grounding.

No learning gains, treatment effects or student misconceptions are inferred from this synthetic technical evaluation. A future authorized study is described separately.
