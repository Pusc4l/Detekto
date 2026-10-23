<#
 DETEKTO :: One-Click Windows Launcher
 Pemakaian (dari folder ini):
   start-detekto.bat                 -> mode standar (Docker + backend + frontend + browser)
   start-detekto.bat -WithCelery     -> aktifkan Celery worker (--pool=threads) untuk swarm
   start-detekto.bat -NoDocker       -> lewati Docker (semua layanan memakai fallback otomatis)
   start-detekto.bat -Tauri          -> jalankan sebagai aplikasi desktop Tauri (butuh Rust)
   start-detekto.bat -SkipInstall    -> lewati pemasangan dependensi
   start-detekto.bat -NoBrowser      -> jangan buka browser otomatis
 Hentikan semuanya dengan: stop-detekto.bat
#>
[CmdletBinding()]
param(
    [switch]$NoDocker,
    [switch]$WithCelery,
    [switch]$Tauri,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

# "Continue": PowerShell 5.1 menganggap stderr perintah native (docker/py) sebagai error fatal bila "Stop". Kegagalan dicek lewat $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvDir  = Join-Path $Backend ".venv"
$VenvPy   = Join-Path $VenvDir "Scripts\python.exe"
$PidFile  = Join-Path $Root ".detekto-pids.json"
$ApiUrl   = "http://127.0.0.1:8000/api/health"
$WebUrl   = "http://localhost:3000"

function Write-Step([string]$Message) { Write-Host (">> " + $Message) -ForegroundColor Yellow }
function Write-Ok([string]$Message)   { Write-Host ("   [OK] " + $Message) -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host ("   [!!] " + $Message) -ForegroundColor DarkYellow }
function Stop-Launcher([string]$Message) {
    Write-Host ""
    Write-Host ("[DETEKTO] " + $Message) -ForegroundColor Red
    exit 1
}
function Test-Command([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Wait-Http([string]$Url, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch { Start-Sleep -Seconds 1 }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-FileHashSafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

Write-Host ""
Write-Host "=== DETEKTO // ONE-CLICK LAUNCHER ===" -ForegroundColor Black -BackgroundColor Yellow
Write-Host ""

# ------------------------------------------------------------ 1. prasyarat
Write-Step "Memeriksa prasyarat"
$pyCmd = $null
$pyArgs = @()
if (Test-Command "py") {
    & py -3.11 --version *> $null
    if ($LASTEXITCODE -eq 0) { $pyCmd = "py"; $pyArgs = @("-3.11") }
}
if (-not $pyCmd -and (Test-Command "python")) { $pyCmd = "python" }
if (-not $pyCmd) { Stop-Launcher "Python 3.11+ tidak ditemukan. Pasang dari https://www.python.org/downloads/ (centang 'Add to PATH')." }
$pyVersion = ((& $pyCmd @pyArgs --version) 2>&1 | Out-String).Trim()
Write-Ok ("Python: " + $pyVersion)
$pyNumber = $null
if ($pyVersion -match "(\d+)\.(\d+)") { $pyNumber = [version]("{0}.{1}" -f $Matches[1], $Matches[2]) }
if ($null -eq $pyNumber -or $pyNumber -lt [version]"3.11") { Stop-Launcher ("Dibutuhkan Python 3.11+ (terdeteksi: " + $pyVersion + "). Pasang dari https://www.python.org/downloads/") }

if (-not (Test-Command "node") -or -not (Test-Command "npm")) { Stop-Launcher "Node.js (npm) tidak ditemukan. Pasang LTS dari https://nodejs.org/" }
Write-Ok ("Node: " + (& node --version))

# ---------------------------------------------------------------- 2. docker
$dockerReady = $false
if ($NoDocker) {
    Write-Warn "Docker dilewati (-NoDocker): Redis/SearxNG/Memgraph memakai fallback otomatis."
} elseif (-not (Test-Command "docker")) {
    Write-Warn "Docker tidak ditemukan: semua layanan akan memakai fallback otomatis (vault memori, DuckDuckGo, NetworkX)."
} else {
    Write-Step "Memeriksa Docker Desktop"
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        $dockerExe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        if (Test-Path -LiteralPath $dockerExe) {
            Write-Warn "Docker Desktop belum aktif. Menyalakan (maks 90 detik)..."
            Start-Process -FilePath $dockerExe | Out-Null
            $deadline = (Get-Date).AddSeconds(90)
            while ((Get-Date) -lt $deadline) {
                Start-Sleep -Seconds 3
                & docker info *> $null
                if ($LASTEXITCODE -eq 0) { break }
            }
        }
        & docker info *> $null
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Step "Menyalakan Redis + SearxNG + Memgraph"
        Push-Location $Root
        try {
            & docker compose up -d
            if ($LASTEXITCODE -ne 0) { & docker-compose up -d }
            if ($LASTEXITCODE -eq 0) { $dockerReady = $true; Write-Ok "Container berjalan (Memgraph Lab: http://localhost:3001)" }
            else { Write-Warn "docker compose gagal: lanjut dengan fallback otomatis." }
        } finally { Pop-Location }
    } else {
        Write-Warn "Docker Desktop tidak aktif: lanjut dengan fallback otomatis."
    }
}

# -------------------------------------------------------------- 3. backend
if (-not $SkipInstall) {
    Write-Step "Menyiapkan backend (virtualenv + dependensi)"
    if (-not (Test-Path -LiteralPath $VenvPy)) {
        & $pyCmd @pyArgs -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { Stop-Launcher "Gagal membuat virtualenv." }
        Write-Ok "virtualenv dibuat"
    }
    $reqFile = Join-Path $Backend "requirements.txt"
    $reqMark = Join-Path $VenvDir ".req-hash"
    $reqHash = Get-FileHashSafe $reqFile
    $oldHash = ""
    if (Test-Path -LiteralPath $reqMark) { $oldHash = (Get-Content -LiteralPath $reqMark -Raw).Trim() }
    if ($reqHash -ne $oldHash) {
        Write-Step "pip install -r requirements.txt (pertama kali bisa beberapa menit)"
        & $VenvPy -m pip install --upgrade pip --quiet
        & $VenvPy -m pip install -r $reqFile
        if ($LASTEXITCODE -ne 0) { Stop-Launcher "pip install gagal. Periksa koneksi internet lalu jalankan ulang." }
        Set-Content -LiteralPath $reqMark -Value $reqHash
        Write-Ok "dependensi backend terpasang"
    } else { Write-Ok "dependensi backend sudah up-to-date" }

    $chromiumMark = Join-Path $VenvDir ".chromium-ok"
    if (-not (Test-Path -LiteralPath $chromiumMark)) {
        Write-Step "Mengunduh Chromium untuk Playwright (sekali saja)"
        & $VenvPy -m playwright install chromium
        if ($LASTEXITCODE -eq 0) { Set-Content -LiteralPath $chromiumMark -Value "ok"; Write-Ok "Chromium siap" }
        else { Write-Warn "Chromium gagal diunduh: Swarm akan berjalan mode degradasi (tanpa scraping browser)." }
    }
} elseif (-not (Test-Path -LiteralPath $VenvPy)) {
    Stop-Launcher "virtualenv belum ada. Jalankan tanpa -SkipInstall sekali."
}

$envFile = Join-Path $Backend ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $Backend ".env.example") -Destination $envFile
    Write-Ok "backend\.env dibuat dari contoh (isi GROQ_API_KEY bila punya)"
}

$tess = (Get-Command tesseract -ErrorAction SilentlyContinue)
$tessDefault = Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"
if (-not $tess -and -not (Test-Path -LiteralPath $tessDefault)) {
    Write-Warn "Tesseract OCR belum terpasang. Unduh: https://github.com/UB-Mannheim/tesseract/wiki (atau pip install easyocr)."
}

# ------------------------------------------------------------- 4. frontend
if (-not $SkipInstall) {
    Write-Step "Menyiapkan frontend (npm)"
    $pkg = Join-Path $Frontend "package.json"
    $pkgMark = Join-Path $Frontend "node_modules\.pkg-hash"
    $pkgHash = Get-FileHashSafe $pkg
    $oldPkg = ""
    if (Test-Path -LiteralPath $pkgMark) { $oldPkg = (Get-Content -LiteralPath $pkgMark -Raw).Trim() }
    if (-not (Test-Path -LiteralPath (Join-Path $Frontend "node_modules")) -or $pkgHash -ne $oldPkg) {
        Push-Location $Frontend
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) { Stop-Launcher "npm install gagal." }
            Set-Content -LiteralPath $pkgMark -Value $pkgHash
        } finally { Pop-Location }
        Write-Ok "dependensi frontend terpasang"
    } else { Write-Ok "dependensi frontend sudah up-to-date" }
}

