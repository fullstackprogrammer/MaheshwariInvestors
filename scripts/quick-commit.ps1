# Quick add + commit + push. Run from repo root.
# Usage: .\scripts\quick-commit.ps1 "Your commit message"
#        .\scripts\quick-commit.ps1  (prompts for message)

param([string]$Message)

if (-not $Message) {
    $Message = Read-Host "Commit message"
}
if (-not $Message.Trim()) {
    Write-Host "No message. Exiting." -ForegroundColor Red
    exit 1
}

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $root

git add -A
git status
git commit -m $Message
if ($LASTEXITCODE -eq 0) {
    git push
} else {
    Write-Host "Nothing to commit or commit failed." -ForegroundColor Yellow
}
