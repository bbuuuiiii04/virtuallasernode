"""
Calibration loader (single source of truth for tunable parameters).

`calibration.json` (next to this module) holds the renderer's movement/geometry/
beam knobs AND the decoder's calibrated colour order + position blank window.
The renderer fetches it over HTTP; the Python decoder reads it from disk here.

Loading is best-effort: if the file is missing or malformed, callers fall back
to their built-in defaults, so behaviour is identical to the pre-extraction code
and tests that import fixtures.py keep passing without the file present.
"""

import json
import math
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")
_cache = None
_cache_mtime = None


def _read_calibration():
    try:
        mtime = os.path.getmtime(_PATH)
        with open(_PATH, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, None
    if not isinstance(data, dict):
        return {}, mtime
    return data, mtime


def _matches_default_shape(value, default):
    """Return True when `value` is safe to use in place of `default`."""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)) and not isinstance(default, bool):
        return (isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value))
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        if not isinstance(value, list):
            return False
        if not default:
            return True
        if len(value) != len(default):
            return False
        return all(_matches_default_shape(v, d) for v, d in zip(value, default))
    if isinstance(default, dict):
        if not isinstance(value, dict):
            return False
        return all(k in value and _matches_default_shape(value[k], d)
                   for k, d in default.items())
    return isinstance(value, type(default))


def load_calibration():
    """Return the parsed calibration dict, reloading when the file changes."""
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(_PATH)
    except OSError:
        mtime = None
    if _cache is None or mtime != _cache_mtime:
        _cache, _cache_mtime = _read_calibration()
    return _cache


def get(section, key, default):
    """Fetch calibration[section][key], falling back to `default`."""
    data = load_calibration()
    sec = data.get(section, {}) if isinstance(data, dict) else {}
    if not isinstance(sec, dict):
        return default
    value = sec.get(key, default)
    if value is default:
        return default
    return value if _matches_default_shape(value, default) else default
