"""Original portable contract fixtures; never a substitute for real research verification."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/public-data"
TARGET.mkdir(parents=True, exist_ok=True)
source = ROOT / "prairielearn-course/serverFilesCourse/siip/data"
for name in [
    "questions.json",
    "dataset_A.sql",
    "dataset_B.sql",
    "mapping.json",
    "provisional_relations.jsonl",
]:
    shutil.copyfile(source / name, TARGET / name)
records = [
    {
        "A": {"name": "CONTRACT_SQL", "role": "Definition"},
        "B": {"name": "CONTRACT_TABLES", "role": "Definition"},
        "relation": "depends_on",
        "justification": "Original synthetic schema fixture; not extraction.",
        "evidence_chunks": [
            {"chunk_id": "public:1", "text": "Original synthetic contract evidence."}
        ],
    },
    {
        "A": {"name": "CONTRACT_TABLES"},
        "B": {"name": "CONTRACT_NULL"},
        "relation": None,
        "evidence_chunks": [],
    },
]
(TARGET / "existing_relations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
(TARGET / "provenance.json").write_text(
    json.dumps(
        {
            "kind": "synthetic_contract_fixture",
            "source": "scripts/init_public.py",
            "instructor_reviewed": False,
        }
    )
)
text = (ROOT / "tests/fixtures/lesson.md").read_text()
(TARGET / "lecture.json").write_text(
    json.dumps(
        [
            {
                "id": f"public:lesson:{i}",
                "page": i,
                "text": paragraph,
                "source_file": "tests/fixtures/lesson.md",
                "source_kind": "synthetic_contract_fixture",
            }
            for i, paragraph in enumerate(text.split("\n\n"), 1)
            if len(paragraph) > 80
        ]
    )
)
print(
    f"Initialized ORIGINAL SYNTHETIC CONTRACT fixtures at {TARGET}; no real graph/PDF or live inference is implied."
)
