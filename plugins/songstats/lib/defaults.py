# -*- coding: utf-8 -*-
"""Default QSettings keys for Song Stats (required before set_status at bootstrap)."""
from openlp.core.common.enum import PluginStatus
from openlp.core.common.settings import Settings

from contrib.plugins.songstats.lib.apiutil import DEFAULT_API_BASE, SYNC_PULL_JSON


def register_songstats_settings_defaults():
    Settings.extend_default_settings({
        'songstats/status': PluginStatus.Active,
        'songstats/enabled': True,
        'songstats/master db version': '',
        'songstats/local db version': '',
        'songstats/local catalog drift': False,
        'songstats/local drift since': '',
        'songstats/local drift reason': '',
        'songstats/drift song ids': '',
        'songstats/local drift has deletes': False,
        'songstats/last sync at': '',
        'songstats/last sync status': '',
        'songstats/version url': '',
        'songstats/api base url': DEFAULT_API_BASE,
        'songstats/api token': '',
        'songstats/default language': 'pl',
        'songstats/default songbook': '',
        'songstats/timeout': 30,
        'songstats/api url': '',
        'songstats/church id': '',
        'songstats/logged in user id': '',
        'songstats/openlp client id': '',
        'songstats/auth profile': '',
        'songstats/force auth prompt': False,
        'songstats/web base url': '',
        'songstats/use production default': True,
        'songstats/push on edit': True,
        'songstats/sync bidirectional': False,
        'songstats/sync pull mode': SYNC_PULL_JSON,
        'songstats/sync pull url': '',
        'songstats/sync push url': '',
        'songstats/openlp save url': '',
    })