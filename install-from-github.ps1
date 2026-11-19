# Download latest contrib plugin tree from GitHub and install into OpenLP DataDir.
# Usage (one-liner in README):
#   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/doszyja/openlp-sync-plugin/main/install-from-github.ps1 | iex"

$ErrorActionPreference = 'Stop'

$Repo = 'doszyja/openlp-sync-plugin'
$Branch = 'main'
$ZipUrl = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
$Temp = Join-Path $env:TEMP "openlp-sync-plugin-$Branch"
$ZipPath = Join-Path $env:TEMP "openlp-sync-plugin.zip"
$Extracted = Join-Path $env:TEMP "$($Repo.Split('/')[1])-$Branch"

foreach ($path in @($Temp, $Extracted)) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force
    }
}

Write-Host "Pobieranie $Repo ($Branch)..."
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
Expand-Archive -Path $ZipPath -DestinationPath $env:TEMP -Force
Remove-Item $ZipPath -Force

if (-not (Test-Path (Join-Path $Extracted 'install.ps1'))) {
    Write-Error "Brak install.ps1 w archiwum. Sprawdź gałąź $Branch w $Repo."
}

Copy-Item -Path $Extracted -Destination $Temp -Recurse -Force
& powershell -ExecutionPolicy Bypass -File (Join-Path $Temp 'install.ps1')