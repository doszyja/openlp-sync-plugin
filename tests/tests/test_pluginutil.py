# -*- coding: utf-8 -*-
from contrib.plugins.songstats.lib.pluginutil import get_remote_id


def test_get_remote_id_from_comments():
    comments = 'songstats:remote_id=507f1f77bcf86cd799439011\nnote'
    assert get_remote_id(comments) == '507f1f77bcf86cd799439011'


def test_get_remote_id_missing():
    assert get_remote_id('') is None
    assert get_remote_id('no marker here') is None