# Run MaheshwariInvestors project locally (backend + frontend)
# Usage: .\scripts\run-local.ps1
# Or from repo root: powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1

$ErrorActionPreference = "Stop"
# Script is in ProjectRoot/scripts/, so parent of script dir is project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ProjectRoot "backend\main.py"))) { $ProjectRoot = (Get-Location).Path }

Write-Host "Project root: $ProjectRoot" -ForegroundColor Cyan

# Find Python (avoid Windows Store stub)
$pythonExe = $null
foreach ($p in @("python", "python3", "py")) {
    try {
        $v = & $p --version 2>&1
        if ($v -and $v -notmatch "Microsoft Store") {
            $pythonExe = $p
            break
        }
    } catch {}
}
if (-not $pythonExe) {
    Write-Host ""
    Write-Host "Python not found or only Store stub. Install from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Then disable 'App execution aliases' for python.exe in Windows Settings." -ForegroundColor Yellow
    exit 1
}

# Check Node
try {
    $null = node --version
} catch {
    Write-Host ""
    Write-Host "Node.js not found. Install from https://nodejs.org/ (LTS)." -ForegroundColor Yellow
    exit 1
}

$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvDir = Join-Path $BackendDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvActivate = Join-Path $VenvDir "Scripts\Activate.ps1"

# Backend: ensure venv and deps
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Cyan
    & $pythonExe -m venv $VenvDir
}
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet --only-binary :all: -r (Join-Path $BackendDir "requirements.txt") 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install --quiet -r (Join-Path $BackendDir "requirements.txt")
}

# Start backend in background
Write-Host "Starting backend at http://localhost:8080 ..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:BackendDir
    & $using:VenvPython -m uvicorn main:app --reload --port 8080 --host 0.0.0.0
}

# Wait for backend to be up
Start-Sleep -Seconds 3

# Frontend: ensure deps
$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    Set-Location $FrontendDir
    npm install
    Set-Location $ProjectRoot
}

# Start frontend (foreground so you see logs)
Write-Host "Starting frontend at http://localhost:5173 ..." -ForegroundColor Green
Write-Host ""
Write-Host "Open in browser: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API docs: http://localhost:8080/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Gray
Write-Host ""

Set-Location $FrontendDir
npm run dev

# When frontend exits, stop backend
Stop-Job $backendJob -ErrorAction SilentlyContinue
Remove-Job $backendJob -ErrorAction SilentlyContinue
