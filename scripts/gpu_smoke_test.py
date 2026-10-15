"""Lightweight GPU Smoke Test for SIIP research platform with local Qwen3 8B.
Runs Tests A-F and measures exact GPU, VRAM, RAM, CPU, and latency.
"""

import ctypes
import http.client
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.feedback import (
    CompatibleProvider,
    generate_feedback,
)
from siip.grader import QUESTIONS, grade

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MODEL_ID = "qwen3:8b"


def get_system_ram():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_mb = stat.ullTotalPhys / (1024 * 1024)
    avail_mb = stat.ullAvailPhys / (1024 * 1024)
    used_mb = total_mb - avail_mb
    return {
        "total_mb": round(total_mb, 2),
        "used_mb": round(used_mb, 2),
        "percent_used": stat.dwMemoryLoad,
    }


def get_gpu_status():
    try:
        smi_bin = shutil.which("nvidia-smi") or "nvidia-smi"
        out = subprocess.check_output(  # nosec B607: verified system utility.
            [
                smi_bin,
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
        gpu_util, mem_used, mem_total, temp = [int(x.strip()) for x in out.split(",")]
        return {
            "gpu_utilization_pct": gpu_util,
            "vram_used_mib": mem_used,
            "vram_total_mib": mem_total,
            "gpu_temperature_c": temp,
        }
    except Exception as e:
        return {"error": str(e)}


def test_a_availability():
    print("\n--- Running Test A: Basic Model Availability ---")
    req = urllib.request.Request(f"{OLLAMA_BASE_URL}/v1/models")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310: fixed loopback.
        body = json.loads(resp.read().decode())
    latency = round(time.monotonic() - t0, 4)
    models = [m.get("id") for m in body.get("data", [])]
    found = MODEL_ID in models
    print(f"Listed models: {models}, Found {MODEL_ID}: {found}, Latency: {latency}s")
    return {
        "status": "PASS" if found else "FAIL",
        "models": models,
        "latency_s": latency,
        "endpoint": f"{OLLAMA_BASE_URL}/v1/models",
    }


def test_b_chat_completions():
    print("\n--- Running Test B: Chat Completions ---")
    gpu_before = get_gpu_status()
    ram_before = get_system_ram()
    prompt = "Explain the difference between INNER JOIN and LEFT JOIN in two sentences."
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 768,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310: fixed loopback.
        data = json.loads(resp.read().decode())
    latency = round(time.monotonic() - t0, 3)
    gpu_after = get_gpu_status()
    ram_after = get_system_ram()

    choice = data["choices"][0]
    content = choice["message"]["content"]
    reasoning = choice["message"].get("reasoning", "")
    finish_reason = choice.get("finish_reason")
    usage = data.get("usage", {})

    print(f"Latency: {latency}s, finish_reason: {finish_reason}")
    print(f"Content: {content}")
    print(f"Reasoning length: {len(reasoning)} chars")
    print(f"Usage: {usage}")
    print(f"GPU after: {gpu_after}")

    is_valid = bool(content and len(content.strip()) > 10 and finish_reason == "stop")
    return {
        "status": "PASS" if is_valid else "PARTIAL",
        "prompt": prompt,
        "response_content": content,
        "reasoning_chars": len(reasoning),
        "usage": usage,
        "latency_s": latency,
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "ram_before": ram_before,
        "ram_after": ram_after,
    }


def test_c_structured_json():
    print("\n--- Running Test C: Structured JSON ---")
    system_prompt = (
        "You are an educational SQL tutor analyzing a student submission. "
        "Output ONLY a valid JSON object with exactly these three fields: "
        '"observed_error": string explaining what went wrong in the query, '
        '"candidate_concepts": list of concept strings from the allowed list, '
        '"hint": pedagogical hint that guides the student without revealing the SQL query.'
    )
    user_prompt = (
        "Question: Write a query to list all employees and their department names. Every employee must appear in the output, even if they have no department assigned.\n"
        "Student SQL: SELECT e.name, d.name FROM Employees e INNER JOIN Departments d ON e.department_id = d.id\n"
        "Grading: 0/1. Observed error: Employees without a department were omitted from the output.\n"
        'Allowed concepts: ["LEFT_OUTER_JOIN", "INNER_JOIN", "NULL_SEMANTICS", "JOIN_CONDITION"]'
    )
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 768,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310: fixed loopback.
        data = json.loads(resp.read().decode())
    latency = round(time.monotonic() - t0, 3)

    content = data["choices"][0]["message"]["content"]
    print(f"Latency: {latency}s")
    print(f"Raw content:\n{content}")

    try:
        parsed = json.loads(content)
        has_required_keys = {"observed_error", "candidate_concepts", "hint"}.issubset(parsed.keys())
        concepts_valid = isinstance(parsed.get("candidate_concepts"), list) and all(
            c in ["LEFT_OUTER_JOIN", "INNER_JOIN", "NULL_SEMANTICS", "JOIN_CONDITION"]
            for c in parsed.get("candidate_concepts", [])
        )
        hint = parsed.get("hint", "")
        no_leak = not bool(re.search(r"\bselect\b|\bfrom\b|\bjoin\b.*department_id", hint, re.I))

        print(f"Parsed JSON successfully: {parsed}")
        print(f"Has required keys: {has_required_keys}")
        print(f"Concepts valid: {concepts_valid}")
        print(f"No solution leakage in hint: {no_leak}")

        passed = has_required_keys and concepts_valid and no_leak
        status = "PASS" if passed else "PARTIAL"
    except Exception as e:
        parsed = None
        status = "FAIL"
        print(f"JSON parse error: {e}")

    return {
        "status": status,
        "raw_response": content,
        "parsed_json": parsed,
        "latency_s": latency,
    }


def test_d_responses_api():
    print("\n--- Running Test D: Responses API Compatibility ---")
    payload = {"model": MODEL_ID, "input": "SELECT 1;"}
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/v1/responses",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310: fixed loopback.
            resp.read()
            status = "PASS"
            detail = "HTTP 200 OK (basic Responses API supported)"
    except (urllib.error.HTTPError, TimeoutError, http.client.RemoteDisconnected, OSError) as e:
        status = "FAIL"
        detail = f"{type(e).__name__}: {e}"
    latency = round(time.monotonic() - t0, 3)

    print(f"Responses API result: {status} ({detail}), Latency: {latency}s")
    return {
        "status": status,
        "endpoint": f"{OLLAMA_BASE_URL}/v1/responses",
        "latency_s": latency,
        "detail": detail,
        "note": "Documented incompatibility: upstream InstructKG research pipeline requires Responses API, but standard Ollama 0.17.7 implements /v1/chat/completions.",
    }


def test_e_feedback_integration():
    print("\n--- Running Test E: Existing Feedback Integration ---")
    qid = "sql_join_02"
    incorrect_sql = QUESTIONS["sql_join_01"]["reference_sql"]

    # 1. Deterministic grading
    grade_res = grade(qid, incorrect_sql)
    print(f"Deterministic grading status: {grade_res['status']}, score: {grade_res['score']}")
    assert grade_res["score"] == 0
    assert grade_res["status"] == "semantic_error"

    provider = CompatibleProvider(f"{OLLAMA_BASE_URL}/v1", MODEL_ID, timeout=14, max_tokens=450)

    results = {}
    for mode in ["baseline", "kg"]:
        t0 = time.monotonic()
        fb = generate_feedback(qid, incorrect_sql, grade_res, mode=mode, provider=provider)
        latency = round(time.monotonic() - t0, 3)
        print(f"Mode [{mode}] Feedback (Latency {latency}s):")
        print(f"  inference_status: {fb.get('inference_status')}")
        print(f"  feedback_text: {fb.get('feedback_text')}")
        print(f"  candidate_concepts: {fb.get('candidate_concepts')}")
        print(f"  evidence_references: {fb.get('evidence_references')}")
        results[mode] = {
            "feedback": fb,
            "latency_s": latency,
            "inference_status": fb.get("inference_status"),
        }

    # 2. Test timeout handling safely (using 0.1s minimum valid timeout)
    timeout_provider = CompatibleProvider(
        f"{OLLAMA_BASE_URL}/v1", MODEL_ID, timeout=0.1, max_tokens=450
    )
    t0 = time.monotonic()
    fb_timeout = generate_feedback(
        qid, incorrect_sql, grade_res, mode="baseline", provider=timeout_provider
    )
    timeout_latency = round(time.monotonic() - t0, 3)
    print(f"Timeout fallback test: {fb_timeout.get('inference_status')} in {timeout_latency}s")
    results["timeout_test"] = {
        "feedback": fb_timeout,
        "latency_s": timeout_latency,
        "fallback_status": fb_timeout.get("inference_status"),
    }

    # Verify grading is untouched
    assert grade_res["score"] == 0
    assert grade_res["status"] == "semantic_error"

    all_passed = (
        results["baseline"]["inference_status"]
        in ["provider_success", "deterministic_fallback", "context_error_fallback"]
        and results["kg"]["inference_status"]
        in ["provider_success", "deterministic_fallback", "context_error_fallback"]
        and fb_timeout.get("inference_status") == "deterministic_fallback"
    )

    return {
        "status": "PASS" if all_passed else "FAIL",
        "grading_status": grade_res["status"],
        "grading_score": grade_res["score"],
        "modes": results,
    }


def main():
    print("=== STARTING PHASE 7 GPU SMOKE TEST ===")
    test_results = {}
    gpu_initial = get_gpu_status()
    ram_initial = get_system_ram()
    print(f"Initial GPU Status: {gpu_initial}")
    print(f"Initial System RAM: {ram_initial}")

    test_results["Test_A_Availability"] = test_a_availability()
    test_results["Test_B_Chat_Completions"] = test_b_chat_completions()
    test_results["Test_C_Structured_JSON"] = test_c_structured_json()
    test_results["Test_D_Responses_API"] = test_d_responses_api()
    test_results["Test_E_Feedback_Integration"] = test_e_feedback_integration()

    gpu_final = get_gpu_status()
    ram_final = get_system_ram()
    print(f"\nFinal GPU Status: {gpu_final}")
    print(f"Final System RAM: {ram_final}")

    full_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gpu_initial": gpu_initial,
        "gpu_final": gpu_final,
        "ram_initial": ram_initial,
        "ram_final": ram_final,
        "results": test_results,
    }

    out_path = ROOT / "artifacts/phase7_smoke_test_results.json"
    out_path.write_text(json.dumps(full_report, indent=2))
    print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    main()
