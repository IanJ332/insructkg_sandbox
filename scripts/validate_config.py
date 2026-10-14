"""Validate owned course/configuration files without upstream code or protected material."""

import json
import sys
import tomllib
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import ProviderConfig

for folder in ["prairielearn-course", "datasets", "security"]:
    for path in (ROOT / folder).rglob("*.json"):
        if path.name in {
            "lecture.json",
            "existing_relations.json",
            "reviews.json",
            "review_queue.json",
        }:
            continue
        value = json.loads(path.read_text())
        if isinstance(value, dict) and "uuid" in value:
            uuid.UUID(value["uuid"])
course = ROOT / "prairielearn-course"
assessment = json.loads(
    (course / "courseInstances/Fall2026/assessments/sql-sandbox/infoAssessment.json").read_text()
)
for zone in assessment["zones"]:
    for question in zone["questions"]:
        assert (course / "questions" / question["id"] / "server.py").exists()
        assert json.loads((course / "questions" / question["id"] / "info.json").read_text())[
            "singleVariant"
        ]
compose = yaml.safe_load((ROOT / "infrastructure/compose.yaml").read_text())
service = compose["services"]["prairielearn"]
assert service["ports"] == ["127.0.0.1:3000:3000"]
assert "@sha256:" in service["image"] and not service.get("privileged", False)
assert all("docker.sock" not in mount for mount in service["volumes"])
with (ROOT / "pyproject.toml").open("rb") as stream:
    tomllib.load(stream)
ProviderConfig.from_env({})
print(
    "Owned JSON/UUID/QID links, TOML, loopback Compose, immutable image and default provider configuration: PASS"
)
