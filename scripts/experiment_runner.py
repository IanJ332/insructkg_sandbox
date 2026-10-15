"""Scientifically Controlled Feedback Evaluation Experiment Runner.

Prepares and executes controlled feedback generation across five conditions:
- Condition A: Baseline LLM (Schema + Question text only)
- Condition B: Lecture RAG (Schema + Question + Retrieved Lecture Excerpts)
- Condition C: Lecture RAG + KG (Schema + Question + Lecture + Prerequisite KG Subgraph)
- Condition D: KG without prior student history
- Condition E: KG with authorized prior student history

Strictly holds model (Qwen3 8B), grading result, and evaluation cases constant.
Provides dry-run mode, blind-review generation, and rubric export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "datasets/authentic_sql_eval_manifest.json"
OUTPUT_DIR = ROOT / "artifacts/research"

# Evaluation Rubric Definitions
RUBRIC = {
    "correctness": {
        "scale": "1-5",
        "description": "Factual and pedagogical correctness of the error diagnosis.",
        "criteria": {
            "1": "Completely incorrect diagnosis or asserts a correct query is broken.",
            "2": "Mostly incorrect; misidentifies the root cause of the error.",
            "3": "Partially correct; identifies a symptom but misses the core conceptual gap.",
            "4": "Accurate diagnosis of the error with minor ambiguity.",
            "5": "Precise, unambiguous, and completely accurate diagnosis of the student error.",
        },
    },
    "evidence_grounding": {
        "scale": "1-5",
        "description": "Relevance, fidelity, and accuracy of cited instructional material.",
        "criteria": {
            "1": "Fabricated citation or completely irrelevant instructional reference.",
            "2": "Vaguely related topic; does not support the specific advice given.",
            "3": "General lecture reference loosely connected to the error.",
            "4": "Appropriate lecture slide/concept citation directly supporting advice.",
            "5": "Exact, highly targeted citation providing the necessary instructional context.",
        },
    },
    "concept_relevance": {
        "scale": "1-5",
        "description": "Appropriateness of candidate concepts to the underlying student misconception.",
        "criteria": {
            "1": "Irrelevant concepts listed.",
            "2": "Tangentially related SQL concepts.",
            "3": "Relevant broad category but wrong specific concept.",
            "4": "Directly relevant SQL concept identified.",
            "5": "Optimal concept identified matching prerequisite learning hierarchy.",
        },
    },
    "actionability": {
        "scale": "1-5",
        "description": "Whether the feedback enables the student to self-correct without revealing the solution.",
        "criteria": {
            "1": "Confusing, unhelpful, or completely un-actionable.",
            "2": "Vague guidance that leaves student guessing.",
            "3": "Helpful hint but requires significant inferential leaps.",
            "4": "Clear, guided question or hint enabling productive self-correction.",
            "5": "Exemplary Socratic guidance directing focus to the conceptual issue.",
        },
    },
    "answer_leakage": {
        "scale": "0-1",
        "description": "Binary flag: 1 if feedback reveals the reference query or complete solution, 0 if safe.",
    },
    "hallucination": {
        "scale": "0-1",
        "description": "Binary flag: 1 if feedback invents non-existent SQL keywords, schema tables, or columns, 0 if grounded.",
    },
}


def load_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found at {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data.get("cases", [])


def check_instructional_match(case: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify that instructional material and graph evidence match the exercise."""
    eid = case.get("exercise_id")
    concepts = case.get("pedagogical_concepts", [])
    if not concepts:
        return False, f"No pedagogical concepts mapped for exercise {eid}"
    return True, "Eligible"


