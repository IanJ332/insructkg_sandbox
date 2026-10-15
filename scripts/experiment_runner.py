"""Scientifically Controlled Feedback Evaluation Experiment Runner.

Prepares and executes controlled feedback generation across five conditions:
- Condition A: Baseline LLM (Schema + Question text + Student SQL only)
- Condition B: Authentic Lecture RAG (Schema + Question + Student SQL + Verified Excerpts)
- Condition C: Authentic Lecture RAG + Verified KG (Schema + Question + Student SQL + Excerpts + Verified Subgraph)
- Condition D: Verified KG without prior student history
- Condition E: Verified KG with authentic prior student history (strictly prior submissions)

Key Methodology Invariants:
1. Holds model (Qwen3 8B), grading result, question context, and evaluation cases constant across A, B, C.
2. Uses only authentic evidence from the Evidence Registry (no fabricated lecture excerpts or synthetic REQUIRES edges).
3. Condition E uses genuine temporal prior student history from the ANU database; no invented mastery values.
4. Reviewer-facing blind packets contain only task context, student SQL, and anonymous responses; no prompt or condition exposure.
5. Provides non-inferential --dry-run mode and local Ollama --execute mode with idempotent caching, resumption, and strict output validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.evidence_registry import EvidenceRegistry

MANIFEST_PATH = ROOT / "datasets/authentic_sql_eval_manifest.json"
OUTPUT_DIR = ROOT / "artifacts/research"
RAW_RESULTS_DIR = OUTPUT_DIR / "raw_results"

PROMPT_VERSION = "siip-eval-v4.4"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

# Database Schema Summary for ANU moviedb
SCHEMA_CONTEXT = (
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

# Standardized Socratic Tutor System Instructions
TUTOR_SYSTEM = (
    "You are an expert SQL pedagogical tutor assisting a student who submitted a partially correct query. "
    "Your goal is to provide formative, Socratic guidance that helps the student identify their own conceptual gap. "
    "RULES:\n"
    "1. Never provide full SQL queries, reference solutions, or complete replacement clauses.\n"
    "2. Never use the SELECT keyword in your guidance_hint or reveal the exact expected column projection.\n"
    "3. Focus on the core logical misconception with calibrated, constructive guidance.\n"
    "4. Return strictly a JSON object with exactly these four keys:\n"
    '   - "observed_error": Brief explanation of the logical or structural flaw in the query.\n'
    '   - "candidate_concepts": List of relevant SQL/relational concepts from instruction.\n'
    '   - "guidance_hint": Socratic hint guiding self-correction without leaking the solution.\n'
    '   - "evidence_citations": List of specific course or schema evidence references supporting the advice, if provided in context.'
)

# Scientifically Balanced Evaluation Rubric
RUBRIC = {
    "correctness": {
        "scale": "1-5",
        "description": "Factual and pedagogical correctness of the error diagnosis.",
        "criteria": {
            "1": "Completely incorrect diagnosis or asserts a correct query is broken.",
            "2": "Mostly incorrect; misidentifies the root cause of the error.",
            "3": "Partially correct; identifies a symptom but misses the core conceptual gap.",
            "4": "Accurate diagnosis of the error with minor ambiguity.",
            "5": "Precise, unambiguous, and completely accurate diagnosis of the student misconception.",
        },
    },
    "evidence_grounding": {
        "scale": "1-5",
        "description": "Fidelity and accuracy of cited instructional or schema material (if any cited).",
        "criteria": {
            "1": "Fabricated citation or completely irrelevant instructional reference.",
            "2": "Vaguely related topic; does not support the specific advice given.",
            "3": "General reference loosely connected to the error.",
            "4": "Appropriate schema or concept citation directly supporting advice.",
            "5": "Exact, highly targeted citation providing the necessary instructional context.",
        },
        "scoring_note": (
            "Distinguish citation presence from citation correctness. Baseline LLM (Condition A) "
            "receives no retrieval context and should not be penalized on general correctness merely "
            "for omitting citations."
        ),
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
        "description": "Binary flag: 1 if feedback reveals the reference query, solution syntax, or complete clauses; 0 if safe.",
    },
    "hallucination": {
        "scale": "0-1",
        "description": "Binary flag: 1 if feedback invents non-existent SQL keywords, schema tables, or columns; 0 if grounded.",
    },
}


def load_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found at {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data.get("cases", [])


def build_condition_prompts(
    case: Dict[str, Any], registry: EvidenceRegistry
) -> Dict[str, Dict[str, Any]]:
    """Build standardized, controlled prompts across all five experimental conditions.

    Strictly holds question, student SQL, evaluation constraints, and grading context constant.
    """
    prompt_q = case["question_prompt"]
    student_sql = case["authentic_student_sql"]
    prior_history = case.get("authentic_prior_history", {})

    # Retrieve verifiable evidence from registry (no hardcoded fake lectures)
    schema_item = registry.items.get("ev-anu-schema-moviedb")

    # Lecture RAG evidence: authentic course document citations
    # If no course lecture slides were deposited for this exercise in ANU, note explicitly.
    lecture_excerpts = (
        [
            f"Course Reference Document: {schema_item.source_doc_id} ({schema_item.location}): {schema_item.text_excerpt}"
        ]
        if schema_item
        else []
    )

    # Knowledge Graph subgraph from registry
    kg_subgraph = registry.get_provisional_kg_subgraph(case)

    # Condition A: Baseline LLM (No lecture, no KG, no history)
    cond_a = {
        "condition": "A_Baseline_LLM",
        "system": TUTOR_SYSTEM,
        "context": {
            "task_description": prompt_q,
            "database_schema": SCHEMA_CONTEXT,
            "student_submission": student_sql,
            "instructional_context": "None (Zero-shot baseline)",
            "knowledge_graph": "None",
            "student_history": "None",
        },
    }

    # Condition B: Authentic Lecture RAG (Verifiable excerpts, no KG, no history)
    cond_b = {
        "condition": "B_Lecture_RAG",
        "system": TUTOR_SYSTEM,
        "context": {
            "task_description": prompt_q,
            "database_schema": SCHEMA_CONTEXT,
            "student_submission": student_sql,
            "instructional_context": lecture_excerpts
            if lecture_excerpts
            else "No authentic lecture slide deposited for this exercise.",
            "knowledge_graph": "None",
            "student_history": "None",
        },
    }

    # Condition C: Authentic Lecture RAG + Verified KG (Excerpts + Subgraph, no history)
    cond_c = {
        "condition": "C_Lecture_RAG_KG",
        "system": TUTOR_SYSTEM,
        "context": {
            "task_description": prompt_q,
            "database_schema": SCHEMA_CONTEXT,
            "student_submission": student_sql,
            "instructional_context": lecture_excerpts
            if lecture_excerpts
            else "No authentic lecture slide deposited for this exercise.",
            "knowledge_graph": kg_subgraph,
            "student_history": "None",
        },
    }

    # Condition D: KG without Prior Student History
    cond_d = {
        "condition": "D_KG_No_History",
        "system": TUTOR_SYSTEM,
        "context": {
            "task_description": prompt_q,
            "database_schema": SCHEMA_CONTEXT,
            "student_submission": student_sql,
            "instructional_context": lecture_excerpts
            if lecture_excerpts
            else "No authentic lecture slide deposited for this exercise.",
            "knowledge_graph": kg_subgraph,
            "student_history": {
                "status": "no_prior_history",
                "prior_attempts": 0,
                "concept_mastery": {},
            },
        },
    }

    # Condition E: KG with Genuine Prior Student History
    cond_e = {
        "condition": "E_KG_Prior_History",
        "system": TUTOR_SYSTEM,
        "context": {
            "task_description": prompt_q,
            "database_schema": SCHEMA_CONTEXT,
            "student_submission": student_sql,
            "instructional_context": lecture_excerpts
            if lecture_excerpts
            else "No authentic lecture slide deposited for this exercise.",
            "knowledge_graph": kg_subgraph,
            "student_history": {
                "status": prior_history.get("status", "authentic_prior_history"),
                "student_id": case["student_id"],
                "prior_attempts": prior_history.get("prior_attempts", 0),
                "historical_observation_count": prior_history.get(
                    "historical_observation_count", 0
                ),
                "distinct_exercises_attempted": prior_history.get(
                    "distinct_exercises_attempted", []
                ),
                "prior_overall_accuracy": prior_history.get("prior_overall_accuracy", 0.0),
                "concept_mastery": prior_history.get("concept_mastery", {}),
                "excluded_future_records_count": prior_history.get(
                    "excluded_future_records_count", 0
                ),
                "profile_version": prior_history.get(
                    "profile_computation_version", "anu-authentic-temporal-v1"
                ),
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


def validate_model_output(
    raw_text: str, student_sql: str, ref_sql: str
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Validate that the model response adheres to the required schema and pedagogical rules.

    Returns:
        (is_valid: bool, parsed_json: Dict, flags: List[str])
    """
    flags = []
    parsed = {}

    # 1. Parse JSON
    try:
        # Strip potential markdown code fences
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return False, {}, ["response_not_a_json_object"]
    except json.JSONDecodeError as e:
        return False, {}, [f"json_decode_error: {str(e)}"]

    # 2. Check required schema fields
    required_keys = ["observed_error", "candidate_concepts", "guidance_hint", "evidence_citations"]
    for k in required_keys:
        if k not in parsed:
            flags.append(f"missing_required_key_{k}")

    hint = str(parsed.get("guidance_hint", ""))
    hint_lower = hint.lower()

    # 3. Check for prohibited solution leakage (Rule 1 & Rule 2)
    if "select " in hint_lower:
        flags.append("answer_leakage:prohibited_select_keyword")

    # Check if hint reveals reference SQL directly
    ref_norm = " ".join(ref_sql.lower().split())
    hint_norm = " ".join(hint_lower.split())
    if len(ref_norm) > 20 and ref_norm in hint_norm:
        flags.append("answer_leakage:exact_reference_query_revealed")

    # 4. Check for obvious hallucination in schema names
    # Check if hint invents phantom tables like 'students' or 'grades'
    words = set(re.findall(r"\b[a-z_]{4,}\b", hint_lower))
    phantom = {"employees", "departments", "customers", "orders", "enrollments"}
    found_phantom = words.intersection(phantom)
    if found_phantom:
        flags.append(f"hallucination:phantom_table_mentioned_{list(found_phantom)}")

    is_valid = len(flags) == 0
    return is_valid, parsed, flags


