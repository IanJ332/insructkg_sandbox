"""Statistical Analysis and Scoring Script for SIIP Research Evaluation.

Processes human / expert scoring sheets from the blind review packet, unblinds
conditions using blind_review_key.json, and generates comparative metrics across:
- Condition A: Baseline LLM
- Condition B: Lecture RAG
- Condition C: Lecture RAG + Knowledge Graph
- Condition D: KG without prior history
- Condition E: KG with prior history
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "artifacts/research"


def analyze_scores(scores_file: Path, key_file: Path) -> Dict[str, Any]:
    if not scores_file.exists():
        raise FileNotFoundError(f"Scores file not found: {scores_file}")
    if not key_file.exists():
        raise FileNotFoundError(f"Unblinding key file not found: {key_file}")

    scores_data = json.loads(scores_file.read_text(encoding="utf-8"))
    key_mapping = json.loads(key_file.read_text(encoding="utf-8"))

    # Aggregators by condition
    metrics = ["correctness", "evidence_grounding", "concept_relevance", "actionability"]
    flags = ["answer_leakage", "hallucination"]

    condition_data: Dict[str, Dict[str, List[float]]] = {
        cond: {m: [] for m in metrics + flags} for cond in ["A", "B", "C", "D", "E"]
    }

    reviews = scores_data.get("reviews", [])
    for review in reviews:
        cid = review["eval_id"]
        blind_id = review["blind_id"]
        lookup_key = f"{cid}:{blind_id}"
        actual_cond = key_mapping.get(lookup_key)
        if not actual_cond:
            continue

        for m in metrics + flags:
            if m in review:
                condition_data[actual_cond][m].append(float(review[m]))

    results = {}
    for cond, values in condition_data.items():
        cond_summary = {}
        for m in metrics:
            vals = values[m]
            if vals:
                cond_summary[m] = {
                    "mean": round(statistics.mean(vals), 3),
                    "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
                    "count": len(vals),
                }
            else:
                cond_summary[m] = {"mean": None, "count": 0}

        for f in flags:
            vals = values[f]
            if vals:
                cond_summary[f] = {
                    "rate": round(sum(vals) / len(vals), 3),
                    "total_flagged": int(sum(vals)),
                    "count": len(vals),
                }
            else:
                cond_summary[f] = {"rate": None, "count": 0}

        results[cond] = cond_summary

    return results


def main():
    parser = argparse.ArgumentParser(description="Analyze SIIP Blind Review Results")
    parser.add_argument(
        "--scores",
        default=str(RESEARCH_DIR / "sample_scores.json"),
        help="Path to reviewed scores JSON",
    )
    parser.add_argument(
        "--key",
        default=str(RESEARCH_DIR / "blind_review_key.json"),
        help="Path to unblinding key JSON",
    )
    args = parser.parse_args()

    scores_p = Path(args.scores)
    key_p = Path(args.key)

    if not scores_p.exists():
        print(
            f"Scores file '{scores_p}' not yet present. Analysis ready when reviews are collected."
        )
        return

    analysis = analyze_scores(scores_p, key_p)
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
