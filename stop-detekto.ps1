<#
 DETEKTO :: Stop Launcher
   stop-detekto.bat              -> hentikan backend/frontend/celery + docker compose down
   stop-detekto.bat -KeepDocker  -> hentikan proses saja, biarkan container hidup
#>
[CmdletBinding()]
param([switch]$KeepDocker)

$ErrorActionPreference = "Continue"
$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root ".detekto-pids.json"

Write-Host ">> Menghentikan DETEKTO" -ForegroundColor Yellow
if (Test-Path -LiteralPath $PidFile) {
    $state = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
    foreach ($prop in $state.pids.PSObject.Properties) {
        $procId = [int]$prop.Value
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            & taskkill /PID $procId /T /F *> $null
            Write-Host ("   [OK] " + $prop.Name + " (PID " + $procId + ") dihentikan") -ForegroundColor Green
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "   (tidak ada catatan proses; tidak ada yang perlu dihentikan)" -ForegroundColor DarkYellow
}

if (-not $KeepDocker -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    Push-Location $Root
    try {
        & docker compose down
        if ($LASTEXITCODE -ne 0) { & docker-compose down }
        Write-Host "   [OK] container Docker dihentikan" -ForegroundColor Green
    } finally { Pop-Location }
}
Write-Host "Selesai." -ForegroundColor Green
