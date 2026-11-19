# Install Song Stats community plugin into the OpenLP data directory (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = 'Stop'

$SourceContrib = Join-Path $PSScriptRoot '.'
$TargetContrib = Join-Path $env:APPDATA 'openlp\data\contrib'

if (-not (Test-Path (Join-Path $env:APPDATA 'openlp\data'))) {
    Write-Host 'Brak folderu danych OpenLP — uruchom OpenLP raz i powtórz instalację.'
    exit 1
}

New-Item -ItemType Directory -Force -Path $TargetContrib | Out-Null

# Copy package init files and the songstats plugin (merge with existing contrib content).
$itemsToCopy = @(
    (Join-Path $SourceContrib '__init__.py'),
    (Join-Path $SourceContrib 'plugins')
)

foreach ($item in $itemsToCopy) {
    if (-not (Test-Path $item)) {
        Write-Error "Missing: $item"
    }
    Copy-Item -Path $item -Destination $TargetContrib -Recurse -Force
}

$pluginPath = Join-Path $TargetContrib 'plugins\songstats\songstatsplugin.py'
Write-Host 'Zainstalowano wtyczkę KWCH Świętochłowice.'
Write-Host "Plik: $pluginPath"
Write-Host 'Zrestartuj OpenLP → Ustawienia → Zarządzaj wtyczkami → włącz „KWCH Swietochlowice plugin”.'