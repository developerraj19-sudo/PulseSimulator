# ============================================================================
# PulseSim: Launcher & Bootstrap Script (PowerShell)
# ============================================================================

Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                PulseSim Startup Manager                  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python installation
Write-Host "[1/4] Verifying Python installation..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "ERROR: Python is not installed or not in system PATH." -ForegroundColor Red
    Exit 1
}

# 2. Virtual Environment setup
Write-Host ""
Write-Host "[2/4] Setting up Virtual Environment..." -ForegroundColor Yellow
$backendDir = "d:\PulseSim\backend"
$venvDir = Join-Path $backendDir "venv"

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment at $venvDir..." -ForegroundColor DarkYellow
    python -m venv $venvDir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Virtual environment created." -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        Exit 1
    }
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# Activate virtual environment
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
Write-Host "Activating environment..." -ForegroundColor DarkYellow
. $activateScript

# 3. Install packages
Write-Host ""
Write-Host "[3/4] Checking and installing Python dependencies..." -ForegroundColor Yellow
pip install -r (Join-Path $backendDir "requirements.txt")
if ($LASTEXITCODE -eq 0) {
    Write-Host "Dependencies verified." -ForegroundColor Green
} else {
    Write-Host "ERROR: Package installation failed." -ForegroundColor Red
    Exit 1
}

# 4. Check configuration files
Write-Host ""
Write-Host "[4/4] Verifying config files..." -ForegroundColor Yellow
$envFile = Join-Path $backendDir ".env"
$exampleFile = Join-Path $backendDir ".env.example"

if (-not (Test-Path $envFile)) {
    Write-Host "No .env found. Generating from example..." -ForegroundColor DarkYellow
    Copy-Item $exampleFile $envFile
    Write-Host "Generated $envFile. Adjust connection strings as needed." -ForegroundColor Green
} else {
    Write-Host "Configuration loaded successfully." -ForegroundColor Green
}

# 5. Start FastAPI Application
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  PulseSim Server launching on http://localhost:8000/   " -ForegroundColor Green
Write-Host "  (To stop the simulation, press Ctrl+C)                " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

Set-Location $backendDir
uvicorn app.main:app --reload --port 8000
