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
    s_model = copy.deepcopy(model)
    spatial_channels = ["CH6", "CH7", "CH15", "CH16", "CH17"]
    for ch_name in spatial_channels:
        if ch_name in s_model.get("channels", {}):
            for bank in s_model["channels"][ch_name].get("banks", []):
                if bank.get("behavior") == "color_animated":
                    # Re-classify as spatial based on its intent
                    bank["behavior"] = "position" if ch_name in ["CH6", "CH7", "CH15", "CH16"] else "zoom"
    return s_model


def compose_fixture_model(channels: list[int] | tuple[int, ...], model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return decoded fixture state plus measured-model metadata."""
    model = model or load_fixture_model()
    model = _sanitize_model(model)
    
    # TASK 1: Normalize channels
    norm_channels = []
    for c in list(channels)[:36]:
        try:
            val = int(c)
        except (ValueError, TypeError):
            val = 0
        norm_channels.append(max(0, min(255, val)))
    norm_channels.extend([0] * (36 - len(norm_channels)))
    
    decoded = decode_36ch(lambda n: norm_channels[n - 1])
    ch = {f"CH{i + 1}": norm_channels[i] for i in range(19)}
    
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
        confidence = "measured_estimated"

    coverage = {
        "dense_validation": "missing",
        "ch7x16": "insufficient_data",
        "higher_order": "pending",
        "renderer_contract": "decoded_shape_composed_values"
    }
        
    # 1. Apply gating masks (Base)
    gating_missing = []
    gating_partial = []
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
                gating_partial.append("CH3_static_modifier_gate_partial")
            else:
                gating_missing.append(enables)

    # 2. Ordered Transformations Pipeline
    # Base -> Pos (CH6/7) -> Move (CH15/16) -> Rot (12/13/14) -> Zoom (17) -> Wave (19) -> Color
    
    composition_applied = []
    composition_missing = []
    
    for comp in model.get("interactions", {}).get("compositional", []):
        rule = comp.get("rule", "")
        channels_involved = comp.get("channels", [])
        
        # Pos -> Move
        if "CH6" in channels_involved and "CH15" in channels_involved and rule == "multiply":
            if composed["movement"]["h"]["mode"] == "position":
                move_h = composed["movement"]["h"]["val"] / 127.0
                composed["position"]["x"] = round(composed["position"]["x"] * move_h, 3)
            composition_applied.append(f"CH6xCH15->{rule}")
                
        # Move -> Wave
        elif "CH15" in channels_involved and "CH19" in channels_involved and rule == "add":
            if composed["movement"]["h"]["mode"] == "position" and composed["waves"]["axis"] == "x":
                composed["movement"]["h"]["val"] = min(127, composed["movement"]["h"]["val"] + composed["waves"]["speed"])
            composition_applied.append(f"CH15xCH19->{rule}")
                
        # Color -> Gradient
        elif "CH8" in channels_involved and "CH18" in channels_involved and rule == "override_by_CH18":
            if composed["gradient"] > 0:
                composed["color"]["mode"] = "gradient_override"
            composition_applied.append(f"CH8xCH18->{rule}")
            
        elif "CH7" in channels_involved and "CH16" in channels_involved:
            composition_missing.append({"channels": channels_involved, "reason": "insufficient_data"})
        elif "CH5" in channels_involved and "CH17" in channels_involved:
            composition_missing.append({"channels": channels_involved, "reason": "interfere_not_implemented"})
        elif "CH12" in channels_involved and "CH15" in channels_involved:
            composition_missing.append({"channels": channels_involved, "reason": "interfere_not_implemented"})
        elif "CH12" in channels_involved and "CH13" in channels_involved and "CH14" in channels_involved:
            composition_missing.append({"channels": channels_involved, "reason": "needs_physical_validation"})
        else:
            composition_missing.append({"channels": channels_involved, "reason": "not_implemented"})

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
            "composition_applied": composition_applied,
            "composition_missing": composition_missing,
            "gating_missing": gating_missing,
            "gating_partial": gating_partial,
            "unsupported": ["higher_order_validation_pending", "118_dense_missing", "ch7x16_missing"],
            "coverage": coverage,
        },
    }
