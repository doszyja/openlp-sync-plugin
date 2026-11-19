# Shared helpers for install.ps1 / install-from-github.ps1

function Get-OpenLPRegistryDataPath {
    foreach ($appName in @('OpenLPPortable', 'OpenLP')) {
        $key = "HKCU:\Software\OpenLP\$appName\advanced"
        if (-not (Test-Path -LiteralPath $key)) {
            continue
        }
        $custom = (Get-ItemProperty -LiteralPath $key -Name 'data path' -ErrorAction SilentlyContinue).'data path'
        if ($custom) {
            $p = $custom.ToString().Trim()
            if ($p -and (Test-Path -LiteralPath $p)) {
                return $p
            }
        }
    }
    return $null
}

function Get-OpenLPDataPathFromIni {
    param([string]$IniPath)

    if (-not (Test-Path -LiteralPath $IniPath)) {
        return $null
    }

    $iniDir = Split-Path -Parent $IniPath
    $inAdvanced = $false
    $dataPath = $null
    $isPortable = $false

    foreach ($line in [System.IO.File]::ReadLines($IniPath)) {
        if ($line -match '^\s*\[advanced\]\s*$') {
            $inAdvanced = $true
            continue
        }
        if ($line -match '^\s*\[') {
            $inAdvanced = $false
            continue
        }
        if (-not $inAdvanced) {
            continue
        }
        if ($line -match '^\s*data\s+path\s*=\s*(.+)\s*$') {
            $dataPath = $matches[1].Trim()
        }
        if ($line -match '^\s*is\s+portable\s*=\s*true\s*$') {
            $isPortable = $true
        }
    }

    if ($dataPath -and (Test-Path -LiteralPath $dataPath)) {
        return $dataPath
    }
    if ($isPortable -and (Test-Path -LiteralPath $iniDir)) {
        return $iniDir
    }
    return $null
}

function Add-OpenLPIniCandidate {
    param([string[]]$List, [hashtable]$Seen, [string]$IniPath)

    if (-not $IniPath -or -not (Test-Path -LiteralPath $IniPath)) {
        return
    }
    $key = $IniPath.ToLowerInvariant()
    if (-not $Seen.ContainsKey($key)) {
        $Seen[$key] = $true
        $List += $IniPath
    }
    return ,$List
}

function Find-OpenLPIniUnder {
    param(
        [string]$BaseDir,
        [string[]]$RelativePaths
    )

    $found = @()
    if (-not $BaseDir -or -not (Test-Path -LiteralPath $BaseDir)) {
        return $found
    }
    foreach ($rel in $RelativePaths) {
        $ini = Join-Path $BaseDir $rel
        if (Test-Path -LiteralPath $ini) {
            $found += $ini
        }
    }
  # common unpacked layout: <dir>/Data/OpenLP.ini next to OpenLP.exe
    try {
        foreach ($child in Get-ChildItem -LiteralPath $BaseDir -Directory -ErrorAction SilentlyContinue) {
            $ini = Join-Path $child.FullName 'Data\OpenLP.ini'
            if (Test-Path -LiteralPath $ini) {
                $found += $ini
            }
        }
    } catch {
        # ignore
    }
    return $found
}

function Find-OpenLPIniFiles {
    $found = @()
    $seen = @{}

    $relative = @(
        'Data\OpenLP.ini',
        'OpenLPPortable\Data\OpenLP.ini',
        'OpenLP\Data\OpenLP.ini'
    )

    $profileDirs = @(
        [Environment]::GetFolderPath('Desktop'),
        [Environment]::GetFolderPath('MyDocuments'),
        (Join-Path $env:USERPROFILE 'Downloads'),
        $env:USERPROFILE
    )
    foreach ($dir in $profileDirs | Select-Object -Unique) {
        foreach ($ini in Find-OpenLPIniUnder -BaseDir $dir -RelativePaths $relative) {
            $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
        }
    }

    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }) {
        foreach ($ini in Find-OpenLPIniUnder -BaseDir $pf -RelativePaths $relative) {
            $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
        }
        foreach ($name in @('OpenLPPortable', 'OpenLP')) {
            $ini = Join-Path $pf "$name\Data\OpenLP.ini"
            $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
        }
    }

    $localPrograms = Join-Path $env:LOCALAPPDATA 'Programs'
    if (Test-Path -LiteralPath $localPrograms) {
        foreach ($ini in Find-OpenLPIniUnder -BaseDir $localPrograms -RelativePaths $relative) {
            $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
        }
    }

    foreach ($drive in [System.IO.DriveInfo]::GetDrives()) {
        if (-not $drive.IsReady -or $drive.DriveType -ne 'Fixed') {
            continue
        }
        $root = $drive.RootDirectory.FullName.TrimEnd('\')
        foreach ($name in @('OpenLPPortable', 'OpenLP')) {
            $ini = Join-Path $root "$name\Data\OpenLP.ini"
            $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
        }
        try {
            foreach ($child in Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue) {
                foreach ($name in @('OpenLPPortable', 'OpenLP')) {
                    $ini = Join-Path $child.FullName "$name\Data\OpenLP.ini"
                    $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
                    $ini = Join-Path $child.FullName 'Data\OpenLP.ini'
                    $found = Add-OpenLPIniCandidate -List $found -Seen $seen -IniPath $ini
                }
            }
        } catch {
            # ignore
        }
    }

    return $found
}

function Discover-OpenLPDataDirs {
    $candidates = @()

    $reg = Get-OpenLPRegistryDataPath
    if ($reg) {
        $candidates += $reg
    }

    foreach ($ini in Find-OpenLPIniFiles) {
        $fromIni = Get-OpenLPDataPathFromIni -IniPath $ini
        if ($fromIni) {
            $candidates += $fromIni
        }
    }

    $unique = @()
    $seen = @{}
    foreach ($p in $candidates) {
        $norm = (Resolve-Path -LiteralPath $p).Path
        if (-not $seen.ContainsKey($norm)) {
            $seen[$norm] = $true
            $unique += $norm
        }
    }
    return $unique
}

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

    $discovered = @(Discover-OpenLPDataDirs)
    if ($discovered.Count -eq 1) {
        Write-Host "Wykryto folder danych OpenLP: $($discovered[0])"
        return $discovered[0]
    }
    if ($discovered.Count -gt 1) {
        Write-Host 'Znaleziono kilka instalacji OpenLP — podaj folder jawnie parametrem -DataPath:'
        foreach ($p in $discovered) {
            Write-Host "  $p"
        }
        return $null
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

  Instalacja standardowa: uruchom OpenLP raz (powstaje %APPDATA%\openlp\data), potem powtorz instalacje.

  OpenLP portable: uruchom portable raz, potem podaj folder Data, np.:
    -DataPath 'D:\OpenLPPortable\Data'

  (Skrypt sam szuka OpenLP.ini i wpisu w rejestrze — jesli nic nie znalazl, sciezka musi byc podana recznie.)
'@
}