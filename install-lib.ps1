# Shared helpers for install.ps1 / install-from-github.ps1

function Resolve-OpenLPDataDir {
    param(
        [string]$DataPath = ''
    )

    if ($DataPath) {
        $resolved = $DataPath.TrimEnd('\', '/')
        if (-not (Test-Path -LiteralPath $resolved)) {
            Write-Error "Folder danych nie istnieje: $resolved"
        }
        return $resolved
    }

    if ($env:OPENLP_DATA_PATH) {
        return (Resolve-OpenLPDataDir -DataPath $env:OPENLP_DATA_PATH)
    }

    $default = Join-Path $env:APPDATA 'openlp\data'
    if (Test-Path -LiteralPath $default) {
        return $default
    }

    return $null
}

function Write-OpenLPDataDirHelp {
    Write-Host @'

Nie znaleziono folderu danych OpenLP.

  Instalacja standardowa: uruchom OpenLP raz (powstaje folder w %APPDATA%\openlp\data), potem powtorz instalacje.

  OpenLP portable: uruchom portable raz, potem wskaz folder Data z instalacji, np.:
    .\install.ps1 -DataPath 'D:\OpenLPPortable\Data'

  Mozesz tez ustawic zmienna OPENLP_DATA_PATH na ten sam folder i uruchomic skrypt ponownie.
'@
}