# Install Song Stats community plugin into the OpenLP data directory (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [-DataPath 'D:\OpenLPPortable\Data']

param(
    [string]$DataPath = ''
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'install-lib.ps1')

$SourceContrib = Join-Path $PSScriptRoot '.'
$dataRoot = Resolve-OpenLPDataDir -DataPath $DataPath

if (-not $dataRoot) {
    Write-OpenLPDataDirHelp
    exit 1
}

$TargetContrib = Join-Path $dataRoot 'contrib'
New-Item -ItemType Directory -Force -Path $TargetContrib | Out-Null

$itemsToCopy = @(
    (Join-Path $SourceContrib '__init__.py'),
    (Join-Path $SourceContrib 'plugins')
)

foreach ($item in $itemsToCopy) {
    if (-not (Test-Path -LiteralPath $item)) {
        Write-Error "Missing: $item"
    }
    Copy-Item -LiteralPath $item -Destination $TargetContrib -Recurse -Force
}

$pluginPath = Join-Path $TargetContrib 'plugins\songstats\songstatsplugin.py'
Write-Host 'Zainstalowano wtyczke KWCH Swietochlowice.'
Write-Host "Plik: $pluginPath"
Write-Host 'Zrestartuj OpenLP -> Ustawienia -> Zarzadzaj wtyczkami -> wlacz KWCH Swietochlowice plugin.'