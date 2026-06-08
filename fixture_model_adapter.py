"""Composition adapter for measured fixture_model.json.

The adapter augments decoded fixture state; it does not replace or alter the
decode_36ch() contract consumed by the renderer.
"""
from __future__ import annotations

import copy
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
    decoded = decode_36ch(lambda n: channels[n - 1])
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

    composed = copy.deepcopy(decoded)
    
    # 1. Apply gating masks
    for g in gate_flags:
        if not g["active"]:
            enables = g["gate"].get("enables", "")
            if enables == "all":
                composed["power"] = False
                composed["dimmer"] = 0.0
            elif enables == "CH9":
                composed["color"]["speed"] = "off"
                composed["color"]["animated"] = False
            elif enables == "CH5-CH19 static pattern modifiers":
                composed["zoom"]["mode"] = "off"
                composed["rotation"]["z"]["mode"] = "off"

    # 2. Apply composition rules
    for comp in model.get("interactions", {}).get("compositional", []):
        rule = comp.get("rule", "")
        channels_involved = comp.get("channels", [])
        
        # CH6 x CH15 (translation) -> multiply
        if "CH6" in channels_involved and "CH15" in channels_involved and rule == "multiply":
            if composed["movement"]["h"]["mode"] == "position":
                move_h = composed["movement"]["h"]["val"] / 127.0
                composed["position"]["x"] = round(composed["position"]["x"] * move_h, 3)
                
        # CH15 x CH19 (movement + wave) -> add
        if "CH15" in channels_involved and "CH19" in channels_involved and rule == "add":
            if composed["movement"]["h"]["mode"] == "position" and composed["waves"]["axis"] == "x":
                composed["movement"]["h"]["val"] = min(127, composed["movement"]["h"]["val"] + composed["waves"]["speed"])
                
        # CH8 x CH18 (color + gradient) -> override by CH18
        if "CH8" in channels_involved and "CH18" in channels_involved and rule == "override_by_CH18":
            if composed["gradient"] > 0:
                composed["color"]["mode"] = "gradient_override"

    return {
        "decoded": decoded,
        "composed": composed,
        "fixture_model": {
            "model_version": model.get("model_version"),
            "model_status": model.get("model_status"),
            "ch1_19": ch,
            "gate_flags": gate_flags,
            "composition": model.get("composition", {}),
            "unsupported": [] if model.get("model_status") == "measured" else ["model_not_fully_measured"],
        },
    }
