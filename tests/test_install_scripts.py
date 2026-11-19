# -*- coding: utf-8 -*-
"""Sanity checks for Windows install scripts (no PowerShell execution)."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_install_from_github_script_paths_consistent():
    text = (REPO / 'install-from-github.ps1').read_text(encoding='utf-8')
    assert 'Copy-Item -Path $Extracted -Destination $Temp' not in text
    assert 'openlp-sync-plugin-main' in text or 'RepoName-$Branch' in text
    assert '& powershell' in text.lower() or 'powershell.exe' in text.lower()
    assert 'install.ps1' in text


def test_install_ps1_expects_plugins_tree():
    text = (REPO / 'install.ps1').read_text(encoding='utf-8')
    assert "plugins" in text
    assert 'songstats' in text
    assert (REPO / 'plugins' / 'songstats' / 'songstatsplugin.py').is_file()


def test_readme_no_broken_nested_oneliner():
    readme = (REPO / 'README.md').read_text(encoding='utf-8')
    assert 'irm' not in readme or 'nie używaj' in readme.lower() or 'Nie używaj' in readme
    assert 'Join-Path $env:TEMP' in readme
    assert '-File $f' in readme or '-File .\\install-from-github.ps1' in readme