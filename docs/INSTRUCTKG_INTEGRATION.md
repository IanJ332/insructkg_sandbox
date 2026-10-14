> Phase 1 historical record. For current Phase 2 status, see [CURRENT_STATUS](handoff/CURRENT_STATUS.md). Counts and blockers below describe the earlier snapshot.

# InstructKG integration and provenance

## Existing output verified

The selected implementation is the untouched Jeffry checkout at c34a7786528e78766f15d918ab17aca2a9f7dc0b. Original reference checkout ade6263a348984cef848eae85dc3d3b15daeea09 is retained for comparison only. `scripts/bootstrap.py` pins detached revisions. `artifacts/input_manifest.json` records commits and SHA256s.

The actual SQL output has 469 judgments: 247 depends_on, 72 part_of, 150 null; 121 named nodes. It contains evidence from multiple SQL lectures. `3-SQL2-JOINS_Nulls.pdf` is only the supplied real initial module PDF, not the source of all those records. `scripts/prepare.py` copies the graph bytes unchanged into server-only course data. `scripts/graph_audit.py` creates an inspectable queue with original evidence and nine flagged records (including missing evidence and the questioned composition).

## Adapter contract

`ConceptGraph` parses original A/B objects, role names, relation, justification, evidence_chunks and _meta. It preserves raw source records, original direction, file checksum, line number, commit attribution and source scope. Null labels are preserved; unsupported labels/malformed records are reported separately. `_meta._error` marks invalid inference and cannot become a usable edge. Nodes are deduplicated by original name while retaining role variations. Edge duplicates are reported and deduplicated only in the query view; original records remain.

A depends_on B means B is a prerequisite of A. A part_of B means A is a component of B. No reverse-direction inference is performed. The known `JOIN_OPERATION part_of LEFT_OUTER_JOIN` remains untouched and unreviewed. Its justification describes the broader JOIN concept containing the narrower join type, so the queue specifically requests direction review.

Review overlays support unreviewed/accepted/rejected/modified. Modified edges require reviewer, reason and explicit replacement source/target/relation; the raw direction remains available. No reviewer has approved any original edge. By default `edges()` returns only accepted or modified edges; `edges(True)` explicitly includes unreviewed model judgments. Bounded prerequisite traversal is limited to depth four and excludes cycles back to the starting node.

## Teaching graph and mapping

Eight separate developer provisional dependencies cover INNER_JOIN, JOIN_CONDITION, LEFT_OUTER_JOIN, UNMATCHED_ROWS, NULL_SEMANTICS, IS_NULL, FILTERING_AFTER_JOIN, SQL_SELECT and RELATIONAL_TABLES. These are development annotations, not extraction results or instructor-approved truth. `mapping.json` records question associations, developer review status and the explicit INNER_JOIN → JOIN_OPERATION alias. Exact concepts absent from the original graph are never silently claimed to exist there.

KG contexts contain actual lecture-page evidence, candidate diagnosis, student estimates when supplied, provisional prerequisites and explicitly unreviewed existing judgments. Those research judgments carry evidence but are not authoritative instructions. The student feedback labels graph status, and the dashboard lets reviewers inspect every original record, direction and justification.

## Real lecture retrieval

Seventeen PDF pages have extractable native text. Page IDs, original path, repository commit and PDF checksum are stored. This lightweight lexical page retrieval is a RAG baseline, not the upstream Docling/LLM extractor. Complex PDF tables may lose layout in native text. Do not describe text extraction as fresh KG generation.

## Fresh extraction status: BLOCKED

No fresh InstructKG LLM pipeline run is claimed. This host has no CUDA GPU; no OpenAI key/authorized model usage was available. A real `pip install --dry-run -r infrastructure/requirements-pipeline.txt` also failed because no suitable torch distribution exists for this Intel macOS Python 3.13 combination. Evidence: `artifacts/pipeline-dependency-check.log`, `artifacts/fresh_extraction_status.json`.

The upstream implementation remains the pipeline:

1. Docling/OCR and HybridChunker → chunks.jsonl.
2. LLM concepts + pedagogical role tagging → mentions.jsonl and concept_cards.jsonl.
3. Embedding/UMAP/HDBSCAN → context_clusters.jsonl.
4. Chunk/cluster evidence pairing → pairpackets.jsonl.
5. Actual relation judgment → relations.jsonl.

Use a supported isolated environment (or an approved Linux inference machine), install `infrastructure/requirements-pipeline.txt`, configure an approved provider and model, and run `scripts/extract.py --run --authorized-model-usage` **only after authorization for that usage**. The wrapper invokes original main.py and records intermediate line counts and exit status. The optional GPU stack stays separate and preserves vllm==0.19.1. No stubbed extraction client is used.

Do not fabricate output if extraction fails. Known upstream issues include orphan concept cards after filtering, temporal lexicographic ordering, OCR/enrichment corruption risks, and sparse graphs from the one-PDF min_unique_chunks filter. Historical SQL runs in testing_cmds.md yielded 13 chunks, two retained concepts and one relation; that is historical evidence, not a new result.

## Explicit review overlay command

`scripts/review_graph.py RECORD_ID` displays a single original record. With `--status`, `--reviewer` and `--reason`, it writes a separate reviews.json overlay; modified decisions also need --source, --target and --relation. Use it only to record an actual review decision. No review decisions were entered during this build. `load_graphs()` consumes the overlay and supplies accepted/modified relationships separately from unreviewed observations.
