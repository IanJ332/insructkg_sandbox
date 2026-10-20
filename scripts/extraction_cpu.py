"""Isolated upstream imports/non-generative ingestion and future backend planning."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import LOCAL_HOSTS
from siip.extraction import backend_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["imports", "ingest", "full"])
    parser.add_argument("--profile", choices=["native", "tesseract"], default="native")
    parser.add_argument("--authorized-model-usage", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    planned = {}
    if args.mode == "full":
        planned = backend_environment(
            os.environ, authorized_model_usage=args.authorized_model_usage or args.dry_run
        )
    local_runtime = planned.get("LLM_PROVIDER") in {
        "local",
        "hf",
        "huggingface",
        "vllm",
        "hf_legacy",
    }
    if args.dry_run:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "dry_run": True,
                    "generative_calls": 0,
                    "backend": planned.get("LLM_PROVIDER"),
                    "endpoint": planned.get("OPENAI_BASE_URL"),
                    "model": os.getenv("SIIP_EXTRACTION_MODEL") if args.mode == "full" else None,
                    "paid_credential_required": bool(planned)
                    and not local_runtime
                    and urlparse(
                        planned.get("OPENAI_BASE_URL", "https://api.anthropic.com")
                    ).hostname
                    not in LOCAL_HOSTS,
                    "cpu_image_supports_backend": not local_runtime,
                    "note": "In-process vLLM requires the separate Linux/WSL2 GPU environment. API extraction uses Responses, unlike feedback's Chat Completions.",
                },
                indent=2,
            )
        )
        return 0
    if local_runtime:
        raise SystemExit(
            "Local backend accepts no paid credential, but needs a separate GPU runtime; CPU image has no vLLM"
        )
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("Docker required")
    source = ROOT / "research/instructkg-jeffry"
    if not source.exists():
        raise SystemExit("Run scripts/bootstrap.py before extraction")
    suffix = args.profile if args.mode == "ingest" else args.mode
    output = ROOT / "artifacts/followup" / ("ingest-" + suffix if args.mode == "ingest" else suffix)
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "artifacts/phase2/model-cache"
    cache.mkdir(parents=True, exist_ok=True)
    command = [
        docker,
        "run",
        "--rm",
        "--cpus",
        "2",
        "--memory",
        "5g",
        "-e",
        "HF_HOME=/cache",
        "-e",
        "OUT_DIR=/output",
        "-v",
        str(source) + ":/research:ro",
        "-v",
        str(output) + ":/output",
        "-v",
        str(cache) + ":/cache",
        "-v",
        str(ROOT / "scripts") + ":/integration/scripts:ro",
    ]
    for key in planned:
        command += ["-e", key]  # values, including any future secrets, never enter argv
    if args.mode == "imports":
        command += ["--network", "none"]
    command += ["siip-extraction-cpu:phase2", "timeout", "480", "python", "-u"]
    if args.mode == "ingest":
        command += ["/integration/scripts/profile_ingestion.py", "--profile", args.profile]
    else:
        command += ["main.py"]
        if args.mode == "imports":
            command += ["--help"]
        else:
            command += [
                "--data-dir",
                "data/sql",
                "--out-dir",
                "/output",
                "--llm-model",
                os.environ["SIIP_EXTRACTION_MODEL"],
            ]
    with (output / "run.log").open("w") as stream:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, **planned},
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    report = {
        "mode": args.mode,
        "exit_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "generative_model_use_requested": args.mode == "full",
        "input_pdf_sha256": hashlib.sha256(
            (source / "data/sql/3-SQL2-JOINS_Nulls.pdf").read_bytes()
        ).hexdigest(),
        "profile": args.profile if args.mode == "ingest" else None,
    }
    (output / "run-status.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
