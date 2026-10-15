"""Inspect the distribution's exact file inventory before any delivery."""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
wheels = list((ROOT / "artifacts/dist").glob("*.whl"))
assert wheels, "Build a wheel first"
for wheel in wheels:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in names:
            assert not any(
                part in name
                for part in [
                    "data/lecture.json",
                    "data/existing_relations.jsonl",
                    "research/",
                    ".env",
                    "sqlite3",
                ]
            )
            assert archive.getinfo(name).file_size < 200000
        assert "siip/grader.py" in names and "siip/data/questions.json" in names
    print("Publishable code-only wheel:", wheel.name, "files:", len(names))
