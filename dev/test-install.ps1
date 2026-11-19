$tmpdir = Join-Path $env:TEMP 'openlp-install-dry'
$data = Join-Path $tmpdir 'FakePortable\Data'
Remove-Item -LiteralPath $tmpdir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $data -Force | Out-Null
Set-Content -LiteralPath (Join-Path $data 'OpenLP.ini') -Value "[advanced]`nis portable=true" -Encoding ASCII
$src = Split-Path $PSScriptRoot -Parent
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src 'install.ps1') -DataPath $data
$p = Join-Path $data 'contrib\plugins\songstats\songstatsplugin.py'
if (Test-Path -LiteralPath $p) {
    Write-Host "OK plugin at $p"
    exit 0
}
Write-Host "FAIL missing $p"
exit 1