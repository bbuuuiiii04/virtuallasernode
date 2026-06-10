from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fixtures import decode_36ch  # noqa: E402


def _decode(channels: dict[int, int]) -> dict:
    def ch(n: int) -> int:
        return channels.get(n, 0)

    return decode_36ch(ch)


def test_ch1_binary_on_is_full_brightness() -> None:
    # CH1 is a binary on/off gate (NOT a 0-255 dimmer): any CH1>0 is fully on.
    state = _decode({1: 3, 3: 24, 4: 12})
    assert state["power"] is True
    assert state["dimmer"] == 1.0


def test_ch1_binary_on_high_value_is_full_brightness() -> None:
    state = _decode({1: 220, 3: 24, 4: 12})
    assert state["power"] is True
    assert state["dimmer"] == 1.0


def test_ch1_zero_is_off() -> None:
    state = _decode({1: 0, 3: 24, 4: 12})
    assert state["power"] is False
    assert state["dimmer"] == 0.0
