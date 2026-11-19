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

$installRoots = @(Get-ContribInstallRoots -ResolvedDataRoot $dataRoot)
if ($installRoots.Count -eq 0) {
    Write-Error 'Brak docelowego folderu danych.'
}

foreach ($root in $installRoots) {
    Write-Host "Instalacja do: $root"
    $TargetContrib = Join-Path $root 'contrib'
    New-Item -ItemType Directory -Force -Path $TargetContrib | Out-Null

    foreach ($required in @('__init__.py', 'plugins\songstats\songstatsplugin.py')) {
        $src = Join-Path $SourceContrib ($required -replace '\\', [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $src)) {
            Write-Error "Brak w paczce instalacyjnej: $src"
        }
    }

    Copy-Item -LiteralPath (Join-Path $SourceContrib '__init__.py') -Destination $TargetContrib -Force
    $pluginsDest = Join-Path $TargetContrib 'plugins'
    New-Item -ItemType Directory -Force -Path $pluginsDest | Out-Null
    Copy-Item -LiteralPath (Join-Path $SourceContrib 'plugins\songstats') -Destination (Join-Path $pluginsDest 'songstats') -Recurse -Force
    if (Test-Path -LiteralPath (Join-Path $SourceContrib 'plugins\__init__.py')) {
        Copy-Item -LiteralPath (Join-Path $SourceContrib 'plugins\__init__.py') -Destination $pluginsDest -Force
    }

    $pluginPath = Join-Path $TargetContrib 'plugins\songstats\songstatsplugin.py'
    if (-not (Test-Path -LiteralPath $pluginPath)) {
        Write-Error "Kopiowanie nieudane — brak pliku: $pluginPath"
    }
}

$primaryPlugin = Join-Path $installRoots[0] 'contrib\plugins\songstats\songstatsplugin.py'
$fileInfo = Get-Item -LiteralPath $primaryPlugin
Write-Host ''
Write-Host 'Zainstalowano wtyczke KWCH Swietochlowice.'
Write-Host "Plik (pieśni / portable Data): $primaryPlugin"
Write-Host ('Rozmiar: {0} bajtow, data: {1}' -f $fileInfo.Length, $fileInfo.LastWriteTime)

if ($installRoots.Count -gt 1) {
    $winPlugin = Join-Path $installRoots[-1] 'contrib\plugins\songstats\songstatsplugin.py'
    Write-Host ''
    Write-Host 'OpenLP portable (Windows) laduje wtyczki community z AppData, nie z App\OpenLP\plugins:'
    Write-Host "  $winPlugin"
}

Write-Host ''
Write-Host 'NIE szukaj wtyczki w App\OpenLP\plugins — to tylko wbudowane moduly OpenLP.'
Write-Host ''
Write-Host 'Dalej w OpenLP:'
Write-Host '  1. Zamknij OpenLP calkowicie i uruchom ponownie.'
Write-Host '  2. Ustawienia -> Zarzadzaj wtyczkami.'
Write-Host '  3. Zaznacz KWCH Swietochlowice plugin -> OK.'