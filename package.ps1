# Build production ZIP for Song Stats community plugin (OpenLP 4+).
# Usage: powershell -ExecutionPolicy Bypass -File contrib\package.ps1

$ErrorActionPreference = 'Stop'

$ContribRoot = $PSScriptRoot
$VersionFile = Join-Path $ContribRoot 'VERSION'
$Version = if (Test-Path $VersionFile) {
    (Get-Content $VersionFile -Raw).Trim()
} else {
    '1.2.0'
}
$DistDir = Join-Path $ContribRoot 'dist'
$Staging = Join-Path $env:TEMP "openlp-songstats-pack-$Version"

$ZipImport = Join-Path $DistDir "songstats-openlp-$Version-import.zip"
$ZipContrib = Join-Path $DistDir "songstats-openlp-$Version-contrib.zip"

$installPl = @"
Song Stats $Version — instalacja (OpenLP 4+, community / contrib)
================================================================

Wymaga: OpenLP z obsługą wtyczek community (katalog DataDir/contrib).
Zależności: requests (zwykle dołączone do OpenLP).

--- Sposób A: archiwum *-import.zip (polecane) ---

1. Ustawienia → Zarządzaj wtyczkami → Importuj wtyczkę community (jeśli dostępne),
   LUB ręcznie:
2. Narzędzia → Otwórz folder danych.
3. Wejdź do podfolderu ``contrib`` (jeśli nie ma — utwórz).
4. Rozpakuj zawartość *-import.zip tak, aby powstało:
   ``contrib\plugins\songstats\songstatsplugin.py``
5. Zrestartuj OpenLP.
6. Ustawienia → Zarządzaj wtyczkami → Song Stats → Aktywny.

--- Sposób B: archiwum *-contrib.zip ---

Rozpakuj całość do folderu danych OpenLP (tam gdzie jest ``songs/``, ``themes/``),
np. ``%APPDATA%\openlp\data\`` — powinien powstać katalog ``contrib\`` z ``__init__.py``.

--- Konfiguracja ---

Ustawienia → Song Stats:
  API base: https://piesni.swietochlowicekwch.pl/api
  Połącz z kontem (przeglądarka) — push i statystyki live.

"@

function Reset-Staging {
    if (Test-Path $Staging) {
        Remove-Item -Recurse -Force $Staging
    }
    New-Item -ItemType Directory -Force -Path $Staging | Out-Null
}

function Copy-ContribTree($destContrib) {
    New-Item -ItemType Directory -Force -Path $destContrib | Out-Null
    Copy-Item (Join-Path $ContribRoot '__init__.py') $destContrib -Force
    Copy-Item (Join-Path $ContribRoot 'plugins') (Join-Path $destContrib 'plugins') -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

# --- Import zip: root = plugins/songstats/ (+ manifest for GUI) ---
Reset-Staging
$importRoot = Join-Path $Staging 'plugins'
Copy-Item (Join-Path $ContribRoot 'plugins\songstats') (Join-Path $importRoot 'songstats') -Recurse -Force
$manifestSrc = Join-Path $ContribRoot 'plugins\songstats\openlp-plugin.json'
$manifestDst = Join-Path $importRoot 'songstats\openlp-plugin.json'
if (Test-Path $manifestSrc) {
    Copy-Item $manifestSrc $manifestDst -Force
    try {
        $json = Get-Content $manifestDst -Raw | ConvertFrom-Json
        $json.version = $Version
        $json | ConvertTo-Json -Depth 4 | Set-Content $manifestDst -Encoding UTF8
    } catch {
        Write-Warning "Could not patch openlp-plugin.json version: $_"
    }
} else {
    $manifest = @{
        id = 'songstats'
        name = 'KWCH Swietochlowice plugin'
        version = $Version
        openlp_min = '4.0'
        module = 'contrib.plugins.songstats.songstatsplugin'
        plugin_class = 'SongStatsPlugin'
        description = 'Live presentation stats and sync with KWCH piesni API.'
    } | ConvertTo-Json -Depth 4
    Set-Content -Path $manifestDst -Value $manifest -Encoding UTF8
}
Set-Content -Path (Join-Path $Staging 'INSTALL_PL.txt') -Value $installPl -Encoding UTF8
if (Test-Path $ZipImport) { Remove-Item $ZipImport -Force }
Compress-Archive -Path (Join-Path $Staging '*') -DestinationPath $ZipImport -CompressionLevel Optimal

# --- Full contrib zip: root = contrib/ (extract into DataDir) ---
Reset-Staging
$dataLayout = Join-Path $Staging 'contrib'
Copy-ContribTree $dataLayout
Set-Content -Path (Join-Path $Staging 'INSTALL_PL.txt') -Value $installPl -Encoding UTF8
if (Test-Path $ZipContrib) { Remove-Item $ZipContrib -Force }
Compress-Archive -Path (Join-Path $Staging '*') -DestinationPath $ZipContrib -CompressionLevel Optimal

Remove-Item -Recurse -Force $Staging

$Releases = Join-Path $ContribRoot 'releases'
New-Item -ItemType Directory -Force -Path $Releases | Out-Null
Copy-Item $ZipImport (Join-Path $Releases (Split-Path $ZipImport -Leaf)) -Force
Copy-Item $ZipContrib (Join-Path $Releases (Split-Path $ZipContrib -Leaf)) -Force

Write-Host "Built:"
Write-Host "  $ZipImport"
Write-Host "  (copy) $(Join-Path $Releases (Split-Path $ZipImport -Leaf))"
Write-Host "     -> unzip into DataDir\contrib  (or use community plugin import)"
Write-Host "  $ZipContrib"
Write-Host "     -> unzip into DataDir (parent of songs/, themes/)"