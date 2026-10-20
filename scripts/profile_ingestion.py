"""Profile actual upstream ingestion with an explicit non-generative CPU variant.

Run inside the locked CPU image, mounting upstream read-only. Instrumentation and
configuration injection are external: upstream files and chunk serialization are
unchanged. Code/formula VLM enrichment is ALWAYS disabled in this phase.
"""

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["native", "tesseract"], required=True)
    parser.add_argument("--source", type=Path, default=Path("/research"))
    parser.add_argument("--pdf", default="data/sql/3-SQL2-JOINS_Nulls.pdf")
    parser.add_argument("--output", type=Path, default=Path("/output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    metrics = defaultdict(lambda: {"calls": 0, "active_seconds": 0.0})
    lock = threading.Lock()
    wrapped = set()

    def add(name, elapsed):
        with lock:
            metrics[name]["calls"] += 1
            metrics[name]["active_seconds"] += elapsed

    def instrument(cls, method, label):
        with lock:
            key = (cls, method)
            if key in wrapped or not hasattr(cls, method):
                return
            wrapped.add(key)
        original = getattr(cls, method)

        def timed(*a, **kw):
            start = time.monotonic()
            try:
                result = original(*a, **kw)
            finally:
                add(label, time.monotonic() - start)
            if label == "page_backend_load":
                for name in ["get_text_cells", "get_segmented_page", "get_page_image"]:
                    instrument(type(result), name, "page_backend_" + name)
            if isinstance(result, Iterator):

                def iterate():
                    while True:
                        tick = time.monotonic()
                        try:
                            item = next(result)
                        except StopIteration:
                            add(label, time.monotonic() - tick)
                            return
                        except Exception:
                            add(label, time.monotonic() - tick)
                            raise
                        add(label, time.monotonic() - tick)
                        yield item

                return iterate()
            return result

        setattr(cls, method, timed)

    profiler = cProfile.Profile()
    profiler.enable()
    sys.path.insert(0, str(args.source))
    import ingest
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.pipeline_options import TesseractCliOcrOptions
    from docling.datamodel.settings import settings
    from docling.document_converter import PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from transformers.generation.utils import GenerationMixin

    blocked_generations = {"calls": 0}

    def deny_generation(*a, **kw):
        blocked_generations["calls"] += 1
        raise RuntimeError("Generative inference is forbidden in CPU ingestion profiling")

    GenerationMixin.generate = deny_generation

    import_seconds = time.monotonic() - started
    settings.debug.profile_pipeline_timings = True
    options_factory = ingest.PdfPipelineOptions
    original_init = StandardPdfPipeline._init_models

    def init_models(pipeline):
        if any(
            getattr(pipeline.pipeline_options, name)
            for name in [
                "do_code_enrichment",
                "do_formula_enrichment",
                "do_picture_description",
                "do_chart_extraction",
            ]
        ):
            raise RuntimeError("Generative enrichment options must remain disabled")
        tick = time.monotonic()
        try:
            original_init(pipeline)
        finally:
            add("model_initialization", time.monotonic() - tick)
        for name in [
            "preprocessing_model",
            "ocr_model",
            "layout_model",
            "table_model",
            "assemble_model",
            "reading_order_model",
        ]:
            instrument(type(getattr(pipeline, name)), "__call__", name)

    StandardPdfPipeline._init_models = init_models
    instrument(PdfFormatOption().backend, "load_page", "page_backend_load")
    instrument(ingest.HybridChunker, "chunk", "hybrid_chunk_generation")

    def cpu_options(**kwargs):
        kwargs.update(
            do_code_enrichment=False,
            do_formula_enrichment=False,
            do_picture_description=False,
            do_chart_extraction=False,
            do_ocr=args.profile == "tesseract",
            ocr_options=TesseractCliOcrOptions(force_full_page_ocr=False),
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=2),
            document_timeout=300,
            enable_remote_services=False,
        )
        return options_factory(**kwargs)

    ingest.PdfPipelineOptions = cpu_options
    pdf = args.source / args.pdf
    report = {
        "profile": "cpu_" + args.profile + "_no_generative_enrichment_v1",
        "original_settings": {"do_formula_enrichment": True, "do_code_enrichment": True},
        "effective_settings": {
            "do_formula_enrichment": False,
            "do_code_enrichment": False,
            "do_ocr": args.profile == "tesseract",
            "ocr": "Tesseract CLI",
            "device": "cpu",
            "threads": 2,
        },
        "upstream_source_sha256": hashlib.sha256(
            (args.source / "ingest.py").read_bytes()
        ).hexdigest(),
        "profiler_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "generative_inference_calls": 0,
        "import_seconds": import_seconds,
    }
    exit_code = 0
    try:
        chunks = ingest.pdf_to_chunks(str(pdf))
        ingest.write_jsonl(chunks, str(args.output / "chunks.jsonl"))
        pages = sorted({p for chunk in chunks for p in chunk["page_numbers"]})
        if not chunks or not pages or any(not c["text"].strip() for c in chunks):
            raise ValueError("No usable page-cited chunks")
        report.update(
            status="PASS",
            chunks=len(chunks),
            pages=pages,
            text_characters=sum(len(c["text"]) for c in chunks),
        )
    except Exception as exc:
        report.update(status="FAIL", error_type=type(exc).__name__)
        exit_code = 1
        raise
    finally:
        profiler.disable()
        stats = pstats.Stats(profiler)
        top = sorted(stats.stats.items(), key=lambda row: row[1][3], reverse=True)[:60]
        report.update(
            wall_seconds=time.monotonic() - started,
            stages=dict(metrics),
            formula_enrichment="NOT_RUN: disabled; original VLM is generative",
            code_enrichment="NOT_RUN: disabled; original VLM is generative",
            generation_guard="Transformers GenerationMixin.generate raises before inference",
            blocked_generation_calls=blocked_generations["calls"],
            timing_note="Stage times instrument worker threads; they can overlap. cProfile covers main-thread calls only. Disabled OCR/model calls can include no-op stage overhead.",
            main_thread_profile=[
                {
                    "file": Path(key[0]).name,
                    "function": key[2],
                    "calls": value[1],
                    "self_seconds": value[2],
                    "cumulative_seconds": value[3],
                }
                for key, value in top
            ],
        )
        (args.output / "profile.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in report.items() if k != "main_thread_profile"}, indent=2),
            flush=True,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
