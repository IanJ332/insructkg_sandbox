# Local KG extraction investigation and implementation

Verified October 19, 2026, America/Chicago. This report covers component behavior;
the main integration agent owns the final browser and release verification.

## What actually runs

`DemoKGRepository.generate_candidates(source_record)` retains its existing public
signature and persisted graph/review/version schema. The default remains
`SYNTHETIC_FIXTURE`. Set `SIIP_DEMO_KG_MODE=local` in the dashboard process to opt
into `LOCAL_LLM_ASSISTED_EXTRACTION`, using an already installed Ollama model
(`SIIP_LOCAL_KG_MODEL`, default `qwen3:8b`). Both modes explicitly report
`actual_instructkg_extraction: false`.

The new local adapter performs fresh inference on the uploaded, parsed source
text. It is not original InstructKG. It does not perform embedding clustering,
pair-packet construction or the upstream multistage concept/role/judgment pipeline.

The adapter divides the complete input into contiguous source passages. A
JSON-schema constrained model response selects passage IDs; the server copies
the original source passage and derives exact character offsets. No model-written
quote is accepted as source provenance. Labels must occur in the source and
their selected passage. Relations require existing distinct endpoints, both
endpoint labels in their evidence passage, supported relation vocabulary, a
bounded justification, finite confidence, and no duplicate or cycle within each
relation type. Explicit textual direction reversals are rejected. A `part_of`
justification must explain component/whole structure. These checks establish
traceability and basic structure, not semantic correctness. Instructor review is
still required; confidence is an uncalibrated model self-report.

Teaching order records the first accepted evidence passage's position in the
uploaded document, not a prerequisite inferred solely from sequence. Roles are
Definition, Example, Assumption or NA. `A depends_on B` means B is prerequisite
to A; `A part_of B` means A is a component of B. Directions are never silently
reversed or repaired.

Bounds: 12,000 source characters, 8 proposed concepts, 12 proposed relations,
2,400 generated tokens, 8,192 context tokens, 120-second HTTP timeout and
256,000 response bytes. Oversize input is rejected, never silently truncated.
The HTTP endpoint is fixed to `127.0.0.1:11434`; proxies and redirects are disabled.
No paid service, credentials, model download or model-invoked tools are used.

Invalid individual candidates are recorded with reasons. Failure, timeout,
malformed output, fewer than two valid concepts or no valid relations produces
an explicitly labeled synthetic fixture with `fallback_reason`. The requested
mode is retained separately. Cached drafts preserve instructor decisions;
retrying the same source reuses its draft, including a prior fallback. Upload a
new source version to request a new attempt. Graph identity includes document,
source version, course/module, source text hash, requested backend and model.

## Upstream and local prerequisites

A read-only `git ls-remote` query confirmed the public
[jeffry branch](https://github.com/code-royce/instructkg/tree/jeffry) exists at
`c34a7786528e78766f15d918ab17aca2a9f7dc0b`; `master` is
`ade6263a348984cef848eae85dc3d3b15daeea09`. No `main` ref was returned.

The pinned upstream
[README](https://github.com/code-royce/instructkg/blob/c34a7786528e78766f15d918ab17aca2a9f7dc0b/README.md),
[requirements](https://github.com/code-royce/instructkg/blob/c34a7786528e78766f15d918ab17aca2a9f7dc0b/requirements.txt),
`config.py`, `llm.py`, and `relation_judger.py` were inspected through GitHub's
public contents API. The original pipeline uses docling ingestion, concept and
role extraction, sentence embeddings, UMAP/HDBSCAN clustering, pair packets,
and relation judgment. Its local provider is vLLM (`vllm==0.19.1`), while API
adapters use a Responses-style interface. Ollama's generate API is not a drop-in
execution of this upstream framework.

The existing `D:\AI\SIIP\insructkg_sandbox` checkout was inspected read-only;
no `research/instructkg-jeffry` checkout was found there or in the assigned
worktree. The active shared Python environment has none of docling, dotenv,
pydantic, openai, anthropic, sentence_transformers, umap, hdbscan or vllm. The
original pipeline therefore remains `BLOCKED_EXTERNAL_DEPENDENCY` here. No heavy
dependencies or weights were installed. `scripts/extract.py` now gives a truthful
checkout/platform preflight and provides an explicit local-text CLI path.

## Actual inference evidence

The installed binary is `D:\AI\Tools\Ollama\ollama.exe`. A hidden `ollama serve`
process was started at 23:04:55 local time, PID 48056. The installed model is
`qwen3:8b`, 8.2B Q4_K_M, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
No model was downloaded. A warm-up returned `{"ready":true}` after about 59.8s
including initial model loading.

Early live probes exposed a reversed `part_of` candidate and model-altered
Markdown quotes. Those observations drove the explicit-direction checks,
trusted-passage binding and transparent rejection behavior. They were not
counted as pedagogically validated extractions.

The final CLI run processed the actual 2,916-character parsed synthetic lesson
`demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md`. It returned a genuine local draft
at `2026-10-20T04:13:48.899976Z` (October 19, 23:13:48 Chicago):

| Evidence | Observed result |
| --- | --- |
| Mode | LOCAL_LLM_ASSISTED_EXTRACTION |
| Graph | kg-48fd8b1e57146538 |
| Parsed text SHA-256 | 3530b7200c2b4a0eb304f15dd8ff5c8d8d727a21279d9defb4f9dae50fdd44b1 |
| Model response SHA-256 | 1777509e34c3d2960f9073932faff48893b3ecf7712da2e01bf9e3bf4194d3e4 |
| Inference duration | 11.371 seconds |
| Token counts | 1,219 input; 621 output |
| Valid concepts / relations | 5 / 3 |
| Rejected candidates | 1 concept, 2 relations |
| Source truncation / fallback | false / none |

Retained concepts were INNER_JOIN, JOIN_PREDICATE, LEFT_OUTER_JOIN,
MISSING_MATCHING_ROWS, and IS_NULL. NULL_SEMANTICS was rejected because its chosen
passage did not support its label. The missing-records `part_of` suggestion is
debatable and should receive instructor revision/rejection; successful inference
does not establish pedagogical correctness. This extractor cannot promise the
fixed SQL fixture concept set for arbitrary uploaded materials.

The complete persisted graph is in the assigned extraction worktree at
`artifacts/local-extraction-proof/kg-48fd8b1e57146538/draft.json`, with CLI output
`artifacts/local-extraction-proof-final.json`. These local generated artifacts
are intentionally untracked; the main agent can copy them into final evidence.

## Reproduction and integration

```powershell
$env:SIIP_DEMO_KG_MODE = 'local'
python scripts/extract.py --local-text demo_materials/SYNTHETIC_SQL_JOINS_LESSON.md --output-dir artifacts/local-kg
python -m unittest discover -s tests -p 'test_*kg*.py' -v
```

The dashboard must display `graph.scientific_boundary`, `extraction_mode`, and
any `fallback_reason`, and derive extraction/review event `source_type` from the
graph. Do not keep its old hard-coded synthetic-only explanation when local
inference succeeds. The graph also retains original `registered_content_hash`,
parsed text hash, `source_version`, `course_id`, and `module_id` for lineage.
Review supports APPROVE, REJECT and NEEDS_REVISION; saved snapshots are immutable.
Only instructor-approved saved edges should ground student feedback.

Component verification: 37 KG/schema unit tests passed using the root `.venv`
Python, with isolated temporary directories and no shared demo database mutation.
Ruff lint and formatting checks passed on all owned Python files. Final release,
browser workflow and recording remain the main integration agent's verification.
