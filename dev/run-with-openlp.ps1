# Run OpenLP from OPENLP_SRC after installing this contrib tree into AppData.
param(
    [ValidateSet('debug', 'info', 'warning')]
    [string]$LogLevel = 'debug',
    [string]$OpenLpRoot = $env:OPENLP_SRC
)

$ErrorActionPreference = 'Stop'
$ContribRoot = Split-Path $PSScriptRoot -Parent

if (-not $OpenLpRoot) {
    $sibling = Join-Path (Split-Path $ContribRoot -Parent) 'run_openlp_dev.py'
    if (Test-Path $sibling) {
        $OpenLpRoot = Split-Path $ContribRoot -Parent
    }
}

if (-not $OpenLpRoot -or -not (Test-Path (Join-Path $OpenLpRoot 'run_openlp_dev.py'))) {
    Write-Host 'Set OPENLP_SRC to your OpenLP source checkout (directory containing run_openlp_dev.py).'
    exit 1
}

Write-Host "OpenLP source: $OpenLpRoot"
Write-Host "Contrib source: $ContribRoot"
& powershell -ExecutionPolicy Bypass -File (Join-Path $ContribRoot 'install.ps1')

$VenvPython = Join-Path $OpenLpRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host 'No .venv in OpenLP repo — run that repo''s dev setup first (run-dev.ps1 or pip install -e .).'
    exit 1
}

Set-Location $OpenLpRoot
& $VenvPython (Join-Path $OpenLpRoot 'run_openlp_dev.py') -l $LogLevel