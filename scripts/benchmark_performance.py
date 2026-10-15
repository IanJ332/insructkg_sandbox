"""Empirical performance benchmark measuring exact subsystem latencies.
Measures:
1. Raw in-process SQLite execution time.
2. Subprocess spawning overhead for sql_worker.py.
3. Complete grade() end-to-end latency across datasets A & B.
4. SQLite job queue throughput (enqueue, claim, concurrent read/write).
5. Queue wait time under simulated worker load.
6. Local LLM generation time (Qwen3 8B on Ollama 11434).
7. End-to-end feedback availability lifecycle.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))

from siip.feedback import configured_provider, generate_feedback
from siip.grader import DATA, QUESTIONS, grade, run_query
from siip.jobs import FeedbackJobRepository, FeedbackWorker


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = int(k)
    c = f + 1
    if c < len(sorted_v):
        return round(sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f]), 3)
    return round(sorted_v[f], 3)


def measure_sql_execution(n=50):
    """Direct in-memory SQLite query execution time (no subprocess)."""
    schema = (DATA / "dataset_A.sql").read_text()
    sql = QUESTIONS["sql_join_02"]["reference_sql"]
    latencies = []
    for _ in range(n):
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema)
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.fetchall()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        conn.close()
    return {
        "iterations": n,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def measure_subprocess_overhead(n=20):
    """Measures process creation overhead for running sql_worker.py."""
    sql = QUESTIONS["sql_join_01"]["reference_sql"]
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        res = run_query(sql, "A")
        t1 = time.perf_counter()
        if res.get("status") == "ok":
            latencies.append((t1 - t0) * 1000.0)
    return {
        "iterations": len(latencies),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def measure_complete_grade_latency(n=20):
    """Measures complete grade() call (datasets A & B, subprocesses, row bags, observation)."""
    sql = QUESTIONS["sql_join_02"]["reference_sql"]
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        res = grade("sql_join_02", sql)
        t1 = time.perf_counter()
        if res.get("score") == 1:
            latencies.append((t1 - t0) * 1000.0)
    return {
        "iterations": len(latencies),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def measure_sqlite_queue_throughput(n=500):
    """Measures SQLite job queue throughput in WAL mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench_jobs.sqlite3"
        repo = FeedbackJobRepository(db_path, max_queue_size=n + 500)

        # 1. Enqueue throughput
        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        t0 = time.perf_counter()
        for i in range(n):
            repo.enqueue(f"att-{i}", f"S{i % 5:03d}", "sql_join_02", f"SELECT {i};", grading)
        t1 = time.perf_counter()
        enqueue_duration = t1 - t0
        enqueue_ops_sec = round(n / enqueue_duration, 1)

        # 2. Claim throughput
        t0 = time.perf_counter()
        claimed = 0
        while True:
            job = repo.claim("worker-bench")
            if not job:
                break
            claimed += 1
        t1 = time.perf_counter()
        claim_duration = t1 - t0
        claim_ops_sec = round(claimed / claim_duration, 1)

        # 3. Concurrent reads/writes with WAL mode
        # 4 reader threads querying stats / jobs + 1 writer enqueuing
        read_ops = [0]
        write_ops = [0]
        stop = False

        def reader():
            while not stop:
                repo.stats()
                read_ops[0] += 1
                time.sleep(0.001)

        def writer():
            idx = n
            while not stop and idx < n + 200:
                repo.enqueue(f"att-concur-{idx}", "S001", "sql_join_01", "SELECT 1;", grading)
                idx += 1
                write_ops[0] += 1
                time.sleep(0.002)

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(reader) for _ in range(3)]
            futures.append(pool.submit(writer))
            time.sleep(1.0)
            stop = True
            for f in futures:
                f.result()
        concurrent_duration = time.perf_counter() - t0

    return {
        "enqueues_measured": n,
        "enqueue_ops_per_sec": enqueue_ops_sec,
        "claim_ops_per_sec": claim_ops_sec,
        "concurrent_wal_ops_per_sec": round((read_ops[0] + write_ops[0]) / concurrent_duration, 1),
        "concurrent_reads": read_ops[0],
        "concurrent_writes": write_ops[0],
    }


