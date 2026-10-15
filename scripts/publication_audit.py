"""Fail closed on restricted paths; scan prospective files and every reachable Git blob.

Only hashes/types/line numbers of scanner findings are printed, never matched values.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
if GIT is None:
    raise SystemExit("git is required")
RESTRICTED = ("research/", "artifacts/", "datasets/knowledge-graphs/")
BANNED_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".mp4",
    ".mov",
    ".webm",
    ".sqlite3",
    ".dump",
    ".db",
    ".pem",
    ".key",
    ".pfx",
    ".zip",
}
GENERATED = {"lecture.json", "existing_relations.jsonl", "reviews.json"}


def permitted(path):
    p = Path(path)
    return not (
        path.startswith(RESTRICTED)
        or p.suffix.lower() in BANNED_SUFFIXES
        or p.name in GENERATED
        or (p.name.startswith(".env") and p.name != ".env.example")
        or any(
            part.startswith(".venv") or part in {"__pycache__", "node_modules", ".git"}
            for part in p.parts
        )
    )


def run_audit(history=True):
    command = [GIT, "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    paths = sorted(
        set(subprocess.check_output(command, cwd=ROOT).decode().strip("\0").split("\0")) - {""}
    )
    prohibited = [p for p in paths if not permitted(p)]
    if prohibited:
        raise ValueError("Restricted publication paths: " + ", ".join(prohibited))
    scan_files = [str(ROOT / p) for p in paths if (ROOT / p).is_file()]
    findings = []
    reviewed = []
    allowlist = json.loads((ROOT / "security/secret-allowlist.json").read_text())
    # The SHA1 identifiers in this explicit non-secret manifest are also non-secret.
    manifest_hashes = {
        hashlib.sha1(k.encode(), usedforsecurity=False).hexdigest() for k in allowlist
    }
    with tempfile.TemporaryDirectory(prefix="siip-audit-") as temporary:
        if history:
            # Deduplicate all reachable blobs; scanner sees historical contents, not only HEAD.
            objects = subprocess.check_output(
                [GIT, "rev-list", "--objects", "--all"], cwd=ROOT, text=True
            ).splitlines()
            for row in objects:
                oid, _, path = row.partition(" ")
                if not path:
                    continue
                kind = subprocess.check_output(
                    [GIT, "cat-file", "-t", oid], cwd=ROOT, text=True
                ).strip()
                if kind != "blob":
                    continue
                if not permitted(path):
                    raise ValueError("Restricted file exists in Git history: " + path)
                content = subprocess.check_output([GIT, "cat-file", "blob", oid], cwd=ROOT)
                target = Path(temporary) / (oid + "-" + Path(path).name)
                target.write_bytes(content)
                scan_files.append(str(target))
        batch_size = 50
        merged_results = {}
        for i in range(0, len(scan_files), batch_size):
            chunk = scan_files[i : i + batch_size]
            result = subprocess.run(
                [sys.executable, "-m", "detect_secrets", "scan", "--no-verify", *chunk],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            chunk_data = json.loads(result.stdout)
            merged_results.update(chunk_data.get("results", {}))
        data = {"results": merged_results}
        for path, entries in data.get("results", {}).items():
            for entry in entries:
                if (
                    entry["type"] == "Hex High Entropy String"
                    and entry["hashed_secret"] in manifest_hashes
                ):
                    reviewed.append(
                        {
                            "path": Path(path).name,
                            "line": entry["line_number"],
                            "reason": "SHA1 identifier in reviewed non-secret manifest",
                        }
                    )
                    continue
                if (
                    entry["hashed_secret"] in allowlist
                    and entry["type"] == allowlist[entry["hashed_secret"]]["type"]
                ):
                    reviewed.append(
                        {
                            "path": Path(path).name,
                            "line": entry["line_number"],
                            "reason": allowlist[entry["hashed_secret"]]["reason"],
                        }
                    )
                    continue
                findings.append(
                    {
                        "path": Path(path).name,
                        "line": entry["line_number"],
                        "type": entry["type"],
                        "hashed_secret": entry["hashed_secret"],
                    }
                )
    report = {
        "status": "FAIL" if findings else "PASS",
        "prospective_files": len(paths),
        "history_scanned": history,
        "restricted_paths": prohibited,
        "secret_findings": findings,
        "reviewed_nonsecret_findings": reviewed,
        "license": "No blanket license assigned; publication authorization does not establish third-party redistribution rights.",
        "excluded": "All research checkouts, course PDF/text, original graph outputs, runtime data, recordings and raw logs.",
    }
    (ROOT / "artifacts/phase2").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/phase2/publication-audit.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()
    run_audit(not args.no_history)
