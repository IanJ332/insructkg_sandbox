# Read-only readiness. No installation, model loading, downloads or inference.
$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    OS = [System.Environment]::OSVersion.VersionString
    Inference = 'BLOCKED; not executed'
    OllamaAvailable = [bool](Get-Command ollama -ErrorAction SilentlyContinue)
    WslAvailable = [bool](Get-Command wsl -ErrorAction SilentlyContinue)
    NvidiaSmiAvailable = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
}
if ($report.NvidiaSmiAvailable) {
    $report.GpuMetadata = @(& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)
    $report.GpuMetadataExitCode = $LASTEXITCODE
}
$report | ConvertTo-Json -Depth 4
