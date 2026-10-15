"""Retrieve immutable public research revisions into isolated checkouts."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
if GIT is None:
    raise SystemExit("git is required")
REPOS = [
    (
        "instructkg-jeffry",
        "https://github.com/code-royce/instructkg.git",
        "c34a7786528e78766f15d918ab17aca2a9f7dc0b",
    ),
    (
        "instructkg-reference",
        "https://github.com/aalrabah/instructkg.git",
        "ade6263a348984cef848eae85dc3d3b15daeea09",
    ),
    (
        "PrairieLearn",
        "https://github.com/PrairieLearn/PrairieLearn.git",
        "eaaa91843807411918d260475e0a9188bcc2c979",
    ),
]
for name, url, commit in REPOS:
    path = ROOT / "research" / name
    if not path.exists():
        subprocess.run(
            [GIT, "clone", "--no-checkout", "--filter=blob:none", url, str(path)], check=True
        )
    current = subprocess.check_output([GIT, "-C", str(path), "status", "--porcelain"], text=True)
    if current.strip():
        raise SystemExit("Preserving modified research checkout: " + str(path))
    subprocess.run([GIT, "-C", str(path), "checkout", "--detach", commit], check=True)
    print(
        name,
        subprocess.check_output([GIT, "-C", str(path), "rev-parse", "HEAD"], text=True).strip(),
    )
