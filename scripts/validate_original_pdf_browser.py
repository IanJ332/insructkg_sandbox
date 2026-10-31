"""Opt-in live original PDF pipeline proof through instructor browser controls."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/original-integration")
parser.add_argument("--base-url", default="http://127.0.0.1:8831")
args = parser.parse_args()
OUT = args.output_dir.resolve()
BASE = args.base_url.rstrip("/")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(20000)
    page.goto(BASE + "/login")
    page.locator('[name="principal"]').select_option("instructor_alawini")
    page.get_by_role("button", name="Sign In to Demo Session").click()
    page.goto(BASE + "/authoring")
    if (
        page.locator('form[action="/api/demo/lessons/upload"] [name="module_id"] option').count()
        == 0
    ):
        course = page.locator('form[action="/api/demo/courses/create"]')
        course.locator('[name="course_id"]').fill("intro-relational-databases")
        course.locator('[name="title"]').fill("Synthetic SQL integration")
        with page.expect_navigation():
            course.get_by_role("button").click()
        module = page.locator('form[action="/api/demo/modules/create"]')
        module.locator('[name="module_id"]').fill("sql-joins")
        module.locator('[name="title"]').fill("Synthetic joins and counts")
        with page.expect_navigation():
            module.get_by_role("button").click()
    if "synthetic-sql-lesson.pdf" not in page.content():
        page.locator('form[action="/api/demo/lessons/upload"] [name="source_document_id"]').fill(
            "original-synthetic-sql"
        )
        page.get_by_test_id("lesson-file").set_input_files(str(OUT / "synthetic-sql-lesson.pdf"))
        with page.expect_navigation():
            page.get_by_test_id("upload-lesson").click()
    assert "synthetic-sql-lesson.pdf" in page.content(), page.content()[:1800]
    page.screenshot(path=str(OUT / "pdf-upload.png"), full_page=True)
    generate = page.locator('form[action="/api/demo/kg/generate"]').filter(
        has=page.locator('[name="version"][value="1"]')
    )
    generate.locator('[name="extraction_mode"]').select_option("ORIGINAL_INSTRUCTKG_CHUNK_ONLY")
    print("Real PDF uploaded; clicking Generate Knowledge Graph", flush=True)
    with page.expect_navigation(timeout=1800000):
        generate.get_by_role("button", name="Generate Knowledge Graph").click(no_wait_after=True)
    assert "/demo-graph?graph_id=" in page.url, page.content()[:1500]
    page.screenshot(path=str(OUT / "original-candidate-graph.png"), full_page=True)
    graph_id = page.url.split("graph_id=", 1)[1].split("&", 1)[0]
    graph = page.request.get(BASE + "/api/demo/graphs?graph_id=" + graph_id).json()
    assert graph["extraction_mode"] == "ORIGINAL_INSTRUCTKG_CHUNK_ONLY"
    (OUT / "candidate_graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (OUT / "browser_pdf_receipt.json").write_text(
        json.dumps(
            {
                "url": page.url,
                "actual_pdf_upload": True,
                "generate_button_clicked": True,
                "graph_id": graph_id,
                "extraction_mode": graph["extraction_mode"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"graph_id": graph_id, "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        ),
        flush=True,
    )
    browser.close()
