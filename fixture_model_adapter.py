"""Composition adapter for measured fixture_model.json.

The adapter augments decoded fixture state; it does not replace or alter the
decode_36ch() contract consumed by the renderer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fixtures import decode_36ch

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "data" / "fixture_model.json"


def load_fixture_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def compose_fixture_model(channels: list[int] | tuple[int, ...], model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return decoded fixture state plus measured-model metadata.

    The decoded payload remains under ``decoded`` so callers can opt in without
    depending on any new field names inside decode_36ch().
    """
    model = model or load_fixture_model()
    decoded = decode_36ch(list(channels))
    ch = {f"CH{i + 1}": int(v) for i, v in enumerate(channels[:19])}
    gate_flags = []
    for gate in model.get("interactions", {}).get("gating", []):
        predicate = gate.get("gate", {})
        channel = predicate.get("channel")
        if not channel or channel not in ch:
            continue
        val = ch[channel]
        op = predicate.get("op")
        active = (
            (op == "in_range" and int(predicate.get("lo", 0)) <= val <= int(predicate.get("hi", 255)))
            or (op == "eq" and val == int(predicate.get("value", -1)))
            or (op == "gte" and val >= int(predicate.get("value", 0)))
            or (op == "lte" and val <= int(predicate.get("value", 255)))
        )
        gate_flags.append({"gate": gate, "active": active})
    return {
        "decoded": decoded,
        "fixture_model": {
            "model_version": model.get("model_version"),
            "model_status": model.get("model_status"),
            "ch1_19": ch,
            "gate_flags": gate_flags,
            "composition": model.get("composition", {}),
            "unsupported": [] if model.get("model_status") == "measured" else ["model_not_fully_measured"],
        },
    }
