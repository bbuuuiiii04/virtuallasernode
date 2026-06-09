#!/usr/bin/env node
"use strict";

const fs = require("fs");
const vm = require("vm");
const path = require("path");

function assert(cond, msg) {
  if (!cond) {
    throw new Error(msg);
  }
}

function approx(a, b, eps = 1e-6) {
  return Math.abs(a - b) <= eps;
}

function makeCtxStub() {
  return {
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    globalCompositeOperation: "source-over",
    lineCap: "round",
    beginPath() {},
    moveTo() {},
    lineTo() {},
    closePath() {},
    fill() {},
    stroke() {},
    arc() {},
    fillRect() {},
    clearRect() {},
    createLinearGradient() {
      return { addColorStop() {} };
    },
    createRadialGradient() {
      return { addColorStop() {} };
    },
  };
}

function makeCanvasStub() {
  return {
    clientWidth: 900,
    clientHeight: 560,
    width: 900,
    height: 560,
    getContext() {
      return makeCtxStub();
    },
  };
}

function buildRenderer() {
  const rendererPath = path.resolve(__dirname, "..", "static", "renderer.js");
  const source = fs.readFileSync(rendererPath, "utf8");
  const context = {
    console,
    performance: { now: () => 1000 },
    window: {
      __VLN_CAL: {},
      __VLN_DEBUG_SOUND_OVERRIDE: false,
      location: { search: "" },
      devicePixelRatio: 1,
      addEventListener() {},
    },
    document: {
      hidden: false,
      addEventListener() {},
    },
    fetch: undefined,
    URLSearchParams,
    requestAnimationFrame() {},
    setTimeout,
    clearTimeout,
    Math,
    Date,
  };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: "renderer.js" });
  const LaserRenderer = context.window.LaserRenderer;
  const lr = new LaserRenderer(makeCanvasStub());
  lr.clock = 1.25;
  return lr;
}

function baseState() {
  return {
    name: "fixture-a",
    universe: 1,
    power: true,
    dimmer: 1,
    size: 128,
    position: { x: 0, y: 0, blanked: false },
    color: { rgb: [255, 255, 255], mode: "solid", speed: "off" },
    strobeOn: false,
    strobeSpeed: 0,
    gradient: 0,
    rotation: { z: { mode: "off" }, x: { mode: "off" }, y: { mode: "off" } },
    movement: { h: { mode: "off", val: 0 }, v: { mode: "off", val: 0 } },
    zoom: { mode: "off", val: 0 },
    scan: { mode: "line" },
    waves: { axis: "off", speed: 0 },
    patternGroup: 0,
    patternIndex: 0,
    dynamic: false,
    control: { sound_gated: false },
    captureLookup: null,
    provenanceLabel: "MEASURED_FIXTURE_MODEL",
    modelStatus: "measured",
    modelConfidence: "measured_estimated",
    layerKind: "primary",
  };
}

function testPowerKill() {
  const lr = buildRenderer();
  const st = baseState();
  st.power = false;
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.visibility.killReason === "power_off", "CH1 off should kill power");
  assert(ms.visibility.visibleAfterStrobe === false, "power kill should hide output");
}

function testPositionBlankKill() {
  const lr = buildRenderer();
  const st = baseState();
  st.position.blanked = true;
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.visibility.killReason === "position_blanked", "blanked pos should kill");
}

function testSoundGateAndOverride() {
  const lr = buildRenderer();
  const st = baseState();
  st.control.sound_gated = true;
  let ms = lr._buildMotionState(st, 0, 1);
  assert(ms.visibility.killReason === "sound_gated", "sound gate should kill without override");
  lr.setSoundOverride(true);
  ms = lr._buildMotionState(st, 0, 1);
  assert(ms.visibility.killReason === null, "sound gate should clear with override");
}

function testMovementModes() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "position", val: 64 };
  st.movement.v = { mode: "speed", val: 200 };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.aim.hMoveMode === "position", "CH15 position mode expected");
  assert(ms.aim.vMoveMode === "speed", "CH16 speed mode expected");
  assert(ms.warnings.includes("CH15_CH16_sine_waveform_approximate_unverified"), "fallback speed warning required");
}

function testSquareStrobeGate() {
  const lr = buildRenderer();
  const st = baseState();
  st.strobeOn = true;
  st.strobeSpeed = 255;
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.strobe.waveform === "square", "strobe must be square");
  assert(typeof ms.strobe.gateOpen === "boolean", "strobe gate should be boolean");
  assert(ms.strobe.phase >= 0 && ms.strobe.phase < 1, "strobe phase should be normalized");
}

