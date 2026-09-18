# One-shot VerticalFox deployment for a Firefox profile.
# Usage: .\deploy.ps1 -Profile <path> [-Repo <repo-root>] [-Launch]
# Firefox will be closed automatically if it is running.
param(
    [Parameter(Mandatory = $true)]
    [string]$Profile,
    [string]$Repo = (Split-Path $PSScriptRoot -Parent),
    [switch]$Launch,
    [string]$Firefox = "C:\Program Files\Firefox Developer Edition\firefox.exe"
)

$ErrorActionPreference = "Stop"

if (Get-Process firefox -ErrorAction SilentlyContinue) {
    Write-Output "Firefox is running -> closing gracefully..."
    Get-Process firefox | ForEach-Object { $null = $_.CloseMainWindow() }
    Start-Sleep -Seconds 5
    if (Get-Process firefox -ErrorAction SilentlyContinue) {
        throw "Firefox still running; close it manually (unsaved session?)"
    }
}

# 1. backup
& (Join-Path $PSScriptRoot "backup.ps1") -Profile $Profile

# 2. userChrome.css + user.js
$chromeDir = Join-Path $Profile "chrome"
New-Item -ItemType Directory -Force -Path $chromeDir | Out-Null
Copy-Item (Join-Path $Repo "windows\userChrome.css") (Join-Path $chromeDir "userChrome.css") -Force
Copy-Item (Join-Path $Repo "windows\user.js") (Join-Path $Profile "user.js") -Force
Write-Output "deployed: chrome\userChrome.css + user.js"

# 3. Sidebery styles -> LSNG sqlite
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    python (Join-Path $PSScriptRoot "deploy_sidebery_css.py") --Profile $Profile
} else {
    Write-Warning "python not found - deploy Sidebery CSS manually (see MAINTENANCE.md)"
}

if ($Launch) {
    Start-Process $Firefox -ArgumentList '-no-remote', '-profile', $Profile
    Write-Output "Firefox launched."
}
