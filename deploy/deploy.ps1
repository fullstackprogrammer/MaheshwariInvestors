# Redeploy frontend (and optionally backend) to existing EC2.
# Usage:
#   .\deploy.ps1                          # uses deploy\config
#   .\deploy.ps1 -EC2_IP 54.89.185.96 -KEY_PATH C:\path\to\key.pem
#   .\deploy.ps1 -BackendToo               # also sync backend + data and restart API
#
# Requires: Node/npm (frontend build), OpenSSH (scp/ssh). Run from repo root.

param(
    [string]$EC2_IP,
    [string]$KEY_PATH,
    [string]$EC2_USER = "ec2-user",
    [string]$RemoteAppDir = "/home/ec2-user/MaheshwariInvestors",
    [switch]$BackendToo
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

# Load config if not passed
if (-not $EC2_IP -and (Test-Path "$ScriptDir\config")) {
    Get-Content "$ScriptDir\config" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Variable -Name $name -Value $value -Scope Script
        }
    }
}
if (-not $EC2_IP) { $EC2_IP = $env:EC2_IP }
if (-not $KEY_PATH) { $KEY_PATH = $env:KEY_PATH }

if (-not $EC2_IP -or -not $KEY_PATH) {
    Write-Host "Set EC2_IP and KEY_PATH in deploy\config or pass -EC2_IP and -KEY_PATH (or env vars)." -ForegroundColor Red
    exit 1
}

$ApiUrl = "http://${EC2_IP}:8000"
Write-Host "Deploying to $EC2_IP (API: $ApiUrl)" -ForegroundColor Cyan

# 1. Build frontend
Push-Location "$RepoRoot\frontend"
$env:VITE_API_BASE_URL = $ApiUrl
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Pop-Location

# 2. Upload frontend dist (whole dist folder → remote frontend/dist)
$DistLocal = "$RepoRoot\frontend\dist"
$DistRemote = "${EC2_USER}@${EC2_IP}:${RemoteAppDir}/frontend/"
Write-Host "Uploading frontend dist..." -ForegroundColor Cyan
& scp -i $KEY_PATH -r "$DistLocal" $DistRemote
if ($LASTEXITCODE -ne 0) { exit 1 }

# 3. Optionally sync backend + data
if ($BackendToo) {
    Write-Host "Syncing backend and data..." -ForegroundColor Cyan
    & scp -i $KEY_PATH -r "$RepoRoot\backend\main.py" "$RepoRoot\backend\requirements.txt" "$RepoRoot\backend\csp_universe.py" "$RepoRoot\backend\csp_screener.py" "${EC2_USER}@${EC2_IP}:${RemoteAppDir}/backend/"
    if (Test-Path "$RepoRoot\data") {
        & scp -i $KEY_PATH -r "$RepoRoot\data" "${EC2_USER}@${EC2_IP}:${RemoteAppDir}/"
    }
    if (Test-Path "$RepoRoot\DFWInvestors2026StockPicks.csv") {
        & scp -i $KEY_PATH "$RepoRoot\DFWInvestors2026StockPicks.csv" "${EC2_USER}@${EC2_IP}:${RemoteAppDir}/"
    }
}

# 4. Restart backend and reload Nginx on EC2
$RemoteCmd = "sudo systemctl restart maheshwari-api; sudo systemctl reload nginx; echo Done"
Write-Host "Restarting backend and Nginx on EC2..." -ForegroundColor Cyan
& ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new "${EC2_USER}@${EC2_IP}" $RemoteCmd
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Deploy done. App: http://${EC2_IP}" -ForegroundColor Green
