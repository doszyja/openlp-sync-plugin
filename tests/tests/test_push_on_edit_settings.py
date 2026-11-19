# -*- coding: utf-8 -*-
"""OpenLP Settings.value accepts only the key (no Qt default argument)."""
from contrib.plugins.songstats.songstatsplugin import SongStatsPlugin


class _OpenLpSettings(object):
    def __init__(self, store):
        self._store = store

    def value(self, key):
        return self._store.get(key)


def test_push_on_edit_enabled_default_when_missing():
    settings = _OpenLpSettings({})
    assert SongStatsPlugin._push_on_edit_enabled(settings) is True


def test_push_on_edit_enabled_respects_false():
    settings = _OpenLpSettings({'songstats/push on edit': False})
    assert SongStatsPlugin._push_on_edit_enabled(settings) is False