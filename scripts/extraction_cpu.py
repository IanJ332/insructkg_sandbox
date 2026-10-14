"""Launch unmodified upstream stages in the isolated locked CPU/API environment."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DOCKER = shutil.which("docker")
GIT = shutil.which("git")
if DOCKER is None or GIT is None:
    raise SystemExit("Docker and Git are required")
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["imports", "ingest", "full"])
parser.add_argument("--authorized-model-usage", action="store_true")
args = parser.parse_args()
source = ROOT / "research/instructkg-jeffry"
if not source.exists():
    raise SystemExit("Run scripts/bootstrap.py before extraction")
output = ROOT / "artifacts/phase2/fresh-cpu"
output.mkdir(parents=True, exist_ok=True)
cache = ROOT / "artifacts/phase2/model-cache"
cache.mkdir(parents=True, exist_ok=True)
command = [
    DOCKER,
    "run",
    "--rm",
    "--cpus",
    "2",
    "--memory",
    "5g",
    "-e",
    "HF_HOME=/cache",
    "-v",
    str(source) + ":/research:ro",
    "-v",
    str(output) + ":/output",
    "-v",
    str(cache) + ":/cache",
]
if args.mode == "imports":
    command += ["--network", "none"]
if args.mode == "full":
    if not args.authorized_model_usage or not os.getenv("SIIP_EXTRACTION_MODEL"):
        raise SystemExit(
            "BLOCKED: explicit model-usage authorization and SIIP_EXTRACTION_MODEL required"
        )
    provider = os.getenv("LLM_PROVIDER", "openai")
    key = "ANTHROPIC_API_KEY" if provider in {"anthropic", "claude"} else "OPENAI_API_KEY"
    if not os.getenv(key):
        raise SystemExit("BLOCKED: approved provider credential unavailable")
    command += ["-e", "LLM_PROVIDER=" + provider, "-e", key]
command += ["siip-extraction-cpu:phase2", "timeout", "600", "python", "main.py"]
if args.mode == "imports":
    command += ["--help"]
else:
    command += ["--data-dir", "data/sql", "--out-dir", "/output"]
    if args.mode == "ingest":
        command += ["--steps", "ingest"]
    else:
        command += ["--llm-model", os.environ["SIIP_EXTRACTION_MODEL"]]
started = datetime.now(timezone.utc)
log = output / (args.mode + ".log")
with log.open("w") as stream:
    result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
expected = [
    "chunks.jsonl",
    "mentions.jsonl",
    "concept_cards.jsonl",
    "context_clusters.jsonl",
    "pairpackets.jsonl",
    "relations.jsonl",
]
counts = {
    name: sum(bool(line.strip()) for line in (output / name).open())
    if (output / name).exists()
    else None
    for name in expected
}
report = {
    "mode": args.mode,
    "status": "PASS" if result.returncode == 0 else "FAIL",
    "exit_code": result.returncode,
    "started": started.isoformat(),
    "finished": datetime.now(timezone.utc).isoformat(),
    "actual_counts": counts,
    "upstream_commit": subprocess.check_output(
        [GIT, "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip(),
    "input_pdf_sha256": hashlib.sha256(
        (source / "data/sql/3-SQL2-JOINS_Nulls.pdf").read_bytes()
    ).hexdigest(),
    "generative_feedback_or_concept_calls": args.mode == "full",
    "model": os.getenv("SIIP_EXTRACTION_MODEL") if args.mode == "full" else None,
}
(output / (args.mode + "-status.json")).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(result.returncode)
