# Download latest plugin tree from GitHub and install into OpenLP DataDir.
param(
    [string]$Repo = 'doszyja/openlp-sync-plugin',
    [string]$Branch = 'main',
    [string]$DataPath = ''
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
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Pobieranie $Repo ($Branch)..."
try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
} catch {
    Write-Error "Nie mozna pobrac archiwum ($ZipUrl). Czy repo jest publiczne i galaz $Branch istnieje?"
}

if (-not (Test-Path -LiteralPath $ZipPath) -or (Get-Item -LiteralPath $ZipPath).Length -lt 100) {
    Write-Error 'Pusty lub uszkodzony plik ZIP — sprawdz URL repozytorium.'
}

Expand-Archive -LiteralPath $ZipPath -DestinationPath $env:TEMP -Force
Remove-Item -LiteralPath $ZipPath -Force

$installScript = Join-Path $Extracted 'install.ps1'
$installLib = Join-Path $Extracted 'install-lib.ps1'
$pluginFile = Join-Path $Extracted 'plugins\songstats\songstatsplugin.py'

if (-not (Test-Path -LiteralPath $installScript)) {
    Write-Error "Brak install.ps1 w ($Extracted). Sprawdz galaz $Branch lub strukture repo."
}
if (-not (Test-Path -LiteralPath $installLib)) {
    Write-Error "Brak install-lib.ps1 w archiwum — zaktualizuj repozytorium."
}
if (-not (Test-Path -LiteralPath $pluginFile)) {
    Write-Error "Brak plugins\songstats w archiwum — to nie jest pelne repo contrib."
}

. $installLib
$resolvedData = Resolve-OpenLPDataDir -DataPath $DataPath
if (-not $resolvedData) {
    Write-OpenLPDataDirHelp
    exit 1
}

$installArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $installScript,
    '-DataPath', $resolvedData
)
& powershell.exe @installArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "install.ps1 zakonczyl sie bledem (kod $LASTEXITCODE)."
}

$installedRoots = @(Get-ContribInstallRoots -ResolvedDataRoot $resolvedData)
$found = $false
foreach ($root in $installedRoots) {
    $p = Join-Path $root 'contrib\plugins\songstats\songstatsplugin.py'
    if (Test-Path -LiteralPath $p) {
        $found = $true
        break
    }
}
if (-not $found) {
    Write-Error 'Po instalacji brak pliku wtyczki w zadnym z docelowych folderow.'
}

Write-Host 'Gotowe.'