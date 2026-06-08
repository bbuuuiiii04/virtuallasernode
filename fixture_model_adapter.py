"""Composition adapter for measured fixture_model.json.

The adapter augments decoded fixture state; it does not replace or alter the
decode_36ch() contract consumed by the renderer.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

try:
    from .fixtures import decode_36ch
except ImportError:
    from fixtures import decode_36ch

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "data" / "fixture_model.json"


def load_fixture_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _sanitize_model(model: dict[str, Any]) -> dict[str, Any]:
    """Sanitize dirty CV artifacts from the model in-memory."""
    # Reject color_animated behavior on spatial channels unless it's a color channel
    spatial_channels = ["CH6", "CH7", "CH15", "CH16", "CH17"]
    for ch_name in spatial_channels:
        if ch_name in model.get("channels", {}):
            for bank in model["channels"][ch_name].get("banks", []):
                if bank.get("behavior") == "color_animated":
                    # Re-classify as spatial based on its intent
                    bank["behavior"] = "position" if ch_name in ["CH6", "CH7", "CH15", "CH16"] else "zoom"
    return model


def compose_fixture_model(channels: list[int] | tuple[int, ...], model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return decoded fixture state plus measured-model metadata."""
    model = model or load_fixture_model()
    model = _sanitize_model(model)
    
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
    
    # 0. Confidence Flagging
    confidence = "missing_data"
    model_status = model.get("model_status", "unknown")
    if model_status == "measured":
        # Missing 118 dense captures & CH7x16 matrix prevents us from declaring "exact"
        confidence = "measured_estimated"
        
    # 1. Apply gating masks (Base)
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

    # 2. Ordered Transformations Pipeline
    # Base -> Pos (CH6/7) -> Move (CH15/16) -> Rot (12/13/14) -> Zoom (17) -> Wave (19) -> Color
    
    for comp in model.get("interactions", {}).get("compositional", []):
        rule = comp.get("rule", "")
        channels_involved = comp.get("channels", [])
        
        # Pos -> Move
        if "CH6" in channels_involved and "CH15" in channels_involved and rule == "multiply":
            if composed["movement"]["h"]["mode"] == "position":
                move_h = composed["movement"]["h"]["val"] / 127.0
                composed["position"]["x"] = round(composed["position"]["x"] * move_h, 3)
                
        # Move -> Wave
        if "CH15" in channels_involved and "CH19" in channels_involved and rule == "add":
            if composed["movement"]["h"]["mode"] == "position" and composed["waves"]["axis"] == "x":
                composed["movement"]["h"]["val"] = min(127, composed["movement"]["h"]["val"] + composed["waves"]["speed"])
                
        # Color -> Gradient
        if "CH8" in channels_involved and "CH18" in channels_involved and rule == "override_by_CH18":
            if composed["gradient"] > 0:
                composed["color"]["mode"] = "gradient_override"

    return {
        "decoded": decoded,
        "composed": composed,
        "fixture_model": {
            "model_version": model.get("model_version"),
            "model_status": model_status,
            "confidence": confidence,
            "ch1_19": ch,
            "gate_flags": gate_flags,
            "composition": model.get("composition", {}),
            "unsupported": ["higher_order_validation_pending", "118_dense_missing", "ch7x16_missing"],
        },
    }
