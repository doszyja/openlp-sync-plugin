# Dev launcher — works in monorepo (contrib next to run_openlp_dev.py) or standalone contrib repo.
# Usage:
#   powershell -ExecutionPolicy Bypass -File run-dev.ps1
# Standalone: set OPENLP_SRC to your OpenLP checkout.

param(
    [ValidateSet('debug', 'info', 'warning')]
    [string]$LogLevel = 'debug'
)

$ContribRoot = $PSScriptRoot
$Parent = Split-Path $ContribRoot -Parent
$MonorepoRunner = Join-Path $Parent 'run_openlp_dev.py'

if (Test-Path $MonorepoRunner) {
    $ErrorActionPreference = 'Stop'
    $RepoRoot = $Parent
    Set-Location $RepoRoot

    $VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $VenvPython)) {
        Write-Host 'Creating .venv and installing OpenLP (editable)...'
        py -3 -m venv .venv
        & $VenvPython -m pip install --upgrade pip wheel setuptools
        $env:PIP_NO_BUILD_ISOLATION = '1'
        & $VenvPython -m pip install -e . 2>&1 | Tee-Object -Variable pipLog
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Retrying install without PyICU (Windows workaround)...'
            & $VenvPython -m pip install -e . --no-deps
            & $VenvPython -m pip install `
                alembic beautifulsoup4 chardet flask flask-cors lxml Mako packaging platformdirs `
                pymediainfo python-vlc PyQt5 PyQtWebEngine QtAwesome qrcode requests SQLAlchemy waitress websockets pywin32
        }
    }

    & $VenvPython -m pip install python-vlc -q 2>$null
    Write-Host 'Installing Song Stats plugin into %APPDATA%\openlp\data\contrib...'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $ContribRoot 'install.ps1')
    Write-Host ''
    Write-Host "Starting OpenLP from source (log: $LogLevel)."
    & $VenvPython (Join-Path $RepoRoot 'run_openlp_dev.py') -l $LogLevel
    exit $LASTEXITCODE
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $ContribRoot 'dev\run-with-openlp.ps1') -LogLevel $LogLevel