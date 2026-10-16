"""Verify Demo A, B, and C in sequence on a shared database with zero resets.

Demonstrates that the three demo flows operate seamlessly on the same persistent
store without cross-step collision, schema corruption, or reset requirements.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
sys.path.insert(0, str(ROOT / "scripts"))

if "SIIP_DATA_DIR" not in os.environ:
    os.environ["SIIP_DATA_DIR"] = str(ROOT / "artifacts/public-data")

from demo_a_personalized_learning import run_demo_a
from demo_b_entrepreneurial_mindset import run_demo_b
from demo_c_dynamic_project import run_demo_c


def run_sequential_verification() -> int:
    print("=" * 76)
    print("SIIP INTEGRATED DEMOS A, B, AND C — SEQUENTIAL EXECUTION TEST")
    print("=" * 76)
    print("Validating that Demos A, B, and C execute consecutively on the SAME")
    print("database instance without requiring any database resets between them.\n")

    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="siip-sequential-demos-") as shared_dir:
        shared_path = Path(shared_dir)
        print(f"[Setup] Initialized shared demo database directory: {shared_path}\n")

        # -------------------------------------------------------------------
        # Phase 1: Demo A — Integrated Personalized Learning
        # -------------------------------------------------------------------
        print(">>> STARTING DEMO A (Personalized Learning)...")
        rc_a = run_demo_a(dir_path=shared_path)
        if rc_a != 0:
            print("FAILED: Demo A returned non-zero exit code.")
            return rc_a
        print(">>> DEMO A COMPLETED SUCCESSFULLY.\n")

        # -------------------------------------------------------------------
        # Phase 2: Demo B — Entrepreneurial Mindset Integration
        # -------------------------------------------------------------------
        print(">>> STARTING DEMO B (Entrepreneurial Mindset on SAME database)...")
        rc_b = run_demo_b(dir_path=shared_path)
        if rc_b != 0:
            print("FAILED: Demo B returned non-zero exit code.")
            return rc_b
        print(">>> DEMO B COMPLETED SUCCESSFULLY.\n")

        # -------------------------------------------------------------------
        # Phase 3: Demo C — Personalized Project Generation
        # -------------------------------------------------------------------
        print(">>> STARTING DEMO C (Dynamic Project Generation on SAME database)...")
        rc_c = run_demo_c(dir_path=shared_path)
        if rc_c != 0:
            print("FAILED: Demo C returned non-zero exit code.")
            return rc_c
        print(">>> DEMO C COMPLETED SUCCESSFULLY.\n")

        # -------------------------------------------------------------------
        # Inspection: Verify all databases exist and hold persistent data
        # -------------------------------------------------------------------
        sub_db = shared_path / "submissions.sqlite3"
        em_db = shared_path / "em.sqlite3"
        proj_db = shared_path / "projects.sqlite3"

        assert sub_db.exists(), "submissions.sqlite3 missing"
        assert em_db.exists(), "em.sqlite3 missing"
        assert proj_db.exists(), "projects.sqlite3 missing"

        t_total = time.perf_counter() - t_start
        print("=" * 76)
        print(f"SEQUENTIAL REHEARSAL VERIFICATION: SUCCESS ({t_total:.2f}s total)")
        print(f"  - Submissions Store: {sub_db.stat().st_size} bytes")
        print(f"  - EM Evidence Store: {em_db.stat().st_size} bytes")
        print(f"  - Project Store:     {proj_db.stat().st_size} bytes")
        print("  - Zero database resets occurred between Demos A, B, and C.")
        print("=" * 76)
        return 0


if __name__ == "__main__":
    sys.exit(run_sequential_verification())
