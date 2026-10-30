"""Run bounded synthetic inputs through pinned, unmodified Jeffry stages offline."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import pathlib
import sys

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
parser = argparse.ArgumentParser()
parser.add_argument(
    "--reference-root",
    type=pathlib.Path,
    required=True,
    help="Read-only extracted Jeffry snapshot containing UPSTREAM_SNAPSHOT.json",
)
parser.add_argument(
    "--output",
    type=pathlib.Path,
    default=pathlib.Path(__file__).resolve().parents[1] / "artifacts" / "phase4" / "legacy_stages",
)
parser.add_argument(
    "--model-path",
    type=pathlib.Path,
    default=pathlib.Path(
        os.environ.get("HF_HUB_CACHE", pathlib.Path.home() / ".cache" / "huggingface" / "hub")
    )
    / "models--sentence-transformers--all-MiniLM-L6-v2"
    / "snapshots"
    / "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
)
args = parser.parse_args()
source = args.reference_root.resolve()
out = args.output.resolve()
if out.exists() and any(out.iterdir()):
    parser.error("Preserve existing evidence: choose a fresh --output directory")
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(source))
import adapters
import clustering
import llm
import pairpackets

snapshot = json.loads((source / "UPSTREAM_SNAPSHOT.json").read_text())
assert snapshot["commit"] == "c34a7786528e78766f15d918ab17aca2a9f7dc0b"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


for name in (
    "llm.py",
    "pairpackets.py",
    "clustering.py",
    "adapters.py",
    "prompts.py",
    "response_parsing.py",
):
    assert sha(source / name) == snapshot["files"][name], name
model = args.model_path.resolve()
chunks = []
mentions = []
for i in range(24):
    group = i // 12
    topic = (
        "SQL joins combine rows from tables using matching keys"
        if group == 0
        else "SQL aggregation groups rows and computes counts and sums"
    )
    text = f"{topic}. Example lesson {i % 12}: " + (
        "join keys and matching records" if group == 0 else "group by and aggregate functions"
    )
    cid = f"lecture{group + 1}__{i:03}"
    chunks.append(
        {"chunk_id": cid, "lecture_id": f"lecture{group + 1}", "chunk_index": i, "text": text}
    )
    names = ["SQL joins", "matching keys"] if group == 0 else ["SQL aggregation", "group by"]
    for n, name in enumerate(names):
        mentions.append(
            {
                "concept_id": llm.concept_to_id(name),
                "concept": name,
                "lecture_id": f"lecture{group + 1}",
                "chunk_id": cid,
                "chunk_index": i,
                "page_numbers": [group + 1],
                "role": "definition" if n == 0 else "example",
                "snippet": text,
            }
        )
chunk_concepts = {
    c["chunk_id"]: [m["concept_id"] for m in mentions if m["chunk_id"] == c["chunk_id"]]
    for c in chunks
}
cards = llm.build_concept_cards(mentions, chunk_concepts)
assert llm.concept_to_id("  Left outer-join! ") == "LEFT_OUTER_JOIN"
assert (
    adapters._extract_user_text(
        [{"role": "user", "content": [{"type": "input_text", "text": "synthetic input"}]}]
    )
    == "synthetic input"
)
assert len(cards) == 4
inputs = {"chunks": chunks, "mentions": mentions}
(out / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
(out / "concept_cards.json").write_text(json.dumps(cards, indent=2) + "\n", encoding="utf-8")
result = {
    "source_commit": snapshot["commit"],
    "source_hashes": {
        n: sha(source / n)
        for n in (
            "llm.py",
            "pairpackets.py",
            "clustering.py",
            "adapters.py",
            "prompts.py",
            "response_parsing.py",
        )
    },
    "canonicalization": "PASS",
    "adapter_payload_helper": "PASS",
    "cards": len(cards),
    "model_snapshot": model.name,
    "model_files": {
        str(p.relative_to(model)): sha(p) for p in sorted(model.rglob("*")) if p.is_file()
    },
    "versions": {},
}
for package in (
    "sentence-transformers",
    "torch",
    "transformers",
    "numpy",
    "scikit-learn",
    "umap-learn",
    "hdbscan",
):
    try:
        result["versions"][package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        result["versions"][package] = "unavailable"
try:
    assert model.exists(), "model snapshot absent"
    # Upstream embed_texts constructs SentenceTransformer from this local path; offline mode prevents downloads.
    clusters = clustering.cluster_global_chunks(
        chunks=chunks,
        mentions=mentions,
        embedding_model=str(model),
        batch_size=32,
        normalize_embeddings=True,
        use_umap=True,
        umap_components=5,
        umap_neighbors=15,
        min_cluster_size=2,
        min_samples=None,
        top_terms=5,
        top_k_chunks_per_cluster=None,
    )
    embeddings = clustering.embed_texts([c["text"] for c in chunks], str(model), 32, True)
    import numpy as np

    np.save(out / "embeddings.npy", embeddings)
    result.update(
        clustering="PASS",
        embedding_shape=list(embeddings.shape),
        embedding_dtype=str(embeddings.dtype),
        clusters=len(clusters),
        embedding_consumer="UMAP cosine reduction, HDBSCAN and centroid representative ranking inside cluster_global_chunks",
    )
except Exception as exc:
    result.update(clustering="BLOCKED", clustering_error=f"{type(exc).__name__}: {exc}")
    clusters = []
(out / "context_clusters.json").write_text(json.dumps(clusters, indent=2) + "\n", encoding="utf-8")
# Without actual clusters, use an explicitly synthetic cluster to exercise the interface.
packet_clusters = clusters or [
    {
        "cluster_id": 0,
        "label_hint": "synthetic",
        "chunk_ids": [c["chunk_id"] for c in chunks],
        "concepts": sorted({m["concept_id"] for m in mentions}),
    }
]
(out / "packet_clusters.json").write_text(
    json.dumps(packet_clusters, indent=2) + "\n", encoding="utf-8"
)
packets = pairpackets.build_pairpackets(
    mentions=mentions, chunks=chunks, clusters=packet_clusters, progress_every=0
)
assert sum(p["chunk_co_occurrence"]["count"] == 12 for p in packets) == 2
if not clusters:
    assert len(packets) == 6
    assert sum(p["cluster_co_occurrence_with_different_chunks"]["count"] == 1 for p in packets) == 4
(out / "pairpackets.json").write_text(json.dumps(packets, indent=2) + "\n", encoding="utf-8")
result.update(
    pairpackets="PASS",
    packet_count=len(packets),
    packet_cluster_input="actual clustering output" if clusters else "synthetic interface input",
)
for p in sorted(list(out.glob("*.json")) + list(out.glob("*.npy"))):
    if p.name != "manifest.json":
        result.setdefault("artifact_sha256", {})[p.name] = sha(p)
(out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
