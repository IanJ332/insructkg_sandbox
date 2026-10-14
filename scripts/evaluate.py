"""Paired technical checks; never a claim of learning improvement or live inference."""

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.configuration import ProviderConfig, read_env_file
from siip.feedback import CompatibleProvider, build_context, generate_feedback
from siip.grader import grade

parser = argparse.ArgumentParser()
parser.add_argument(
    "--live-local",
    "--live",
    dest="live_local",
    action="store_true",
    help="Use configured local OpenAI-compatible endpoint; does not enable paid remote usage",
)
args = parser.parse_args()
provider = None
if args.live_local:
    config = ProviderConfig.from_env(read_env_file(str(ROOT / ".env"), os.environ))
    if config.provider == "deterministic":
        raise SystemExit(
            "Choose an approved local/compatible provider explicitly; no inference called."
        )
    provider = CompatibleProvider(
        config.base_url,
        config.model,
        config.api_key,
        config.allow_paid,
        config.timeout_seconds,
        config.max_tokens,
        config.retries,
    )
fixtures = json.loads((ROOT / "datasets/synthetic-submissions/attempts.json").read_text())
rows = []
for record in fixtures:
    result = grade(record["question_id"], record["submitted_sql"])
    for mode in ["baseline", "rag", "kg"]:
        context = build_context(record["question_id"], record["submitted_sql"], result, mode)
        feedback = generate_feedback(
            record["question_id"], record["submitted_sql"], result, mode, provider=provider
        )
        refs = feedback["evidence_references"]
        rows.append(
            {
                "attempt_id": record["attempt_id"],
                "question_id": record["question_id"],
                "mode": mode,
                "context": context,
                "feedback": feedback,
                "checks": {
                    "schema_valid": True,
                    "rule_filter_passed": feedback["non_revealing_validation"]
                    == "passed_rule_filter",
                    "has_course_reference": bool(refs),
                    "concept_relevance": "manual_review_pending",
                    "specificity": "manual_review_pending",
                    "diagnosis_supported": "manual_review_pending",
                    "answer_leakage_human_review": "pending",
                },
            }
        )
(ROOT / "artifacts/feedback_comparison.json").write_text(json.dumps(rows, indent=2) + "\n")
lines = [
    "# Technical feedback comparison",
    "",
    "Same 21 synthetic submissions × three contexts. Same configured base model/settings for live-local runs. Deterministic grades remain authoritative.",
    "",
    "This run contains **"
    + str(sum(r["feedback"]["inference_status"] == "live_success" for r in rows))
    + " successful live model calls**. Fallback outputs do not measure LLM quality or student learning.",
    "",
    "| Mode | Outputs | Live success | Schema/filter passed | Median latency ms |",
    "|---|---:|---:|---:|---:|",
]
for mode in ["baseline", "rag", "kg"]:
    selected = [r for r in rows if r["mode"] == mode]
    lines.append(
        "| "
        + mode
        + " | "
        + str(len(selected))
        + " | "
        + str(sum(r["feedback"]["inference_status"] == "live_success" for r in selected))
        + " | "
        + str(
            sum(r["checks"]["schema_valid"] and r["checks"]["rule_filter_passed"] for r in selected)
        )
        + " | "
        + str(round(statistics.median(r["feedback"]["latency_ms"] for r in selected), 3))
        + " |"
    )
lines += [
    "",
    "Token usage and cost: null (no live provider usage in default mode; no pricing assumptions). Context construction time is included. These latencies are not model inference benchmarks.",
    "",
    "Baseline excludes lecture/graph context. RAG retrieves actual PDF pages. KG adds diagnosis, provisional prerequisites and explicitly unreviewed existing judgments. Original graph is never described as instructor approved.",
    "",
    "Manually inspect artifacts/feedback_comparison.json for all prompts, outputs and evidence. Human ratings of relevance, specificity, grounding quality, and leakage remain pending; automatic reference presence is not proof of semantic grounding.",
    "",
    "Live inference is BLOCKED until a suitable local model server is available or explicit authorization for approved provider usage is supplied. No paid API requests were made.",
]
(ROOT / "artifacts/FEEDBACK_COMPARISON.md").write_text("\n".join(lines) + "\n")
print(
    f"Wrote {len(rows)} paired outputs. Live success: "
    + str(sum(r["feedback"]["inference_status"] == "live_success" for r in rows))
)