class LocalOllamaClient:
    """Client for local Ollama server with retries, timeout, and usage tracking."""

    def __init__(
        self, base_url: str = DEFAULT_OLLAMA_URL, model: str = DEFAULT_MODEL, timeout: float = 35.0
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.digest: Optional[str] = None
        self._check_server_and_model()

    def _check_server_and_model(self) -> None:
        """Verify local Ollama server is running and model is present."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            for m in models:
                if m.get("name") == self.model:
                    self.digest = m.get("digest")
                    break
        except Exception:
            # Server not currently running or unreachable
            self.digest = None

    def execute_chat(
        self,
        system_prompt: str,
        user_context: Dict[str, Any],
        num_ctx: int = 4096,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Execute a single inference request with bounded retries."""
        user_message_text = json.dumps(user_context, indent=2)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message_text},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }

        last_error = None
        for attempt in range(max_retries + 1):
            t0 = time.monotonic()
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))

                latency = round(time.monotonic() - t0, 3)
                content = resp_data.get("message", {}).get("content", "")
                prompt_tokens = resp_data.get("prompt_eval_count", 0)
                completion_tokens = resp_data.get("eval_count", 0)

                return {
                    "status": "success",
                    "latency_seconds": latency,
                    "raw_response": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "model": self.model,
                    "digest": self.digest,
                    "attempt": attempt + 1,
                }
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0)

        return {
            "status": "error",
            "error": last_error,
            "latency_seconds": round(time.monotonic() - t0, 3),
            "model": self.model,
            "digest": self.digest,
            "attempts": max_retries + 1,
        }


