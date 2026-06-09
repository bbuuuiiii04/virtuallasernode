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


def sanitize_model(model: dict[str, Any]) -> dict[str, Any]:
    """Sanitize dirty CV artifacts from the model in-memory."""
    s_model = copy.deepcopy(model)
    spatial_channels = ["CH6", "CH7", "CH15", "CH16", "CH17"]
    for ch_name in spatial_channels:
        if ch_name in s_model.get("channels", {}):
            for bank in s_model["channels"][ch_name].get("banks", []):
                if bank.get("behavior") == "color_animated":
                    # Re-classify as spatial based on its intent
                    bank["behavior"] = "position" if ch_name in ["CH6", "CH7", "CH15", "CH16"] else "zoom"
    s_model["_sanitized"] = True
    return s_model


def compose_fixture_model(channels: list[int] | tuple[int, ...], model: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return decoded fixture state plus measured-model metadata."""
    model = model or load_fixture_model()
    if not model.get("_sanitized"):
        model = sanitize_model(model)
    
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

    # Derive CH7xCH16 coverage status from the model's composition rules
    ch7x16_comp = next(
        (c for c in model.get("interactions", {}).get("compositional", [])
         if "CH7" in c.get("channels", []) and "CH16" in c.get("channels", [])),
        None,
    )
    ch7x16_status = (
        "measured_interfere" if ch7x16_comp and ch7x16_comp.get("rule") not in ("insufficient_data", "no_data")
        else "insufficient_data"
    )
    coverage = {
        "dense_validation": "missing",
        "ch7x16": ch7x16_status,
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
    composition_supported = []
    
    for comp in model.get("interactions", {}).get("compositional", []):
        rule = comp.get("rule", "")
        channels_involved = comp.get("channels", [])
        group = comp.get("group", "")
        tag = f"{'x'.join(channels_involved)}->{rule}"
        
        # CH8xCH9: colour speed is already handled inside the decode_36ch _color() call
        if "CH8" in channels_involved and "CH9" in channels_involved:
            composition_supported.append("CH8xCH9->handled_by_decoder")
            
        # CH8xCH18: gradient override (interfere — gradient channel alters colour output)
        elif "CH8" in channels_involved and "CH18" in channels_involved:
            if rule == "interfere" and composed["gradient"] > 0:
                composed["color"]["mode"] = "gradient_override"
                composition_applied.append(tag)
            else:
                composition_supported.append(tag)

        # CH7xCH16: vertical translation interference — measured but not yet
        # reducible to a simple add/multiply formula. The decoder already
        # outputs independent CH7 position + CH16 movement, which is correct
        # for the renderer; the interference means their combined visual
        # effect is non-linear (acknowledged, not corrected at compose time).
        elif "CH7" in channels_involved and "CH16" in channels_involved:
            composition_supported.append(f"{tag}_measured_not_correctable")

        # Remaining interfere / insufficient pairs: acknowledged, no runtime
        # correction attempted. Decoder outputs are passed through as-is.
        elif rule in ("interfere", "insufficient_reference_rows"):
            composition_supported.append(f"{tag}_passthrough")

        # Orientation triple: compose — each axis decoded independently by
        # _angle_or_speed(), which is the correct decomposition.
        elif "CH12" in channels_involved and "CH13" in channels_involved and "CH14" in channels_involved:
            composition_supported.append(f"{tag}_handled_by_decoder")

        else:
            composition_missing.append({"channels": channels_involved, "reason": f"{rule}_not_implemented"})

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
            "composition_supported": composition_supported,
            "gating_missing": gating_missing,
            "gating_partial": gating_partial,
            "unsupported": ["higher_order_validation_pending", "118_dense_missing"],
            "coverage": coverage,
        },
    }
