param([string]$OutputRoot = '')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot 'artifacts/full-sandbox' }
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$receiptPath = Join-Path $OutputRoot 'runtime/launch.json'
$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
if ([IO.Path]::GetFullPath($receipt.repository) -ne [IO.Path]::GetFullPath($repoRoot)) {
    throw 'Launch receipt belongs to another checkout.'
}
foreach ($entry in @(@($receipt.worker_pid, 'feedback_worker.py'), @($receipt.dashboard_pid, 'dashboard.py'))) {
    $servicePid = [int]$entry[0]
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid"
    if (-not $process) { continue }
    $expectedScript = Join-Path $PSScriptRoot $entry[1]
    if (-not $process.CommandLine -or -not $process.CommandLine.Contains($expectedScript)) {
        throw "PID $servicePid no longer matches the recorded SIIP script; refusing to stop it."
    }
    Stop-Process -Id $servicePid -Force
    Write-Output "Stopped recorded SIIP service $servicePid ($($entry[1]))."
}
