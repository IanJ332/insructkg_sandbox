# Dependency inventory and compatibility

The integration package has **zero third-party runtime Python dependencies**. Python standard library implements SQLite worker, HTTP client/server, JSON and persistence. Development dependencies are all version pinned in requirements-dev.txt: pypdf 6.20.1, Ruff 0.17.0, mypy 2.4.0, Bandit 1.9.4, detect-secrets 1.5.0, pip-audit 2.10.1 and Playwright 1.64.0 with pinned transitive packages. pypdf was upgraded from baseline 6.1.1 following dependency review. Chromium is installed by the pinned Playwright CLI, not committed.

PrairieLearn image digest is `sha256:f030faf735fdbb80c0307cc1b599d0757bb76a2f4573fbab9a7303adad4275ac`. The independent audited source revision is `eaaa91843807411918d260475e0a9188bcc2c979`; no assertion equates image contents with that source SHA. Compose pins the runtime digest and binds loopback only.

Upstream pins retrieved without vendoring:

| Checkout | Git commit | Use |
|---|---|---|
| code-royce/instructkg jeffry | c34a7786528e78766f15d918ab17aca2a9f7dc0b | Actual pipeline and existing graph |
| aalrabah/instructkg | ade6263a348984cef848eae85dc3d3b15daeea09 | Reference architecture audit |
| PrairieLearn/PrairieLearn | eaaa91843807411918d260475e0a9188bcc2c979 | Official lifecycle/docs inspection |

## Isolated extraction environment

The actual Intel Mac/Python 3.13 resolver cannot install a compatible torch wheel for the current Docling stack; this is broader than optional vLLM. A Linux Python 3.11 CPU image imports the unmodified upstream CLI successfully with networking disabled. No algorithm changes were made. Base Python image is pinned by digest in Dockerfile.extraction.

`extraction-cpu.lock` records the actual resolved environment, including Docling 2.109.0, torch 2.14.1+cpu, torchvision 0.29.1+cpu, transformers 5.19.0 and numpy 2.4.6. CPU torch packages come from the explicit PyTorch CPU index; remaining exact pins use the standard index. Apt OS package versions and downloaded parsing-weight revisions are not a hermetic lock; see model-cache and build logs for this run. The initial image yielded the lock; the exact-lock recipe is separately rebuilt and tracked in current status.

The historical original-settings ingestion attempt downloaded public Docling/RapidOCR parsing models but exceeded a 600-second, 2-CPU/5-GiB budget before producing chunks. This is a real unsuccessful ingestion attempt, not a Python import failure. Generative concept/role/relation stages were not run. Full model execution remains forbidden by the current no-inference/no-paid-usage instruction.

`requirements-pipeline.txt` is a human-readable optional dependency input; **extraction-cpu.lock** is the resolved CPU recipe. CUDA/vLLM requirements are separate and untested here. Integration CI does not install this large stack. Vulnerability results cover the dev pins and integration source, not the PL image or all research/model dependencies.

Follow-up: the existing CPU lock remains unchanged. Named native/Tesseract configurations complete actual ingestion without generative enrichment; see INGESTION_PROFILING.md. Future Windows server version inputs are recorded separately in infrastructure/windows/local-model-versions.json; they are not installed or treated as a validated GPU extraction environment.
