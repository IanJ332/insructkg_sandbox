param(
    [string]$OutputRoot = '',
    [string]$Python = 'python',
    [int]$Port = 8810,
    [switch]$Deterministic,
    [switch]$LocalModel
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot 'artifacts/full-sandbox' }
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$runtimeRoot = Join-Path $OutputRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$baseUrl = "http://127.0.0.1:$Port"
try { $existing = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 2 } catch { $existing = $null }
if ($existing) { throw "A service is already listening at $baseUrl. Preserve it; use its saved launch receipt or select another port." }
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:SIIP_ENV = 'development'
$env:SIIP_ALLOW_SYNTHETIC_AUTH = '1'
$env:SIIP_ASYNC_FEEDBACK = '1'
$env:SIIP_DB_PATH = Join-Path $runtimeRoot 'synthetic.sqlite3'
$env:SIIP_FEEDBACK_JOBS_DB = Join-Path $runtimeRoot 'feedback_jobs.sqlite3'
$env:SIIP_DATA_DIR = Join-Path $runtimeRoot 'public-data'
$env:SIIP_DEMO_STATE_DIR = Join-Path $runtimeRoot 'demo-state'
$env:SIIP_DEMO_ARTIFACT_DIR = Join-Path $OutputRoot 'backend-timeline'
$env:SIIP_DEMO_CORRELATION_ID = 'siip-professor-demo-2026-10-20'
$env:SIIP_DASHBOARD_PORT = "$Port"
$env:SIIP_FEEDBACK_SERVICE_URL = $baseUrl
if (-not $env:SIIP_LLM_BASE_URL) { $env:SIIP_LLM_BASE_URL = 'http://127.0.0.1:11434/v1' }
if (-not $env:SIIP_LLM_MODEL) { $env:SIIP_LLM_MODEL = 'qwen3:8b' }
$env:SIIP_LOCAL_KG_MODEL = $env:SIIP_LLM_MODEL
Remove-Item Env:SIIP_LLM_MODEL_DIGEST -ErrorAction SilentlyContinue
$env:SIIP_LLM_TIMEOUT_SECONDS = '60'
$env:SIIP_LLM_MAX_TOKENS = '500'
$env:SIIP_LLM_TRANSPORT = 'ollama'
$env:SIIP_FEEDBACK_PROVIDER = 'local'
$env:SIIP_DEMO_KG_MODE = 'local'
if ($Deterministic -or -not $LocalModel) {
    $env:SIIP_FEEDBACK_PROVIDER = 'deterministic'
    $env:SIIP_DEMO_KG_MODE = 'synthetic'
} else {
    try {
        $ollamaRoot = $env:SIIP_LLM_BASE_URL -replace '/v1/?$', ''
        $tags = Invoke-RestMethod "$ollamaRoot/api/tags" -TimeoutSec 5
        $model = $tags.models | Where-Object name -EQ $env:SIIP_LLM_MODEL | Select-Object -First 1
        if ($model) { $env:SIIP_LLM_MODEL_DIGEST = $model.digest }
    } catch { Write-Warning 'Ollama is unavailable. Extraction and feedback must retain their explicit fallback labels.' }
}
& $Python (Join-Path $PSScriptRoot 'init_public.py') $env:SIIP_DATA_DIR
if ($LASTEXITCODE -ne 0) { throw 'Synthetic public-data preparation failed; no server started.' }
$dashboard = Start-Process -FilePath $Python -ArgumentList @('-u', ('"' + (Join-Path $PSScriptRoot 'dashboard.py') + '"')) -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'dashboard.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'dashboard.err.log')
$worker = Start-Process -FilePath $Python -ArgumentList @('-u', ('"' + (Join-Path $PSScriptRoot 'feedback_worker.py') + '"'), '--poll-interval', '0.25') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'worker.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'worker.err.log')
$receipt = @{ repository = $repoRoot; python = $Python; url = $baseUrl; dashboard_pid = $dashboard.Id; worker_pid = $worker.Id; started_utc = [DateTime]::UtcNow.ToString('o'); runtime = $runtimeRoot; environment = @{} }
Get-ChildItem Env: | Where-Object { $_.Name -like 'SIIP_*' -and $_.Name -notmatch 'KEY|SECRET|TOKEN' } | ForEach-Object { $receipt.environment[$_.Name] = $_.Value }
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtimeRoot 'launch.json') -Encoding utf8
Write-Output "Synthetic sandbox starting at $baseUrl/login. Launch receipt: $runtimeRoot\launch.json"
