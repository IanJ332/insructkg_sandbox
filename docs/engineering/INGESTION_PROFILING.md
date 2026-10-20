# Actual Docling ingestion profiling

The pinned upstream `ingest.py` enables code/formula enrichment with CodeFormulaV2, a generative VLM. The accepted Phase2 original-settings run timed out after 600seconds with no chunks. That failure remains historical evidence. This phase does **not** rerun generative enrichment or concept/role/relation inference.

`scripts/profile_ingestion.py` imports the actual upstream ingestion module, injects a named CPU configuration externally and calls its original `pdf_to_chunks`/`write_jsonl`/HybridChunker. Source files, natural-order/chunk IDs, max_tokens 8191, merge_peers and neighboring/page provenance remain upstream behavior. Configuration differs explicitly: formula/code/picture/chart enrichment and remote services are disabled; CPU/two threads; native extraction or Tesseract bitmap OCR. This is a documented non-generative variant, not a claim that original settings completed.

The final Tesseract run asserts enrichment flags before model initialization and replaces Transformers GenerationMixin.generate with a raising guard. Its report records **zero blocked generation attempts and zero completed generative calls**. Importing neural layout/table parsing models and non-generative OCR is separate from LLM inference.

| Actual run | Wall time | Imports | Model initialization | OCR | Layout | Table | Chunking | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Native, OCR off |163.01s|23.81s|11.21s|no-op|99.79s|68.71s|0.19s|13 chunks;13 cited pages;2,852chars |
| Guarded Tesseract |268.25s|50.57s|19.01s|157.76s|110.68s|72.28s|0.42s|13 chunks;16 cited pages;8,303chars |

Stage active times instrument worker-thread iterator work and may overlap; **do not sum them**. cProfile separately covers main-thread imports/calls. Page backends loaded all 17 pages; citation coverage differs. Native backend text access was 0.71s (native) /0.63s (guarded Tesseract). The 17-page PDF contains 3,545 pypdf-extracted native characters, a different extraction representation rather than a quality gold standard. The first unguarded-but-enrichment-disabled Tesseract comparison completed in 130.24s; different cache/load conditions prohibit a speed conclusion.

Interpretation: the compatible non-generative path is not stuck in chunk generation or suffering a general parse failure. Layout/table inference and, when enabled, OCR dominate this run; import/model startup is material but smaller. The previous 600s original-settings timeout reached generative/OCR initialization; **its exact internal attribution remains unproven** because it was not instrumented and generative execution is forbidden. Do not assert that a single flag definitively caused that historical timeout.

```sh
docker build -f infrastructure/Dockerfile.extraction -t siip-extraction-cpu:phase2 .
.venv/bin/python scripts/extraction_cpu.py ingest --profile native
.venv/bin/python scripts/extraction_cpu.py ingest --profile tesseract
.venv/bin/python scripts/verify_ingestion.py artifacts/followup/ingest-tesseract --require-generation-guard
```

The wrapper uses 2 CPUs / 5 GiB, a 480s process bound and 300s document bound; logs/outputs/cache stay ignored. It mounts upstream read-only. Verification checks input/source hashes, chunk IDs/counts, text, valid page citations and exact neighboring links. Reports store profiler/input/upstream hashes and stage timings. Do not overwrite an experiment output directory when comparing configurations; this phase preserved the first comparison separately.

The generated chunks are **not automatically installed as the RAG corpus**, promoted to approved curriculum or represented as a new KG. Page 6 is absent from the Tesseract chunk citations; OCR/table correctness and coverage require human review. Concepts, roles, clusters, pairs and relations remain NOT_RUN/BLOCKED. Formula/code enrichment timing is intentionally NOT_RUN, not a zero-cost success.