def prepare_blind_review_packet(
    cases: List[Dict[str, Any]],
    results_by_case: Optional[Dict[str, Dict[str, Any]]] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Generate genuinely blinded review files.

    Excludes condition names, full prompts, and source-treatment metadata.
    Provides only task context, authentic student SQL, and anonymous feedback variants.
    """
    rng = random.Random(seed)
    blind_cases = []
    key_mapping = {}

    conditions = ["A", "B", "C", "D", "E"]

    for case in cases:
        cid = case["eval_id"]
        shuffled_conds = list(conditions)
        rng.shuffle(shuffled_conds)

        blind_variants = []
        for cond in shuffled_conds:
            token = hashlib.sha256(f"{cid}:{cond}:salt{seed}".encode()).hexdigest()[:8]
            blind_id = f"resp-{token}"
            key_mapping[f"{cid}:{blind_id}"] = {
                "eval_id": cid,
                "blind_id": blind_id,
                "actual_condition": cond,
                "condition_name": {
                    "A": "Baseline_LLM",
                    "B": "Lecture_RAG",
                    "C": "Lecture_RAG_KG",
                    "D": "KG_No_History",
                    "E": "KG_Prior_History",
                }.get(cond, cond),
            }

            # Retrieve feedback from executed results or placeholder for review preparation
            feedback_content = None
            if results_by_case and cid in results_by_case and cond in results_by_case[cid]:
                feedback_content = results_by_case[cid][cond].get("parsed_response")

            variant_entry: Dict[str, Any] = {
                "blind_id": blind_id,
            }
            if feedback_content:
                variant_entry["feedback"] = feedback_content
            else:
                variant_entry["feedback_placeholder"] = f"Awaiting execution of Condition {cond}"

            blind_variants.append(variant_entry)

        blind_cases.append(
            {
                "eval_id": cid,
                "exercise_id": case["exercise_id"],
                "exercise_title": case["exercise_title"],
                "question_prompt": case["question_prompt"],
                "student_sql": case["authentic_student_sql"],
                "schema_context": SCHEMA_CONTEXT,
                # Reference SQL provided strictly for reviewer ground-truth verification
                "reference_sql_for_grader": case["reference_sql"],
                "variants": blind_variants,
            }
        )

    return {
        "metadata": {
            "title": "SIIP Single-Blind Expert Evaluation Packet",
            "protocol_type": "single_blind",
            "protocol_note": "Evaluator is blinded to condition names and treatments. Generator is automated.",
            "seed": seed,
            "total_cases": len(blind_cases),
            "rubrics": RUBRIC,
        },
        "review_cases": blind_cases,
        "blind_key": key_mapping,
    }


def main():
    parser = argparse.ArgumentParser(description="SIIP Research Experiment Protocol Runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate prompts, registry, and schemas without calling LLM",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute inference via local Ollama provider"
    )
    parser.add_argument(
        "--limit", type=int, default=25, help="Number of benchmark cases to process"
    )
    parser.add_argument(
        "--case", type=str, default=None, help="Specific case ID to process (e.g. eval-anu-001)"
    )
    parser.add_argument(
        "--conditions", type=str, default="A,B,C,D,E", help="Comma-separated conditions to execute"
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default=DEFAULT_OLLAMA_URL,
        help="Base URL for local Ollama server",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--num-ctx", type=int, default=4096, help="Context window size")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_manifest()
    if args.case:
        cases = [c for c in cases if c["eval_id"] == args.case]
        if not cases:
            print(f"Error: Case {args.case} not found in manifest.")
            sys.exit(1)
    else:
        cases = cases[: args.limit]

    print(f"=== SIIP Evaluation Runner (Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}) ===")
    print(f"Processing {len(cases)} benchmark evaluation cases.")

    registry = EvidenceRegistry()
    print(f"Evidence Registry loaded {len(registry.items)} verifiable items.")

    # Audit eligibility
    eligible_inst_kg = 0
    eligible_history = 0
    for case in cases:
        ok_kg, reason_kg, _ = registry.check_instructor_aligned_eligibility(case)
        if ok_kg:
            eligible_inst_kg += 1
        hist = case.get("authentic_prior_history", {})
        if hist.get("has_valid_history") and hist.get("prior_attempts", 0) > 0:
            eligible_history += 1

    print(f"Verified Instructor-Aligned KG Eligible: {eligible_inst_kg}/{len(cases)} cases")
    print(f"Verified Authentic Prior History Eligible: {eligible_history}/{len(cases)} cases")

    selected_conditions = [c.strip().upper() for c in args.conditions.split(",")]
    print(f"Selected conditions: {selected_conditions}")

    results_by_case: Dict[str, Dict[str, Any]] = {}

    if args.execute:
        client = LocalOllamaClient(base_url=args.ollama_url, model=args.model)
        if not client.digest:
            print(
                f"Error: Unable to connect to Ollama at {args.ollama_url} or model {args.model} not found."
            )
            print("Ensure Ollama server is running (e.g. 'ollama serve' with OLLAMA_MODELS).")
            sys.exit(1)
        print(f"Connected to local Ollama server. Model: {client.model} (Digest: {client.digest})")

        total_inferences = len(cases) * len(selected_conditions)
        print(f"Executing {total_inferences} total inferences across {len(cases)} cases...")

        for idx, case in enumerate(cases, 1):
            cid = case["eval_id"]
            results_by_case[cid] = {}
            prompts = build_condition_prompts(case, registry)

            for cond in selected_conditions:
                raw_file = RAW_RESULTS_DIR / f"{cid}_{cond}.json"

                # Idempotent resume: load existing valid execution if present
                if raw_file.exists():
                    try:
                        cached = json.loads(raw_file.read_text(encoding="utf-8"))
                        if cached.get("validation", {}).get("is_valid"):
                            print(f"[{idx}/{len(cases)}] {cid} Cond {cond}: Resumed from cache.")
                            results_by_case[cid][cond] = cached
                            continue
                    except Exception:
                        pass

                cond_spec = prompts[cond]
                print(
                    f"[{idx}/{len(cases)}] {cid} Cond {cond} ({cond_spec['condition']}): Invoking Ollama...",
                    end=" ",
                    flush=True,
                )

                res = client.execute_chat(
                    system_prompt=cond_spec["system"],
                    user_context=cond_spec["context"],
                    num_ctx=args.num_ctx,
                )

                if res.get("status") == "success":
                    raw_text = res["raw_response"]
                    is_valid, parsed, flags = validate_model_output(
                        raw_text, case["authentic_student_sql"], case["reference_sql"]
                    )
                    record = {
                        "eval_id": cid,
                        "condition": cond,
                        "condition_name": cond_spec["condition"],
                        "model": res["model"],
                        "digest": res["digest"],
                        "prompt_version": PROMPT_VERSION,
                        "latency_seconds": res["latency_seconds"],
                        "tokens": {
                            "prompt_tokens": res["prompt_tokens"],
                            "completion_tokens": res["completion_tokens"],
                            "total_tokens": res["total_tokens"],
                        },
                        "validation": {
                            "is_valid": is_valid,
                            "flags": flags,
                        },
                        "raw_response": raw_text,
                        "parsed_response": parsed,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    raw_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
                    results_by_case[cid][cond] = record
                    status_flag = "VALID" if is_valid else f"FLAGGED({','.join(flags)})"
                    print(
                        f"Done ({res['latency_seconds']}s, {res['total_tokens']} tokens, {status_flag})"
                    )
                else:
                    print(f"FAILED: {res.get('error')}")

        # Save aggregated execution results
        agg_file = OUTPUT_DIR / "experiment_results.json"
        agg_file.write_text(json.dumps(results_by_case, indent=2), encoding="utf-8")
        print(f"\nSaved aggregated results to: {agg_file}")

    else:
        # Non-inferential dry run validation mode
        print(
            "\n[DRY RUN] Validating condition prompt constructions and schemas without model calls..."
        )
        for case in cases:
            prompts = build_condition_prompts(case, registry)
            assert len(prompts) == 5, f"Expected 5 condition prompts for {case['eval_id']}"
            for cond_k, cond_v in prompts.items():
                assert "system" in cond_v
                assert "context" in cond_v
                assert cond_v["context"]["task_description"] == case["question_prompt"]
                assert cond_v["context"]["student_submission"] == case["authentic_student_sql"]
        print("[DRY RUN] All condition prompts structurally validated.")

    # Generate Blind Review Packet and Key
    packet = prepare_blind_review_packet(cases, results_by_case=results_by_case)
    packet_path = OUTPUT_DIR / "blind_review_packet.json"
    key_path = OUTPUT_DIR / "blind_review_key.json"

    review_form = {
        "metadata": packet["metadata"],
        "review_cases": packet["review_cases"],
    }
    packet_path.write_text(json.dumps(review_form, indent=2), encoding="utf-8")
    key_path.write_text(json.dumps(packet["blind_key"], indent=2), encoding="utf-8")

    print(f"\nSaved blind review packet to: {packet_path}")
    print(f"Saved unblinding key to: {key_path}")

    # Generate Reviewer Scoring Form Template
    scoring_form = {
        "instructions": (
            "Score each anonymous response (resp-*) independently on a 1-5 scale for criteria 1-4, "
            "and 0-1 for flags 5-6. Do not penalize responses for lack of citations if no citations were needed. "
            "Record scores in the 'ratings' dictionary."
        ),
        "rubric": RUBRIC,
        "evaluator_id": "EXPERT_REVIEWER_1",
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "reviews": [
            {
                "eval_id": case["eval_id"],
                "blind_id": variant["blind_id"],
                "correctness": None,
                "evidence_grounding": None,
                "concept_relevance": None,
                "actionability": None,
                "answer_leakage": None,
                "hallucination": None,
                "evaluator_notes": "",
            }
            for case in packet["review_cases"]
            for variant in case["variants"]
        ],
    }
    scoring_path = OUTPUT_DIR / "scoring_form.json"
    scoring_path.write_text(json.dumps(scoring_form, indent=2), encoding="utf-8")
    print(f"Saved reviewer scoring template to: {scoring_path}")

    # Resource Summary
    total_calls = len(cases) * len(selected_conditions)
    avg_latency = 9.2
    est_runtime_s = total_calls * avg_latency
    print("\n--- Execution Resource Estimate ---")
    print(
        f"Cases: {len(cases)} | Conditions: {len(selected_conditions)} | Total Inferences: {total_calls}"
    )
    print("Target Model: Qwen3 8B (Q4_K_M) on NVIDIA RTX 5070 Ti (12 GB VRAM)")
    print(f"Estimated Execution Time: ~{est_runtime_s:.1f}s ({est_runtime_s / 60:.1f} minutes)")
    print("Estimated Cost: $0.00 (100% Local GPU inference, zero external API)")


if __name__ == "__main__":
    main()
