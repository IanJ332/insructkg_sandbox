# Feedback evaluation

`scripts/evaluate.py` pairs the same 21 synthetic attempts across Baseline/RAG/KG: **63 outputs**, with deterministic grades fixed. Default execution uses deterministic fallback and makes zero inference calls. Contract tests separately use a local fake provider. Neither result establishes live provider quality, comparative LLM effectiveness or learning impact.

The implemented retriever scores terms over page-cited real document text, includes observed SQL/error terms, bounds excerpts and records references. Baseline omits these. KG adds explicitly unreviewed/provisional relation evidence and prior mastery context. Public tests use a differently labeled synthetic lesson. Original local PDF provenance remains ignored, not published as a fixture.

Structured results record mode/model/prompt v2, text, concepts, evidence references, inference/fallback status, rule validation, latency and provider token usage when present. Cost is null without observed authorized pricing assumptions. Failed/invalid model output falls back and never changes deterministic score. Automatic checks measure JSON/shape/reference membership/obvious leakage only. Context-construction time in deterministic runs is not an inference benchmark.

Human rubric (pending): factual accuracy against grade evidence; useful next-step hint; concept specificity; cited excerpt actually supporting the statement; instructor alignment; hidden-answer leakage; consistency across equivalent attempts. Use blinded raters and retain disagreement/error examples. Prompt-injection and oblique answer leakage need adversarial semantic review beyond the existing lexical filters.

Live Baseline/RAG/KG verification is BLOCKED by the user's explicit no-inference/no-paid instruction. Do not configure or call a provider until that instruction changes. Then freeze model/settings, log sanitized usage/status, bound the evaluation batch and record all failures and denominators.
