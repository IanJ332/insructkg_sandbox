# Graph validation and instructor review

Mode A loads actual Jeffry `out/relations_sql_qwen14b.jsonl`: 469 judgments, 247 depends_on, 72 part_of, 150 null, 121 nodes, no duplicate records in the baseline audit. Nine records are flagged for review. Original judgments remain unreviewed; eight original-to-this-integration developer provisional dependencies are separate and not an extracted KG.

Preserve raw A/B endpoint objects, roles, relation direction, evidence chunks, justifications, metadata, source checksum and line identity. Do not reverse a relation merely because its explanation looks contradictory. Example: JOIN_OPERATION part_of LEFT_OUTER_JOIN is retained and flagged; an instructor must assess composition direction against source material. Explicit aliases address missing exact INNER_JOIN/NULL names without inventing extraction provenance.

Review queue/overlay supports approve, reject and modify with reviewer/reason. Modified endpoints must belong to known nodes; Phase 2 fixed false rejection of endpoints appearing later in a file. Review cycles, role/identifier consistency, contradictory direction, missing/unknown evidence, null-with-error versus true null and exact node mappings. Preserve historical decisions and separate overlay from original records. UI is local synthetic tooling, not an authenticated multi-instructor approval system.

Mode B ran the real upstream CLI in a compatible CPU image: import passed, ingestion timed out at 600 seconds and wrote no chunks; no concepts/roles/clusters/pairs/relations were generated. Full generative stages remain blocked. Existing historical graph counts cannot be used as fresh-run counts. A future successful run must record PDF checksum/pages, every stage count/runtime/error/model setting and compare meaningful coverage rather than require an arbitrary large graph.

The single available 17-page JOIN/NULL PDF covers less than the multi-lecture historical graph. Published upstream notes record small retained concept sets after minimum-three-chunk filtering; do not conclude pipeline failure from a small graph alone. Known orphan-card and OCR enrichment risks need review before promoting new results.
