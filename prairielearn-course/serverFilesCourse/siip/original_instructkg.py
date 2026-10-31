"""Pinned original InstructKG chunk-only subprocess integration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .configuration import LOCAL_HOSTS
from .identity import is_instructor_principal

COMMIT = "c34a7786528e78766f15d918ab17aca2a9f7dc0b"
MODE = "ORIGINAL_INSTRUCTKG_CHUNK_ONLY"
PIPELINE_VERSION = "original-instructkg-jeffry-chunk-only-v2"
EXTRACTION_METHOD = "original_instructkg_chunk_only"
BOUNDARY = "Original InstructKG chunk-based integration; embedding and clustering deferred."
HASHES = {
    "adapters.py": "53073f42d0e628d96e04e6759a940bd1b2798829bad39f9014641780321010ae",
    "clustering.py": "0b7d18f2a5bf8a7b2914abfdcf903cd360f3a3c2ca4032b587ee622eee47d4d0",
    "config.py": "01414bcf6137b1c2c93999562b317202a63b83073759960ec1d01ea57f5afd59",
    "ingest.py": "04c176fd35e9882aff47f139df2d13780cde13aedd69dbd94f45678577b770fa",
    "llm.py": "37fa755ab33d9c43f352c28c67b9c02925512b4f1c887b37ca7dd974134aaf6f",
    "main.py": "7ea3d3b7747fc126fec239067685abb82cc40ab9d3d97c2522ae9c6add828e54",
    "pairpackets.py": "b6152dfe5d6f30bbebdfb5c42e51458d1f6ee8e287079821c1259850f645da0b",
    "prompts.py": "ff6583f153a0e247c8b8bb892480d7d64400b6525ace50446a1acccf5aa1f47d",
    "relation_judger.py": "12ded1c1587ea8042e89a0c8d3c588260fddf286a5a3295e9451994882be0500",
    "response_parsing.py": "a47e6017b42c7f4195e64ad10c22ffa603d50cd6dcd17031b45795017b2dbf5b",
}


class OriginalPipelineError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_source():
    value = os.environ.get("SIIP_INSTRUCTKG_SOURCE_DIR")
    if not value:
        raise OriginalPipelineError(
            "SIIP_INSTRUCTKG_SOURCE_DIR must name the pinned external snapshot"
        )
    source = Path(value).resolve()
    for name, expected in HASHES.items():
        if sha(source / name) != expected:
            raise OriginalPipelineError(f"Original source integrity mismatch: {name}")
    return source


def read_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path, rows):
    Path(path).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def instructional_chunks(chunks, chunk_items, document_items, exclusions):
    """Drop only whole chunks whose every item has an explicit hash-bound review."""
    if not isinstance(exclusions, list) or len(exclusions) > 64:
        raise OriginalPipelineError("Invalid reviewed document exclusions")
    reviewed = set()
    for entry in exclusions:
        ref = entry.get("item_ref") if isinstance(entry, dict) else None
        item = document_items.get(ref) if isinstance(ref, str) else None
        if (
            not item
            or not isinstance(item.get("text"), str)
            or entry.get("text_sha256") != hashlib.sha256(item["text"].encode()).hexdigest()
            or not is_instructor_principal(entry.get("reviewed_by"))
            or not isinstance(entry.get("reason"), str)
            or not entry["reason"].strip()
        ):
            raise OriginalPipelineError(
                "Document exclusion requires matching item and instructor review"
            )
        reviewed.add(ref)
    selected, excluded, mixed = [], [], []
    for chunk, refs in zip(chunks, chunk_items, strict=True):
        refs = set(refs)
        if refs and refs.issubset(reviewed):
            excluded.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "item_refs": sorted(refs),
                    "page_numbers": chunk.get("page_numbers", []),
                }
            )
        else:
            selected.append(chunk)
            if refs & reviewed:
                mixed.append(chunk["chunk_id"])
    if not selected:
        raise OriginalPipelineError("No instructional chunks remain")
    return selected, {
        "reviewed_exclusions": exclusions,
        "excluded_chunks": excluded,
        "mixed_chunks_retained": mixed,
        "policy": "No vocabulary filtering; mixed or unreviewed content is retained.",
    }


def directional_pairpackets(module, chunks, mentions):
    """Let upstream recompute directional evidence in two independent orientations."""
    forward = module.build_pairpackets(chunks=chunks, mentions=mentions, clusters=[])
    original = module._cooc_counts
    try:
        module._cooc_counts = lambda index: {(b, a): n for (a, b), n in original(index).items()}
        reverse = module.build_pairpackets(chunks=chunks, mentions=mentions, clusters=[])
    finally:
        module._cooc_counts = original
    if {tuple(p["pair"]) for p in reverse} != {tuple(reversed(p["pair"])) for p in forward}:
        raise OriginalPipelineError("Directional PairPacket parity mismatch")
    return forward, reverse


def validate_relation_responses(responses, parser):
    """Reject malformed decisions before the upstream normalizer can turn them into null."""
    for response in responses:
        try:
            decision = parser(response)
        except (ValueError, TypeError) as exc:
            raise OriginalPipelineError("Invalid original relation response") from exc
        if not isinstance(decision, dict) or "relation" not in decision:
            raise OriginalPipelineError("Original relation response missing relation")
        relation = decision["relation"]
        if relation is None:
            continue
        if not isinstance(relation, str):
            raise OriginalPipelineError("Invalid original relation label")
        label = relation.strip().lower()
        if label not in ("null", "none") and label.replace("-", "_").replace(" ", "_") not in (
            "depends_on",
            "part_of",
        ):
            raise OriginalPipelineError("Invalid original relation label")


def generate(source_record, artifact_dir):
    _source = verified_source()
    pdf = Path(source_record.get("source_path", "")).resolve()
    if not pdf.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
        raise OriginalPipelineError("Original mode requires a genuine PDF source_path")
    source_hash = sha(pdf)
    if source_hash != source_record.get("content_hash"):
        raise OriginalPipelineError("Original PDF hash does not match registry")
    base = Path(artifact_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    (target / "input_policy.json").write_text(
        json.dumps(
            {
                "source_sha256": source_hash,
                "content_exclusions": (source_record.get("pdf_provenance") or {}).get(
                    "content_exclusions", []
                ),
            }
        ),
        encoding="utf-8",
    )
    runtime = os.environ.get("SIIP_INSTRUCTKG_PYTHON")
    if not runtime:
        raise OriginalPipelineError(
            "SIIP_INSTRUCTKG_PYTHON must name the external heavy-runtime Python"
        )
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONUNBUFFERED="1",
    )
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    try:
        proc = subprocess.run(
            [runtime, "-m", "siip.original_instructkg", str(pdf), str(target)],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OriginalPipelineError(f"Original pipeline failed: {exc}") from exc
    (target / "worker.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise OriginalPipelineError(
            f"Original pipeline failed (exit {proc.returncode}); see {target / 'worker.log'}"
        )
    result = json.loads((target / "result.json").read_text(encoding="utf-8"))
    if result["source_sha256"] != source_hash:
        raise OriginalPipelineError("Worker source identity mismatch")
    result["extraction_metadata"]["source_sha256"] = source_hash
    return result


class OllamaResponses:
    def __init__(self, output):
        base_url = os.environ.get("SIIP_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in LOCAL_HOSTS
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise OriginalPipelineError(
                "Original model transport requires a local Ollama HTTP endpoint"
            )
        self.url = base_url + "/api/chat"

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        self.opener = build_opener(NoRedirect())
        self.output = output
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(2)

    async def create(self, *, model, instructions, input, **kwargs):
        batches = input if input and isinstance(input[0], list) else [input]

        async def one(messages):
            async with self.semaphore:
                chat = [{"role": "system", "content": instructions}] if instructions else []
                for message in messages:
                    content = message.get("content", "")
                    if isinstance(content, list):
                        content = "\n".join(str(c.get("text", "")) for c in content)
                    chat.append({"role": message.get("role", "user"), "content": content})
                payload = {
                    "model": model,
                    "messages": chat,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0, "num_predict": 2400, "num_ctx": 8192},
                }

                def call():
                    req = Request(
                        self.url,
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with self.opener.open(req, timeout=120) as response:
                        return json.loads(response.read().decode("utf-8"))

                try:
                    response = await asyncio.to_thread(call)
                except Exception as exc:
                    async with self.lock:
                        with self.output.open("a", encoding="utf-8") as f:
                            f.write(
                                json.dumps(
                                    {"request": payload, "error": str(exc)}, ensure_ascii=False
                                )
                                + "\n"
                            )
                    raise
                async with self.lock:
                    with self.output.open("a", encoding="utf-8") as f:
                        f.write(
                            json.dumps(
                                {"request": payload, "response": response}, ensure_ascii=False
                            )
                            + "\n"
                        )
                return response["message"]["content"]

        texts = await asyncio.gather(*(one(batch) for batch in batches))
        return SimpleNamespace(output_texts=texts, output_text=texts[0] if texts else "")


async def worker(pdf, target):
    source = verified_source()
    sys.path.insert(0, str(source))
    os.environ["LLM_PROVIDER"] = "local"
    os.environ["OUT_DIR"] = str(target)
    import ingest
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

    original_options = ingest.PdfPipelineOptions

    def options(**kwargs):
        kwargs.update(
            do_code_enrichment=False,
            do_formula_enrichment=False,
            do_ocr=False,
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=2),
            enable_remote_services=False,
            document_timeout=180,
        )
        return original_options(**kwargs)

    ingest.PdfPipelineOptions = options
    policy = json.loads((target / "input_policy.json").read_text(encoding="utf-8"))
    if policy["source_sha256"] != sha(pdf):
        raise OriginalPipelineError("Content policy source mismatch")
    original_converter, original_chunker = ingest.DocumentConverter, ingest.HybridChunker
    document_items, chunk_items = {}, []

    class CapturingConverter:
        def __init__(self, **kwargs):
            self.converter = original_converter(**kwargs)

        def convert(self, path):
            result = self.converter.convert(path)
            document = result.document.export_to_dict()
            (target / "docling_document.json").write_text(
                json.dumps(document, indent=2), encoding="utf-8"
            )
            document_items.update({item["self_ref"]: item for item in document.get("texts", [])})
            return result

    class CapturingChunker:
        def __init__(self, **kwargs):
            self.chunker = original_chunker(**kwargs)

        def chunk(self, *, dl_doc):
            for chunk in self.chunker.chunk(dl_doc=dl_doc):
                chunk_items.append([item.self_ref for item in (chunk.meta.doc_items or [])])
                yield chunk

    ingest.DocumentConverter, ingest.HybridChunker = CapturingConverter, CapturingChunker
    import llm

    client = SimpleNamespace(responses=OllamaResponses(target / "model_calls.jsonl"))
    llm.get_llm_client = lambda: client
    import adapters
    import main

    adapters.get_llm_client = lambda: client
    import relation_judger

    relation_judger._LLM_CLIENT = client
    original_relation_batch = relation_judger._call_llm_batch

    async def checked_relation_batch(prompts, *, model):
        responses = await original_relation_batch(prompts, model=model)
        if len(responses) != len(prompts):
            raise OriginalPipelineError("Original relation response count mismatch")
        validate_relation_responses(responses, relation_judger._parse_llm_json)
        return responses

    relation_judger._call_llm_batch = checked_relation_batch
    import pairpackets

    model = os.environ.get("SIIP_LOCAL_KG_MODEL", "qwen3:8b")
    # Retain a stable, original lecture filename without exposing the registry path.
    with tempfile.TemporaryDirectory(dir=target) as temp:
        staged = Path(temp) / "lecture_text.pdf"
        shutil.copyfile(pdf, staged)
        chunks_path = Path(
            ingest.ingest_pdfs([str(staged)], out_name="chunks_original.jsonl", out_dir=str(target))
        )
    original_chunks = read_jsonl(chunks_path)
    chunks, content_selection = instructional_chunks(
        original_chunks, chunk_items, document_items, policy["content_exclusions"]
    )
    (target / "content_selection.json").write_text(
        json.dumps(content_selection, indent=2), encoding="utf-8"
    )
    (target / "chunk_items.json").write_text(json.dumps(chunk_items, indent=2), encoding="utf-8")
    chunks_path = target / "chunks.jsonl"
    write_jsonl(chunks_path, chunks)
    if not chunks:
        raise OriginalPipelineError("Original ingestion produced no chunks")
    mentions, cards = await main.run_llm_and_cards(
        chunks_path=str(chunks_path),
        mentions_out=str(target / "mentions.jsonl"),
        concept_cards_out=str(target / "concept_cards.jsonl"),
        model=model,
    )
    forward, reverse = directional_pairpackets(pairpackets, chunks, mentions)
    packets = forward + reverse
    write_jsonl(target / "pairpackets.jsonl", packets)
    (target / "clusters.json").write_text("[]\n", encoding="utf-8")
    relations = []
    for orientation, batch in (("forward", forward), ("reverse", reverse)):
        packet_path, relation_path = (
            target / f"pairpackets_{orientation}.jsonl",
            target / f"relations_{orientation}.jsonl",
        )
        write_jsonl(packet_path, batch)
        relation_path.write_text("", encoding="utf-8")
        await relation_judger.judge_pairpackets_file(
            str(packet_path), out_path=str(relation_path), model=model, concurrency=2, batch_size=8
        )
        judged = read_jsonl(relation_path)
        if len(judged) != len(batch):
            raise OriginalPipelineError("Original directional judgment count mismatch")
        relations.extend(judged)
    write_jsonl(target / "relations.jsonl", relations)
    if (target / "model_calls.jsonl").exists() and any(
        x.get("error") for x in read_jsonl(target / "model_calls.jsonl")
    ):
        raise OriginalPipelineError("Original model transport failed; see model_calls.jsonl")
    if len(relations) != len(packets):
        raise OriginalPipelineError("Original relation output count does not match candidate pairs")
    if any(r.get("_meta", {}).get("_error") for r in relations):
        raise OriginalPipelineError("Original relation judgment returned invalid model output")
    names = {c["concept_id"] for c in cards}
    chunk_index = {c["chunk_id"]: c for c in chunks}
    nodes = [
        {"id": c["concept_id"], "label": c["concept_label"], "original_card": c} for c in cards
    ]
    edges = []
    for r in relations:
        a, b, relation = r["A"]["name"], r["B"]["name"], r.get("relation")
        if relation is None:
            continue
        if a not in names or b not in names or relation not in ("depends_on", "part_of"):
            raise OriginalPipelineError(
                "Original relation references an unknown concept or relation"
            )
        evidence = [
            dict(
                e,
                page_numbers=chunk_index.get(e.get("chunk_id"), {}).get("page_numbers", []),
                prev_chunk_id=chunk_index.get(e.get("chunk_id"), {}).get("prev_chunk_id"),
                next_chunk_id=chunk_index.get(e.get("chunk_id"), {}).get("next_chunk_id"),
            )
            for e in (r.get("evidence_chunks") or [])
        ]
        edges.append(
            {
                "source": a,
                "target": b,
                "relation": relation,
                "evidence_excerpt": str(evidence[0].get("text", "")) if evidence else "",
                "original_relation": r,
                "evidence_chunks": evidence,
            }
        )
    calls = target / "model_calls.jsonl"
    if not calls.exists():
        calls.write_text("", encoding="utf-8")
    files = [
        "input_policy.json",
        "docling_document.json",
        "chunk_items.json",
        "chunks_original.jsonl",
        "content_selection.json",
        "pairpackets_forward.jsonl",
        "pairpackets_reverse.jsonl",
        "relations_forward.jsonl",
        "relations_reverse.jsonl",
        "chunks.jsonl",
        "mentions.jsonl",
        "concept_cards.jsonl",
        "clusters.json",
        "pairpackets.jsonl",
        "relations.jsonl",
        "model_calls.jsonl",
    ]
    artifacts = {n: {"path": str(target / n), "sha256": sha(target / n)} for n in files}
    metadata = {
        "source_sha256": sha(pdf),
        "status": "completed",
        "upstream_repository": "https://github.com/code-royce/instructkg",
        "upstream_commit": COMMIT,
        "source_file_sha256": HASHES,
        "requested_model": model,
        "actual_models": sorted(
            {x.get("response", {}).get("model", "") for x in read_jsonl(calls) if x.get("response")}
        ),
        "functions": [
            "ingest.ingest_pdfs",
            "ingest.pdf_to_chunks",
            "main.run_llm_and_cards",
            "llm.extract_concepts_llm_batch",
            "llm.classify_concept_role_llm_batch_texts",
            "llm.concept_to_id",
            "llm.build_concept_cards",
            "pairpackets.build_pairpackets",
            "relation_judger.judge_pairpackets_file",
            "relation_judger.judge_pairpacket_batch",
        ],
        "artifacts": artifacts,
        "counts": {
            "original_chunks": len(original_chunks),
            "unordered_candidate_pairs": len(forward),
            "chunks": len(chunks),
            "mentions": len(mentions),
            "concepts": len(cards),
            "candidate_pairs": len(packets),
            "judged_relationships": len(relations),
        },
        "clustering": "DEFERRED",
        "content_selection": content_selection,
        "direction_policy": "Original functions recompute forward/reverse packets; separate file judger calls avoid unordered dedup; every non-null remains an unreviewed directed candidate.",
        "fallback": False,
        "adapter_configuration": {
            "ocr": "disabled (native PDF text)",
            "formula_enrichment": False,
            "code_enrichment": False,
            "model_transport": "Ollama native chat; think=false",
            "temperature": 0,
            "max_tokens": 2400,
            "context": 8192,
            "request_timeout_seconds": 120,
            "concurrency": 2,
        },
    }
    result = {
        "nodes": nodes,
        "edges": edges,
        "extracted_text": "\n\n".join(c["text"] for c in chunks if c.get("text")),
        "extracted_chunks": chunks,
        "source_sha256": sha(pdf),
        "extraction_metadata": metadata,
        "rejected_candidates": [],
    }
    (target / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(worker(Path(sys.argv[1]), Path(sys.argv[2])))
