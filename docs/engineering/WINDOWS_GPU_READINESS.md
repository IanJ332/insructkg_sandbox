# Windows NVIDIA GPU readiness — future execution only

**No Ollama/vLLM server or generative model was installed, loaded or served by this phase. No generative inference ran.** CPU parsing/OCR models were used separately as documented in the ingestion profile. The current Mac has no ollama/vllm/nvidia-smi/wsl executable on PATH. A future Windows host, GPU/VRAM, driver and approved model are unknown. Windows hardware execution and actual model/structured-output quality are NOT_RUN. Configuration and mock transport contracts pass.

## Verified compatibility and fixed versions

[Ollama's official Windows guide](https://docs.ollama.com/windows) supports a native Windows service/application with NVIDIA acceleration and localhost 11434. [Its API compatibility docs](https://docs.ollama.com/api/openai-compatibility) document `/v1/chat/completions`, model selection and response_format/JSON mode. These match the project's existing compatible feedback client; local semantic validation still rejects malformed output, unknown concepts/citations and obvious answer leakage.

[vLLM's official GPU guide](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/) requires Linux for the standard GPU runtime; Windows uses WSL2/a compatible Linux distribution. Native Windows support is not assumed. Current documented NVIDIA capability requirements must be compared with the actual card. [NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) describes Windows-driver CUDA integration; do not install a separate Linux display driver inside WSL.

Fixed official release references, verified 2026-10-14: Ollama **0.40.4**, vLLM server **0.31.0**. `infrastructure/windows/local-model-versions.json` records release URLs and NOT_RUN status. The original research in-process vLLM pin is a **separate 0.19.1 environment**, not interchangeable with the server or CPU extraction lock. Model weights/digest and GPU-specific transitive lock must be recorded after the future host is selected; no universal model/VRAM fit is claimed.

## Readiness without inference

On the future Windows host, `powershell -File infrastructure/windows/readiness.ps1` reads command availability and NVIDIA name/driver/VRAM only. It does not install anything or start inference. Confirm the GPU/driver against the selected server release and record the output locally. Choose a model only after VRAM/context/precision and rights are known.

Run the project itself in WSL2/Linux so existing `.venv/bin`, resource-limit and Docker workflows remain applicable. Native Windows grading/runtime compatibility is not verified. Use a separate Linux model-server virtual environment; never install CUDA vLLM into the integration venv or the exact CPU Docling lock.

## Reproducible future Ollama recipe

After model-use authorization changes, obtain `ollama-windows-amd64.zip` and `sha256sum.txt` from the [fixed 0.40.4 release](https://github.com/ollama/ollama/releases/tag/v0.40.4). Verify the archive with `Get-FileHash -Algorithm SHA256`, compare the release checksum, extract into a versioned directory and record `ollama --version`. Do not silently use a floating installer/latest tag.

A future PowerShell launch, after choosing an approved local model, is:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama serve
# Separate future terminal: download the approved model only after authorization.
# ollama pull <approved-model-tag>
```

Keep the existing daemon if it already owns the port; inspect its version rather than starting a second copy. Record the model's immutable digest and server/driver versions. `infrastructure/windows/ollama.env.example` leaves feedback deterministic today and contains no credential. A local server may have a local authentication token; it does not require a paid provider account.

For WSL→Windows localhost access, [Microsoft documents mirrored networking](https://learn.microsoft.com/en-us/windows/wsl/networking) on supported Windows 11/WSL versions. Validate routing on that host. Default NAT does not imply that WSL's 127.0.0.1 reaches Windows. Prefer a validated loopback/mirrored setup or put server/client in the same Linux environment; do not bind unauthenticated APIs to all LAN interfaces just to bypass routing. No firewall/security changes are made by this project.

## Reproducible future WSL2 vLLM recipe

Prepare approved WSL2/Ubuntu and the Windows NVIDIA driver; verify `nvidia-smi` inside WSL. In a **separate** Python 3.12 environment, pin the server version:

```sh
python3.12 -m venv .venv-vllm-server
.venv-vllm-server/bin/python -m pip install 'vllm==0.31.0'
.venv-vllm-server/bin/python -m pip check
.venv-vllm-server/bin/python -m pip freeze > artifacts/vllm-server-resolved.txt
# Future authorized model loading/server launch ONLY:
.venv-vllm-server/bin/vllm serve "$APPROVED_MODEL_PATH"   --host 127.0.0.1 --port 8000 --served-model-name siip-local   --max-model-len 4096 --gpu-memory-utilization 0.8
```

The model path, checkpoint revision, dtype and memory budget must be chosen from actual hardware evidence;4,096tokens/80% are starting configuration values, not a fit guarantee. Do not enable remote model code by default. Pin the resolved GPU environment after a successful dependency/GPU check and retain a rollback version. The fixed pip version is a reproducible recipe input, **not proof that this untested host resolves or runs it**.

## Project endpoint and contract verification

Keep SIIP_FEEDBACK_PROVIDER=deterministic now. Future approved local feedback uses provider=local, base URL `http://127.0.0.1:11434/v1` for Ollama or `http://127.0.0.1:8000/v1` for vLLM and the exact served model ID. PL's Docker container may need `host.docker.internal`; validate that path separately. All endpoints remain local; no paid-consent sentinel is needed for local serving.

`scripts/check_local_model.py` validates config/tool availability without contacting a server. Optional `--probe` sends only **GET /v1/models** and reports model-listed status, never successful inference. Tests verify configurable endpoint/model/max_tokens, JSON-object wire format, validation/fallback and failure handling against mocks. JSON mode is not a guarantee of semantic schema correctness; the client's strict three-field filter remains authoritative. Actual model support and leakage quality require a future authorized canary.

## Extraction backend distinction

The reviewed bug is fixed: LLM_PROVIDER=local/hf/huggingface/vllm/hf_legacy needs no OPENAI_API_KEY/ANTHROPIC_API_KEY. The CPU image correctly refuses an in-process GPU backend because it lacks vLLM, with a runtime message rather than a false missing-paid-key error. Test planning without execution:

```sh
LLM_PROVIDER=vllm SIIP_EXTRACTION_MODEL=synthetic-model   .venv/bin/python scripts/extraction_cpu.py full --dry-run
```

For a local compatible API, upstream uses **Responses API**, unlike feedback's Chat Completions. OPENAI_BASE_URL is honored by the upstream SDK; a non-secret local placeholder satisfies its key constructor if no local token is needed. Chat compatibility alone does not verify Responses behavior. Validate the specific server's Responses/prompt/output behavior later, or use the supported in-process upstream adapter in a separately resolved GPU environment. No speculative protocol bridge or generative canary was executed here. Remote paid extraction still requires explicit model-use consent, HTTPS and a provider credential.

Actual upstream constructor check also passed inside the locked CPU image with `--network none`: OpenAICompatClient honored the local OPENAI_BASE_URL with a non-secret placeholder, and VLLMCompatClient initialized with no API key while its engine remained unset and vllm was not imported. No create/generate method was invoked. This validates constructor/configuration behavior only, not a running server's Responses protocol or GPU execution. Evidence: artifacts/followup/upstream-backend-constructor.log.