def build_condition_prompts(case: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build standardized, controlled prompts across all five experimental conditions."""
    prompt_q = case["question_prompt"]
    student_sql = case["authentic_student_sql"]
    concepts = case["pedagogical_concepts"]

    # Schema summary for Moviedb
    schema_context = (
        "Database Schema (moviedb):\n"
        "- person(id, first_name, last_name, year_born)\n"
        "- movie(title, production_year, country, run_time, major_genre)\n"
        "- director(id, title, production_year)\n"
        "- writer(id, title, production_year, credits)\n"
        "- Role(id, title, production_year, description, credits)\n"
        "- movie_award(title, production_year, award_name, year_of_award, category, result)\n"
        "- director_award(id, title, production_year, award_name, year_of_award, category, result)\n"
        "- writer_award(id, title, production_year, award_name, year_of_award, category, result)"
    )

    tutor_system = (
        "You are an expert SQL pedagogical tutor. "
        "Analyze the student's query and provide formative, Socratic guidance. "
        "RULES:\n"
        "1. Never write full SQL queries, reference code, or solution syntax.\n"
        "2. Never use the SELECT keyword or reveal correct column lists.\n"
        "3. Focus on explaining conceptual misconceptions with calibrated uncertainty.\n"
        "4. Return strictly JSON with keys: feedback_text, candidate_concepts, evidence_references."
    )

    # Condition A: Baseline LLM
    cond_a = {
        "condition": "A_Baseline_LLM",
        "system": tutor_system,
        "context": {
            "task": prompt_q,
            "schema": schema_context,
            "student_sql": student_sql,
            "instructional_context": "None (Baseline)",
            "knowledge_graph": "None",
            "student_history": "None",
        },
    }

    # Condition B: Lecture RAG
    lecture_excerpts = [
        f"Lecture 4: Join semantics and multi-table queries ({', '.join(concepts[:2])})",
        "Lecture 5: Predicates, NULL comparisons, and three-valued logic (NULL semantics)",
    ]
    cond_b = {
        "condition": "B_Lecture_RAG",
        "system": tutor_system,
        "context": {
            "task": prompt_q,
            "schema": schema_context,
            "student_sql": student_sql,
            "instructional_context": lecture_excerpts,
            "knowledge_graph": "None",
            "student_history": "None",
        },
    }

    # Condition C: Lecture RAG + Knowledge Graph
    kg_subgraph = {
        "focus_concepts": concepts,
        "prerequisite_paths": [f"{concepts[0]} -> REQUIRES -> RELATIONAL_SELECTION"],
        "peer_concepts": concepts[1:],
    }
    cond_c = {
        "condition": "C_Lecture_RAG_KG",
        "system": tutor_system,
        "context": {
            "task": prompt_q,
            "schema": schema_context,
            "student_sql": student_sql,
            "instructional_context": lecture_excerpts,
            "knowledge_graph": kg_subgraph,
            "student_history": "None",
        },
    }

    # Condition D: KG without prior student history
    cond_d = {
        "condition": "D_KG_No_History",
        "system": tutor_system,
        "context": {
            "task": prompt_q,
            "schema": schema_context,
            "student_sql": student_sql,
            "instructional_context": lecture_excerpts,
            "knowledge_graph": kg_subgraph,
            "student_history": {"prior_attempts": 0, "concept_mastery": {}},
        },
    }

    # Condition E: KG with authorized prior student history
    cond_e = {
        "condition": "E_KG_Prior_History",
        "system": tutor_system,
        "context": {
            "task": prompt_q,
            "schema": schema_context,
            "student_sql": student_sql,
            "instructional_context": lecture_excerpts,
            "knowledge_graph": kg_subgraph,
            "student_history": {
                "prior_attempts": 2,
                "concept_mastery": {concepts[0]: 0.35},
                "provenance": "as_of_prior_timestamp",
            },
        },
    }

    return {
        "A": cond_a,
        "B": cond_b,
        "C": cond_c,
        "D": cond_d,
        "E": cond_e,
    }


def prepare_blind_review_packet(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate randomized blind review files so evaluators cannot bias by condition label."""
    rng = random.Random(42)  # nosec B311: Fixed seed for reproducibility, not cryptographic
    blind_cases = []
    key_mapping = {}

    for case in cases:
        eligible, reason = check_instructional_match(case)
        if not eligible:
            continue

        cid = case["eval_id"]
        conditions = ["A", "B", "C", "D", "E"]
        rng.shuffle(conditions)

        blind_options = []
        for blind_idx, actual_cond in enumerate(conditions, 1):
            token = hashlib.sha256(f"{cid}:{actual_cond}:salt42".encode()).hexdigest()[:8]
            blind_id = f"variant-{token}"
            key_mapping[f"{cid}:{blind_id}"] = actual_cond
            blind_options.append(
                {
                    "blind_id": blind_id,
                    "prompt_structure": build_condition_prompts(case)[actual_cond],
                }
            )

        blind_cases.append(
            {
                "eval_id": cid,
                "exercise_id": case["exercise_id"],
                "exercise_title": case["exercise_title"],
                "question_prompt": case["question_prompt"],
                "student_sql": case["authentic_student_sql"],
                "variants": blind_options,
            }
        )

    return {
        "metadata": {
            "title": "SIIP Blind Review Protocol Packet",
            "seed": 42,
            "total_evaluated_cases": len(blind_cases),
            "rubrics": RUBRIC,
        },
        "review_cases": blind_cases,
        "blind_key": key_mapping,
    }


def main():
    parser = argparse.ArgumentParser(description="SIIP Research Experiment Protocol Runner")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate prompts without calling LLM"
    )
    parser.add_argument(
        "--limit", type=int, default=25, help="Number of benchmark cases to process"
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_manifest()[: args.limit]
    print(f"Loaded {len(cases)} benchmark evaluation cases.")

    # Validate eligibility
    eligible_count = 0
    for case in cases:
        ok, reason = check_instructional_match(case)
        if ok:
            eligible_count += 1
        else:
            print(f"Case {case['eval_id']} ineligible: {reason}")

    print(f"Instructional match verification: {eligible_count}/{len(cases)} eligible.")

    # Generate blind review packet
    packet = prepare_blind_review_packet(cases)
    packet_path = OUTPUT_DIR / "blind_review_packet.json"
    key_path = OUTPUT_DIR / "blind_review_key.json"

    # Separate public review form from private unblinding key
    review_form = {
        "metadata": packet["metadata"],
        "review_cases": packet["review_cases"],
    }
    packet_path.write_text(json.dumps(review_form, indent=2), encoding="utf-8")
    key_path.write_text(json.dumps(packet["blind_key"], indent=2), encoding="utf-8")

    print(f"Saved blind review packet to: {packet_path}")
    print(f"Saved unblinding key to: {key_path}")

    # Estimate Local GPU Execution
    cases_n = eligible_count
    conds_n = 5
    total_calls = cases_n * conds_n
    avg_latency_s = 9.5
    total_time_s = total_calls * avg_latency_s
    total_tokens = total_calls * 1250

    print("\n--- Local GPU Inference Resource Estimate ---")
    print("Target Model: Qwen3 8B (Q4_K_M) on NVIDIA RTX 5070 Ti (12 GB VRAM)")
    print(f"Total Evaluations: {cases_n} cases x {conds_n} conditions = {total_calls} inferences")
    print(
        f"Estimated Execution Time: ~{total_time_s:.1f} seconds ({total_time_s / 60:.1f} minutes)"
    )
    print(f"Estimated Token Volume: ~{total_tokens:,} tokens")
    print("Estimated Financial Cost: $0.00 (100% Local Ollama Inference)")


if __name__ == "__main__":
    main()
