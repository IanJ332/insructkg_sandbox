"""Actual local PL UI → grade → feedback → CSV → atomic storage → analytics.

Run only with --ack-local-synthetic. Traces/screenshots/exports remain ignored locally.
No API key, model, real course or raw database write is used.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prairielearn-course/serverFilesCourse"))
from siip.grader import QUESTIONS
from siip.ingestion import import_local_csv
from siip.store import SubmissionRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ack-local-synthetic", action="store_true", required=True)
    parser.add_argument("--base-url", default="http://localhost:3000")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.scheme != "http":
        raise SystemExit("This automated demo is restricted to the local synthetic sandbox")
    out = ROOT / "artifacts/phase2/e2e"
    out.mkdir(parents=True, exist_ok=True)
    repo = SubmissionRepository(
        Path(os.environ.get("SIIP_DB_PATH") or ROOT / "artifacts/synthetic.sqlite3")
    )
    previous_ids = {r["attempt_id"] for r in repo.records()}
    before = repo.analytics()["attempt_count"]
    evidence = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 960})
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            print("E2E: loading local PrairieLearn", flush=True)
            page.goto(args.base_url + "/pl")
            menu = page.locator("#course-nav-toggler")
            if menu.is_visible():
                menu.click()
            page.locator("#navbar-load-from-disk").click()
            expect(page.get_by_text("Success", exact=True)).to_be_visible(timeout=60000)
            page.goto(args.base_url + "/pl")
            page.get_by_role("link", name="Fall 2026 Synthetic Sandbox", exact=True).click()
            link = page.get_by_role("link", name="SQL Concept-Aware Feedback Sandbox", exact=True)
            href = link.get_attribute("href")
            if not href:
                raise AssertionError("Missing assessment route")
            # The downloads link is derived from this observed local assessment, never a guessed course.
            assessment_path = href.rstrip("/")
            link.click()
            page.locator("#navbarDropdown").click()
            page.locator("#navbar-user-view-authn-student").click()
            expect(
                page.get_by_role(
                    "heading", name="HW1: SQL Concept-Aware Feedback Sandbox", exact=True
                )
            ).to_be_visible()
            overview = page.url
            qlinks = {
                qid: page.get_by_role("link", name=title, exact=True).get_attribute("href")
                for qid, title in {
                    "sql_join_01": "HW1.1. Matching employees and departments",
                    "sql_join_02": "HW1.2. Keep every employee",
                    "sql_join_03": "HW1.3. Find employees without a department match",
                }.items()
            }
            sequence = [
                ("sql_join_01", QUESTIONS["sql_join_01"]["reference_sql"], "correct"),
                ("sql_join_02", QUESTIONS["sql_join_01"]["reference_sql"], "semantic_error"),
                ("sql_join_02", QUESTIONS["sql_join_02"]["reference_sql"], "correct"),
                (
                    "sql_join_03",
                    "SELECT name FROM Employees WHERE department_id IS NULL",
                    "semantic_error",
                ),
                ("sql_join_03", QUESTIONS["sql_join_03"]["reference_sql"], "correct"),
            ]
            for index, (qid, sql, status) in enumerate(sequence, 1):
                target = qlinks[qid]
                if not target:
                    raise AssertionError("Missing question route")
                page.goto(args.base_url + target if target.startswith("/") else target)
                bodies = page.locator('[id^="submission-"][id$="-body"]')
                before_id = bodies.first.get_attribute("id") if bodies.count() else None
                page.get_by_role("textbox", name="SQL query", exact=True).fill(sql)
                page.get_by_role("textbox", name="SQL query", exact=True).press("Tab")
                page.get_by_role("button", name=re.compile("Save & Grade")).click()
                newest = page.locator('[id^="submission-"][id$="-body"]').first
                if before_id:
                    expect(newest).not_to_have_attribute("id", before_id)
                expect(newest).to_contain_text(status)
                expect(newest).to_contain_text("deterministic_fallback")
                sid = newest.get_attribute("id")
                path = out / f"{index}-{qid}-{status}.png"
                page.screenshot(path=str(path), full_page=True)
                print(f"E2E: {qid} {status} {sid}", flush=True)
                evidence.append(
                    {
                        "question": qid,
                        "expected_status": status,
                        "submission_dom_id": sid,
                        "screenshot": str(path.relative_to(ROOT)),
                    }
                )
            page.goto(overview)
            expect(page.get_by_role("main")).to_contain_text(
                re.compile(r"Total\s+points:\s*3\s*/\s*3")
            )
            page.screenshot(path=str(out / "assessment.png"), full_page=True)
            # Authorized, supported instructor UI export; no PAT creation or internal DB writes.
            page.goto(args.base_url + assessment_path + "/downloads")
            export = page.get_by_role("link", name=re.compile("_all_submissions.csv$"))
            with page.expect_download() as information:
                export.click()
            downloaded = information.value
            csv_path = out / "local-pl-export.csv"
            downloaded.save_as(csv_path)
            print("E2E: importing supported local CSV export", flush=True)
            imported = import_local_csv(repo, csv_path)
            added = {r["attempt_id"] for r in imported} - previous_ids
            after = repo.analytics()["attempt_count"]
            assert len(added) >= 5 and after == before + len(added)
            with urllib.request.urlopen(
                "http://127.0.0.1:8080/api/analytics", timeout=15
            ) as response:  # nosec B310: fixed loopback.
                analytics = json.load(response)
            assert analytics["attempt_count"] == after
            page.goto("http://127.0.0.1:8080/students?id=S003")
            expect(
                page.get_by_role("heading", name="S003 · synthetic learning history", exact=True)
            ).to_be_visible()
            page.screenshot(path=str(out / "profile.png"), full_page=True)
            report = {
                "status": "PASS",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "actual_local_prairielearn_ui_and_supported_csv_import",
                "browser_submissions": evidence,
                "record_count_before": before,
                "record_count_after": after,
                "new_pl_attempt_ids": sorted(added),
                "live_model_calls": 0,
                "course_data": "synthetic students only",
            }
            (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
        finally:
            context.tracing.stop(path=str(out / "trace.zip"))
            browser.close()


if __name__ == "__main__":
    main()
