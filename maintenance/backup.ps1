# Back up the profile files that VerticalFox touches.
# Usage: .\backup.ps1 -Profile <path> [-Out <dir>]
param(
    [Parameter(Mandatory = $true)]
    [string]$Profile,
    [string]$Out = ""
)

if (-not (Test-Path -LiteralPath $Profile)) { throw "profile not found: $Profile" }
if (-not $Out) { $Out = Join-Path $env:TEMP ("vfox-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss")) }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$uuidFile = Join-Path $Profile "prefs.js"
$uuid = ""
if (Test-Path $uuidFile) {
    $line = (Select-String -Path $uuidFile -Pattern 'webextensions\.uuids').Line
    if ($line) {
        $m = [regex]::Match($line, '3c078156-979c-498b-8990-85f7987dd929\}?\\?":\\"([0-9a-f-]+)')
        if ($m.Success) { $uuid = $m.Groups[1].Value }
    }
}

$items = @(
    @{ Src = Join-Path $Profile "chrome\userChrome.css";        Dst = "userChrome.css" },
    @{ Src = Join-Path $Profile "user.js";                      Dst = "user.js" },
    @{ Src = Join-Path $Profile "prefs.js";                     Dst = "prefs.js" },
    @{ Src = Join-Path $Profile "xulstore.json";                Dst = "xulstore.json" }
)
if ($uuid) {
    $lsdb = Join-Path $Profile "storage\default\moz-extension+++${uuid}\ls\data.sqlite"
    $items += @{ Src = $lsdb; Dst = "sidebery-ls-data.sqlite" }
}

foreach ($it in $items) {
    if (Test-Path -LiteralPath $it.Src) {
        Copy-Item -LiteralPath $it.Src -Destination (Join-Path $Out $it.Dst) -Force
        Write-Output "backed up: $($it.Dst)"
    } else {
        Write-Output "skip (missing): $($it.Src)"
    }
}
Write-Output "backup dir: $Out"
