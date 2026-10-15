# Local setup

Supported integration targets are Python 3.11 and 3.13. The observed Mac uses Intel macOS/Python 3.13.9, Docker Desktop engine 28.5.2, Compose 2.40.3. Allow ports 3000/8080 and enough Docker memory for PL; CPU extraction separately caps itself at 5 GiB / two CPUs. No GPU or paid account is needed for public tests.

Clone `https://github.com/IanJ332/insructkg_sandbox`, check out `engineering/phase2-hardening`, then run the README public-code sequence. `manage.py install` creates `.venv` and installs all exact dev pins. `test-public` sets `SIIP_DATA_DIR` to ignored `artifacts/public-data`; ordinary unit tests do not start PL. `quality` runs Ruff, formatting, scoped strict mypy and configuration validation. `build` produces and inspects the code-only wheel.

For a new public-code PL demo, `init_public.py prairielearn-course/serverFilesCourse/siip/data` prepares the explicitly synthetic graph/lesson. `seed.py` initializes 21 original fixture attempts. `manage.py start` waits up to 300 seconds for actual PL health, then checks the dashboard's service identity. Cold PL asset compilation can take several minutes. Load the course from disk through PL, then select Student view. No API token or database injection is needed.

## Authorized local research path

Do not run the public initializer over an existing research data directory. `scripts/bootstrap.py` retrieves three immutable upstream checkouts under ignored `research/`, preserving modified checkouts by stopping. Review source ownership before using materials. With authorized local PDF/graph present, `manage.py init` prepares page text, dataset expectations, graph review queue and seed attempts. It does not run fresh LLM extraction. Run `manage.py test-research` for the two actual-graph assertions. Those tests require the pinned local corpus and deliberately are not silently skipped in public CI.

Copy `.env.example` to ignored `.env` only if needed; Python uses the literal parser and shell-exported values take precedence. No shell expressions are evaluated. Current instruction requires deterministic mode and no paid calls. Do not enable local/compatible inference without a later authorization.

For upstream isolation, `docker build -f infrastructure/Dockerfile.extraction -t siip-extraction-cpu:phase2 .`, then `.venv/bin/python scripts/extraction_cpu.py imports`. `ingest` can download free public parsing weights and runs the unmodified upstream parser; its observed 600-second timeout is a known limit. `full` remains blocked. Research output is never needed to install the integration package.

Troubleshoot Docker availability with `manage.py check`. Preserve unrelated port owners; dashboard startup rejects an unrelated service. Health URLs are `/health` on analytics and `/pl` on PL. See [operations](OPERATIONS.md) for persistence and recovery.
