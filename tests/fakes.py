# -*- coding: utf-8 -*-
"""Test doubles — no OpenLP install required."""


class FakeSettings:
    """Minimal QSettings-like store for plugin helpers."""

    def __init__(self, data=None):
        self._data = dict(data or {})

    def value(self, key, default=None):
        if key not in self._data:
            return default
        return self._data[key]

    def setValue(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)


def fake_jwt_payload(payload: dict) -> str:
    """Unsigned JWT-shaped string (plugin decodes payload only)."""
    import base64
    import json

    def b64(obj):
        raw = json.dumps(obj, separators=(',', ':')).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    header = b64({'alg': 'none', 'typ': 'JWT'})
    body = b64(payload)
    return '{0}.{1}.sig'.format(header, body)