function testDrawModeDot() {
  const lr = buildRenderer();
  const st = baseState();
  st.scan.mode = "dot";
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.scan.drawMode === "dot", "CH10 dot should map drawMode dot");
}

function testSecondPatternLayerWarning() {
  const lr = buildRenderer();
  const st = baseState();
  st.layerKind = "second_pattern";
  const ms = lr._buildMotionState(st, 1, 2);
  assert(ms.fixture.layerKind === "second_pattern", "second pattern layer should be marked");
  assert(ms.warnings.includes("second_pattern_decoder_driven_with_warning"), "second pattern warning required");
}

function testMeasuredMotionApplied() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "speed", val: 190 };
  st.strobeOn = true;
  st.strobeSpeed = 180;
  st.captureLookup = {
    hit: true,
    metrics: {
      motion_type: "oscillating",
      loop_duration_estimate: 1.0,
      strobe_frequency_hz: 7.5,
      duty_cycle: 0.25,
      x_range_norm_roi: 0.3,
      y_range_norm_roi: 0.4,
      motion_direction: "right_to_left",
      motion_direction_confidence: 0.91,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.fixture.motionProvenance === "MEASURED_MOTION_ANALYSIS", "measured provenance should be used");
  assert(ms.strobe.source === "MEASURED_MOTION_ANALYSIS", "measured strobe should be used");
  assert(approx(ms.strobe.duty, 0.25), "measured duty expected");
}

function testWarningsForCaptureQualityAndFallback() {
  const lr = buildRenderer();
  const st = baseState();
  st.modelStatus = "unavailable";
  st.modelConfidence = "decoded_fallback";
  st.provenanceLabel = "MANUAL_DECODER";
  st.captureLookup = {
    hit: false,
    fallback_reason: "capture_index_unavailable",
    quality: {
      usable_evidence: false,
      geometry_clipped_low: true,
      recapture_pending_manifest: true,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.warnings.includes("model_not_measured_status"), "missing model warning expected");
  assert(ms.warnings.includes("model_confidence_non_measured"), "model confidence warning expected");
  assert(ms.warnings.includes("manual_decoder_fallback_active"), "manual decoder warning expected");
  assert(ms.warnings.includes("capture_lookup_capture_index_unavailable"), "capture fallback warning expected");
  assert(ms.warnings.includes("capture_quality_usable_evidence_false"), "capture quality usable warning expected");
  assert(ms.warnings.includes("capture_quality_geometry_clipped_low"), "capture geometry warning expected");
  assert(ms.warnings.includes("capture_quality_recapture_pending"), "capture recapture warning expected");
}

function testFixtureMetadataAndSecondPatternDiagnostics() {
  const lr = buildRenderer();
  const st = baseState();
  st.name = "fixture-b";
  st.universe = 3;
  st.layerKind = "second_pattern";
  const ms = lr._buildMotionState(st, 1, 2);
  assert(ms.fixture.name === "fixture-b", "fixture name should be carried");
  assert(ms.fixture.universe === 3, "fixture universe should be carried");
  assert(ms.fixture.layerKind === "second_pattern", "layer kind should be second pattern");
  assert(ms.warnings.includes("second_pattern_decoder_driven_with_warning"), "second pattern warning expected");
}

function testInterpCarriesPowerAndPosition() {
  const lr = buildRenderer();
  const p = baseState();
  const n = baseState();
  n.position = { x: 0.2, y: -0.3, blanked: true };
  n.power = true;
  n.dimmer = 0.8;
  const st = lr._interp(p, n, 1);
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.visibility.power === true, "interpolated state should carry power");
  assert(ms.visibility.positionBlanked === true, "interpolated state should carry position blanked");
  assert(ms.visibility.killReason === "position_blanked", "blanking kill should survive interpolation");
}

function run() {
  const tests = [
    testPowerKill,
    testPositionBlankKill,
    testSoundGateAndOverride,
    testMovementModes,
    testSquareStrobeGate,
    testDrawModeDot,
    testSecondPatternLayerWarning,
    testMeasuredMotionApplied,
    testWarningsForCaptureQualityAndFallback,
    testFixtureMetadataAndSecondPatternDiagnostics,
    testInterpCarriesPowerAndPosition,
  ];
  for (const t of tests) t();
  process.stdout.write(`ok ${tests.length} renderer MotionState checks\n`);
}

run();
