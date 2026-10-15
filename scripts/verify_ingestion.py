"""Validate actual local chunk/profiling artifacts without exposing lecture text."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
parser.add_argument("--require-generation-guard", action="store_true")
args = parser.parse_args()
report = json.loads((args.directory / "profile.json").read_text())
chunks = [
    json.loads(line) for line in (args.directory / "chunks.jsonl").read_text().splitlines() if line
]
source = ROOT / "research/instructkg-jeffry"
assert report["status"] == "PASS" and report["generative_inference_calls"] == 0
assert not report["effective_settings"]["do_code_enrichment"]
assert not report["effective_settings"]["do_formula_enrichment"]
if args.require_generation_guard:
    assert report["blocked_generation_calls"] == 0 and report["generation_guard"]
assert (
    hashlib.sha256((source / "ingest.py").read_bytes()).hexdigest()
    == report["upstream_source_sha256"]
)
assert (
    hashlib.sha256((source / "data/sql/3-SQL2-JOINS_Nulls.pdf").read_bytes()).hexdigest()
    == report["input_pdf_sha256"]
)
assert len(chunks) == report["chunks"] and chunks
assert len({c["chunk_id"] for c in chunks}) == len(chunks)
for i, chunk in enumerate(chunks):
    assert chunk["chunk_index"] == i and chunk["text"].strip() and chunk["page_numbers"]
    assert all(1 <= p <= 17 for p in chunk["page_numbers"])
    assert chunk["prev_chunk_id"] == (chunks[i - 1]["chunk_id"] if i else None)
    assert chunk["next_chunk_id"] == (chunks[i + 1]["chunk_id"] if i + 1 < len(chunks) else None)
print(
    json.dumps(
        {
            "status": "PASS",
            "profile": report["profile"],
            "chunks": len(chunks),
            "cited_pages": len(report["pages"]),
            "wall_seconds": report["wall_seconds"],
            "generative_inference_calls": 0,
            "note": "Chunk provenance/links validated; semantic OCR quality still requires review.",
        },
        indent=2,
    )
)
