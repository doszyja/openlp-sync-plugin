# Fetch repo ZIP from GitHub, expand under %TEMP%, run install.ps1 (no self-copy).
param(
    [string]$Repo = 'doszyja/openlp-sync-plugin',
    [string]$Branch = 'main'
)

$ErrorActionPreference = 'Stop'

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
    # Windows PowerShell 5.1
}

$RepoName = ($Repo -split '/', 2)[-1]
if (-not $RepoName) {
    Write-Error 'Invalid Repo id (expected owner/name).'
}

$ZipUrl = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
$ZipPath = Join-Path $env:TEMP "openlp-sync-plugin-$Branch.zip"
$Extracted = Join-Path $env:TEMP "$RepoName-$Branch"

foreach ($path in @($Extracted, $ZipPath)) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Pobieranie $Repo ($Branch)..."
try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
} catch {
    Write-Error "Nie mozna pobrac archiwum ($ZipUrl). Czy repo jest publiczne i gałąź $Branch istnieje?"
}

if (-not (Test-Path $ZipPath) -or (Get-Item $ZipPath).Length -lt 100) {
    Write-Error 'Pusty lub uszkodzony plik ZIP — sprawdz URL repozytorium.'
}

Expand-Archive -LiteralPath $ZipPath -DestinationPath $env:TEMP -Force
Remove-Item -LiteralPath $ZipPath -Force

$installScript = Join-Path $Extracted 'install.ps1'
$pluginFile = Join-Path $Extracted 'plugins\songstats\songstatsplugin.py'

if (-not (Test-Path -LiteralPath $installScript)) {
    Write-Error "Brak install.ps1 w ($Extracted). Sprawdz gałąź $Branch lub strukture repo."
}
if (-not (Test-Path -LiteralPath $pluginFile)) {
    Write-Error "Brak plugins\songstats w archiwum — to nie jest pelne repo contrib."
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installScript

if (-not (Test-Path (Join-Path $env:APPDATA 'openlp\data\contrib\plugins\songstats\songstatsplugin.py'))) {
    Write-Error 'Instalacja nie skopiowala wtyczki — uruchom OpenLP raz i sprobuj ponownie.'
}

Write-Host 'Gotowe.'