# -------------------------------------------------------------- 5. proses
Write-Step "Menyalakan layanan DETEKTO"
$pids = @{}
$celeryFlag = ""
if ($WithCelery) { $celeryFlag = '$env:CELERY_ENABLED = ''true''; ' }

$backendCmd = "`$Host.UI.RawUI.WindowTitle = 'DETEKTO :: BACKEND'; Set-Location -LiteralPath '$Backend'; " + $celeryFlag +
              "& '$VenvPy' -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"
$p = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd) -PassThru
$pids["backend"] = $p.Id

if ($WithCelery) {
    $celeryCmd = "`$Host.UI.RawUI.WindowTitle = 'DETEKTO :: CELERY WORKER'; Set-Location -LiteralPath '$Backend'; `$env:CELERY_ENABLED = 'true'; " +
                 "& '$VenvPy' -m celery -A workers.swarm_manager.celery_app worker --pool=threads --concurrency=3 -l info"
    $c = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $celeryCmd) -PassThru
    $pids["celery"] = $c.Id
}

$frontScript = "dev"
if ($Tauri) { $frontScript = "tauri dev" }
$frontendCmd = "`$Host.UI.RawUI.WindowTitle = 'DETEKTO :: FRONTEND'; Set-Location -LiteralPath '$Frontend'; npm run $frontScript"
$f = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd) -PassThru
$pids["frontend"] = $f.Id

$state = @{ pids = $pids; docker = $dockerReady; started = (Get-Date).ToString("s") }
$state | ConvertTo-Json | Set-Content -LiteralPath $PidFile

# ------------------------------------------------------------- 6. tunggu
Write-Step "Menunggu backend siap (maks 90 detik)"
if (Wait-Http $ApiUrl 90) { Write-Ok "Backend online: $ApiUrl" }
else { Write-Warn "Backend belum merespons. Lihat jendela 'DETEKTO :: BACKEND' untuk pesan error." }

if (-not $Tauri) {
    Write-Step "Menunggu frontend siap (maks 120 detik)"
    if (Wait-Http $WebUrl 120) {
        Write-Ok "Frontend online: $WebUrl"
        if (-not $NoBrowser) { Start-Process $WebUrl | Out-Null }
    } else { Write-Warn "Frontend belum merespons. Lihat jendela 'DETEKTO :: FRONTEND'." }
}

Write-Host ""
Write-Host "=== DETEKTO SIAP ===" -ForegroundColor Black -BackgroundColor Green
Write-Host "  UI        : $WebUrl"
Write-Host "  API       : http://127.0.0.1:8000/docs"
Write-Host "  Memgraph  : http://localhost:3001 (Lab)"
Write-Host "  Hentikan  : stop-detekto.bat"
Write-Host ""
