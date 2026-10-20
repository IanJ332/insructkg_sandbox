"""Original InstructKG preflight, or explicitly requested bounded local extraction.

Example: python scripts/extract.py --local-text lecture.md --output-dir artifacts/local-kg
The local path uses Ollama only and is not original InstructKG.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--local-text", type=Path, help="Extract candidates from UTF-8 TXT/Markdown using local Ollama"
)
parser.add_argument("--source-id", help="Source-document identifier for local text extraction")
parser.add_argument("--output-dir", type=Path, help="Local graph persistence directory")
parser.add_argument(
    "--model", default="qwen3:8b", help="Already installed Ollama model; no downloads"
)
parser.add_argument(
    "--run",
    action="store_true",
    help="Execute actual pipeline with configured approved model resources",
)
parser.add_argument(
    "--authorized-model-usage",
    action="store_true",
    help="Use only after explicit approval of the configured model and usage",
)
args = parser.parse_args()
if args.local_text is not None:
    if args.local_text.suffix.lower() not in {".txt", ".md", ".markdown"}:
        parser.error(
            "--local-text accepts UTF-8 TXT or Markdown; parse PDF through the upload portal"
        )
    if not args.local_text.is_file() or args.local_text.stat().st_size > 100000:
        parser.error("--local-text must be an existing text file of at most 100000 bytes")
    sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
    from siip.demo_kg import DemoKGRepository

    text = args.local_text.read_text(encoding="utf-8-sig")
    source_id = args.source_id or "source-cli-" + hashlib.sha256(text.encode()).hexdigest()[:16]
    os.environ["SIIP_DEMO_KG_MODE"] = "local"
    os.environ["SIIP_LOCAL_KG_MODEL"] = args.model
    repository = DemoKGRepository(args.output_dir or ROOT / "artifacts/local-kg")
    graph = repository.generate_candidates(
        {
            "source_document_id": source_id,
            "original_filename": args.local_text.name,
            "content": text,
        }
    )
    print(json.dumps(graph, indent=2, ensure_ascii=False))
    raise SystemExit(0)
packages = [
    "docling",
    "dotenv",
    "pydantic",
    "openai",
    "anthropic",
    "sentence_transformers",
    "umap",
    "hdbscan",
]
missing = [name for name in packages if importlib.util.find_spec(name) is None]
provider = os.environ.get("LLM_PROVIDER", "openai")
issues = []
if not os.environ.get("SIIP_EXTRACTION_MODEL"):
    issues.append("SIIP_EXTRACTION_MODEL must identify the approved extraction model.")
if missing:
    issues.append("Missing isolated pipeline packages: " + ", ".join(missing))
if provider in {"vllm", "hf", "local", "huggingface"}:
    issues.append(
        "Original upstream vLLM requires its separate compatible GPU environment; "
        "use --local-text for the bounded Ollama adapter."
    )
if not (ROOT / "research/instructkg-jeffry/main.py").exists():
    issues.append(
        "Original InstructKG research checkout is absent; bootstrap separately before an upstream run."
    )
if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
    issues.append("OPENAI_API_KEY unavailable in this process.")
if provider in {"anthropic", "claude"} and not os.environ.get("ANTHROPIC_API_KEY"):
    issues.append("ANTHROPIC_API_KEY unavailable in this process.")
if not args.authorized_model_usage:
    issues.append("No paid/API model-usage authorization supplied; no inference initiated.")
status = {
    "status": "BLOCKED" if issues else "NOT_RUN",
    "fresh_extraction_executed": False,
    "provider": provider,
    "blockers": issues,
    "source": "research/instructkg-jeffry/main.py",
    "input": "research/instructkg-jeffry/data/sql",
    "expected_outputs": [
        "chunks.jsonl",
        "mentions.jsonl",
        "concept_cards.jsonl",
        "context_clusters.jsonl",
        "pairpackets.jsonl",
        "relations.jsonl",
    ],
}
if args.run and not issues:
    destination = ROOT / "artifacts/fresh-kg"
    destination.mkdir(exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / status["source"]),
        "--data-dir",
        str(ROOT / status["input"]),
        "--out-dir",
        str(destination),
        "--llm-model",
        os.environ.get("SIIP_EXTRACTION_MODEL", "gpt-4o-mini"),
    ]
    with (destination / "run.log").open("w") as log:
        result = subprocess.run(
            command, cwd=ROOT / "research/instructkg-jeffry", stdout=log, stderr=subprocess.STDOUT
        )
    counts = {
        name: sum(bool(line.strip()) for line in (destination / name).open())
        if (destination / name).exists()
        else None
        for name in status["expected_outputs"]
    }
    status.update(
        {
            "status": "PASS"
            if result.returncode == 0 and all(v is not None for v in counts.values())
            else "FAIL",
            "fresh_extraction_executed": True,
            "returncode": result.returncode,
            "actual_counts": counts,
        }
    )
(ROOT / "artifacts").mkdir(exist_ok=True)
(ROOT / "artifacts/fresh_extraction_status.json").write_text(json.dumps(status, indent=2) + "\n")
print(json.dumps(status, indent=2))
