# -*- coding: utf-8 -*-
import pytest

pytest.importorskip('PyQt5')

from contrib.plugins.songstats.lib.syncstatusbar import _circle_pixmap, _short_sync_time


def test_short_sync_time_iso():
    assert '18:30' in _short_sync_time('2026-11-19 18:30:00')
    assert _short_sync_time('') == ''


def test_circle_pixmap_not_empty():
    from PyQt5 import QtGui

    src = QtGui.QPixmap(64, 64)
    src.fill(QtGui.QColor(40, 120, 200))
    result = _circle_pixmap(src, 32, 1.0)
    assert not result.isNull()
    assert result.width() == 32
    assert result.height() == 32