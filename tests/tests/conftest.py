# -*- coding: utf-8 -*-
"""
Standalone test harness: fake DataDir/contrib on sys.path + OpenLP stubs.

Run from repo root:  python -m pytest tests/
"""
from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_DATADIR = REPO_ROOT / 'tests' / 'fake_datadir'
FAKE_CONTRIB = FAKE_DATADIR / 'contrib'


def _install_openlp_stubs():
    """Enough of OpenLP for contrib.plugins.songstats.lib imports."""

    def translate(namespace, text, *args, **kwargs):
        if args or kwargs:
            try:
                return text.format(*args, **kwargs)
            except (KeyError, IndexError):
                return text
        return text

    for name in list(sys.modules.keys()):
        if name.startswith('openlp.'):
            return

    openlp = types.ModuleType('openlp')
    core = types.ModuleType('openlp.core')
    common = types.ModuleType('openlp.core.common')
    i18n = types.ModuleType('openlp.core.common.i18n')
    registry_mod = types.ModuleType('openlp.core.common.registry')
    httputils = types.ModuleType('openlp.core.common.httputils')
    enum_mod = types.ModuleType('openlp.core.common.enum')
    threading_mod = types.ModuleType('openlp.core.threading')

    i18n.translate = translate
    registry_mod.Registry = MagicMock
    httputils.get_proxy_settings = lambda: {}
    enum_mod.PluginStatus = MagicMock()

    class _ThreadWorker:
        def __init__(self):
            self.quit = MagicMock()

    threading_mod.ThreadWorker = _ThreadWorker
    threading_mod.run_thread = lambda *a, **k: None

    common.i18n = i18n
    common.registry = registry_mod
    common.httputils = httputils
    common.enum = enum_mod
    core.common = common
    core.threading = threading_mod
    openlp.core = core

    sys.modules['openlp'] = openlp
    sys.modules['openlp.core'] = core
    sys.modules['openlp.core.common'] = common
    sys.modules['openlp.core.common.i18n'] = i18n
    sys.modules['openlp.core.common.registry'] = registry_mod
    sys.modules['openlp.core.common.httputils'] = httputils
    sys.modules['openlp.core.common.enum'] = enum_mod
    sys.modules['openlp.core.threading'] = threading_mod


def _sync_contrib_tree():
    FAKE_CONTRIB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / '__init__.py', FAKE_CONTRIB / '__init__.py')
    plugins_src = REPO_ROOT / 'plugins'
    plugins_dst = FAKE_CONTRIB / 'plugins'
    shutil.copytree(plugins_src, plugins_dst, dirs_exist_ok=True)
    for cache in plugins_dst.rglob('__pycache__'):
        shutil.rmtree(cache, ignore_errors=True)
    if str(FAKE_DATADIR) not in sys.path:
        sys.path.insert(0, str(FAKE_DATADIR))


@pytest.fixture(scope='session', autouse=True)
def _contrib_test_env():
    _install_openlp_stubs()
    _sync_contrib_tree()
    yield