def measure_llm_generation_time():
    """Measures real Ollama Qwen3 8B generation latency if server is running."""
    provider = configured_provider()
    if not provider:
        return {"status": "skipped", "reason": "No provider configured"}

    grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
    sql = "SELECT e.name, d.department_name FROM Employees e INNER JOIN Departments d ON e.department_id = d.department_id;"

    t0 = time.perf_counter()
    try:
        feedback = generate_feedback("sql_join_02", sql, grading, mode="kg", provider=provider)
        t1 = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000.0, 2)
        return {
            "status": "measured",
            "model": feedback.get("model_identifier"),
            "inference_status": feedback.get("inference_status"),
            "latency_ms": latency_ms,
            "has_feedback_text": bool(feedback.get("feedback_text")),
            "feedback_length_chars": len(feedback.get("feedback_text", "")),
        }
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def measure_end_to_end_lifecycle():
    """Measures the full lifecycle: enqueue -> worker claim -> inference -> complete -> retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "e2e_bench_jobs.sqlite3"
        repo = FeedbackJobRepository(db_path)
        worker = FeedbackWorker(repo, worker_id="worker-e2e")
        provider = configured_provider()

        grading = {"status": "semantic_error", "score": 0, "observation": "missing_unmatched_rows"}
        sql = "SELECT name FROM Employees e;"

        # Step 1: Enqueue
        t_start = time.perf_counter()
        t0 = time.perf_counter()
        job = repo.enqueue("att-e2e-bench", "S001", "sql_join_02", sql, grading, mode="kg")
        t_enqueued = time.perf_counter()
        enqueue_latency_ms = round((t_enqueued - t0) * 1000.0, 3)

        # Step 2: Queue wait + worker process
        t_claim_start = time.perf_counter()
        completed_job = worker.process_one(provider=provider)
        t_completed = time.perf_counter()
        process_latency_ms = round((t_completed - t_claim_start) * 1000.0, 3)

        # Step 3: Learner retrieval
        t_retrieve_start = time.perf_counter()
        retrieved = repo.get_for_student(job.job_id, "S001")
        assert retrieved is not None
        t_retrieved = time.perf_counter()
        retrieve_latency_ms = round((t_retrieved - t_retrieve_start) * 1000.0, 3)

        total_lifecycle_ms = round((t_retrieved - t_start) * 1000.0, 3)

        return {
            "enqueue_latency_ms": enqueue_latency_ms,
            "worker_processing_latency_ms": process_latency_ms,
            "learner_retrieval_latency_ms": retrieve_latency_ms,
            "total_end_to_end_ms": total_lifecycle_ms,
            "job_status": completed_job.status if completed_job else "None",
            "model_identifier": completed_job.model_identifier if completed_job else "None",
        }


def main():
    print("=" * 70)
    print("SIIP Phase 4.1 Empirical Subsystem Performance Measurement")
    print("=" * 70, flush=True)

    print("1. Measuring raw in-process SQLite execution time...", flush=True)
    sql_bench = measure_sql_execution()
    print(f"   -> P50: {sql_bench['p50_ms']} ms | P95: {sql_bench['p95_ms']} ms")

    print("2. Measuring subprocess creation overhead (sql_worker.py)...", flush=True)
    subproc_bench = measure_subprocess_overhead()
    print(f"   -> P50: {subproc_bench['p50_ms']} ms | P95: {subproc_bench['p95_ms']} ms")

    print("3. Measuring complete grade() latency (Datasets A & B + observation)...", flush=True)
    grade_bench = measure_complete_grade_latency()
    print(f"   -> P50: {grade_bench['p50_ms']} ms | P95: {grade_bench['p95_ms']} ms")

    print("4. Measuring SQLite WAL feedback job queue throughput...", flush=True)
    queue_bench = measure_sqlite_queue_throughput()
    print(f"   -> Enqueue: {queue_bench['enqueue_ops_per_sec']} ops/sec")
    print(f"   -> Claim: {queue_bench['claim_ops_per_sec']} ops/sec")
    print(f"   -> Concurrent WAL: {queue_bench['concurrent_wal_ops_per_sec']} ops/sec")

    print("5. Measuring local LLM generation time (Qwen3 8B via Ollama)...", flush=True)
    llm_bench = measure_llm_generation_time()
    print(
        f"   -> Status: {llm_bench.get('status')} | Latency: {llm_bench.get('latency_ms', 'N/A')} ms"
    )

    print("6. Measuring complete end-to-end feedback availability lifecycle...", flush=True)
    e2e_bench = measure_end_to_end_lifecycle()
    print(f"   -> Total End-to-End: {e2e_bench['total_end_to_end_ms']} ms")
    print(f"   -> Queue Enqueue: {e2e_bench['enqueue_latency_ms']} ms")
    print(f"   -> Worker Processing: {e2e_bench['worker_processing_latency_ms']} ms")
    print(f"   -> Learner Retrieval: {e2e_bench['learner_retrieval_latency_ms']} ms")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "raw_sqlite_execution": sql_bench,
        "subprocess_overhead": subproc_bench,
        "complete_grading": grade_bench,
        "sqlite_queue_throughput": queue_bench,
        "llm_generation": llm_bench,
        "end_to_end_lifecycle": e2e_bench,
    }

    out_file = ROOT / "artifacts/performance_benchmark.json"
    out_file.write_text(json.dumps(report, indent=2) + "\n")
    print("=" * 70)
    print(f"Full benchmark written to {out_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
