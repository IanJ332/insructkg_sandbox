"""Read-only model-server readiness; never sends completion/generation requests."""

import argparse
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import LOCAL_HOSTS, ProviderConfig, read_env_file


def probe_models(config):
    config.validate()
    if config.provider != "local" or urlparse(config.base_url).hostname not in LOCAL_HOSTS:
        raise ValueError("Metadata probe is restricted to an explicitly local endpoint")
    request = urllib.request.Request(config.base_url.rstrip("/") + "/models")
    if config.api_key:
        request.add_header("Authorization", "Bearer " + config.api_key)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=2) as response:
            body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Metadata response too large")
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("Invalid metadata schema")
        found = any(isinstance(row, dict) and row.get("id") == config.model for row in data["data"])
        return {
            "status": "model_listed" if found else "model_not_listed",
            "inference_verified": False,
        }
    except (OSError, ValueError, TypeError):
        return {"status": "unavailable_or_invalid_metadata", "inference_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Only GET /v1/models; no inference")
    args = parser.parse_args()
    config = ProviderConfig.from_env(read_env_file(str(ROOT / ".env"), os.environ))
    report = {
        "config_status": "valid",
        "provider": config.provider,
        "model": config.model,
        "tools_on_current_host": {
            name: bool(shutil.which(name)) for name in ["ollama", "vllm", "nvidia-smi", "wsl"]
        },
        "inference": "BLOCKED; not executed",
        "probe": "NOT_RUN",
    }
    if args.probe:
        report["probe"] = probe_models(config)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
