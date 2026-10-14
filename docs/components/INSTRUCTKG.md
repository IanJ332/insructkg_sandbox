# InstructKG component

The primary upstream remains unmodified Jeffry c34a7786528e78766f15d918ab17aca2a9f7dc0b; reference ade6263a348984cef848eae85dc3d3b15daeea09 is for audit only. Bootstrap retrieves pinned checkouts into ignored research/. No research implementation is vendored into the public integration package.

`graph.py` consumes actual A/B/name/role/relation/evidence/_meta JSONL, preserves raw direction, checksum/line IDs and review overlays, detects duplicates/null/invalid records, and bounds prerequisite traversal. Phase 2 handles non-object records, identifier inconsistency and valid overlay endpoints that appear later in a file. Missing evidence is a review warning; unreviewed edges are not silently approved.

Local Mode A independently verifies 469 judgments, 319 non-null/150 null and 121 nodes; two explicit research tests cover provenance/direction. Public CI has a different clearly synthetic contract graph, not an imitation extraction result. Eight developer provisional edges remain separate from original judgments; no instructor approval is claimed.

Mode B uses the actual upstream main.py. A locked Python 3.11 Linux CPU/API image isolates the Mac torch-wheel incompatibility without changing OCR/chunking/extraction algorithms. It excludes vLLM. Actual import/ingestion and remaining stage statuses are recorded in the handoff and local extraction logs; no concept/relation run is claimed without model resources. See dependencies and graph-validation docs.
