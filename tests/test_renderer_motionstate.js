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

function buildRenderer(ch19Flag, fanMotionFlag) {
  const quarantinePaths = [
    path.resolve(__dirname, "..", "archive", "experiments", "quarantine", "static", "ch19_wave.js"),
    path.resolve(__dirname, "..", "archive", "experiments", "quarantine", "static", "fan_motion.js"),
  ];
  const rendererPath = path.resolve(__dirname, "..", "static", "renderer.js");
  const context = {
    console,
    performance: { now: () => 1000 },
    window: {
      __VLN_CAL: {},
      __VLN_DEBUG_SOUND_OVERRIDE: false,
      __VLN_QUARANTINE_CH19_WAVE: ch19Flag,
      __VLN_QUARANTINE_FAN_MOTION: fanMotionFlag,
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
  for (const p of quarantinePaths) {
    vm.runInContext(fs.readFileSync(p, "utf8"), context, { filename: path.basename(p) });
  }
  vm.runInContext(fs.readFileSync(rendererPath, "utf8"), context, { filename: "renderer.js" });
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
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "horizontal_sweep",
      loop_duration_estimate: 1.0,
      periodic_motion: true,
      loop_confidence: 0.9,
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

function testStrobeGateNoTranslationalOffset() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "speed", val: 200 };
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "strobe_gate",
      loop_duration_estimate: 0.0667,
      periodic_motion: true,
      loop_confidence: 1.0,
      motion_direction: "left_to_right",
      motion_direction_confidence: 0.95,
      x_range_norm_roi: 0.8,
      y_range_norm_roi: 0.8,
      strobe_frequency_hz: 15.0,
      duty_cycle: 0.6,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(approx(ms.aim.hMoveOffset, 0), "strobe_gate must not translate horizontally");
}

function testHorizontalSweepTranslatesHAxisOnly() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "speed", val: 200 };
  st.movement.v = { mode: "speed", val: 200 };
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "horizontal_sweep",
      loop_duration_estimate: 1.0,
      periodic_motion: true,
      loop_confidence: 0.9,
      motion_direction: "rightward",
      motion_direction_confidence: 0.2,
      x_range_norm_roi: 0.3,
      y_range_norm_roi: 0.4,
      strobe_frequency_hz: 10.0,
      duty_cycle: 0.5,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(Math.abs(ms.aim.hMoveOffset) > 1e-6, "horizontal_sweep must translate H even with both axes in speed mode");
  assert(approx(ms.aim.vMoveOffset, 0), "horizontal_sweep must NOT translate V");
}

function testUnknownMotionTypeUsesDecoderFallbackSine() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "speed", val: 200 };
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "oscillating_unmapped",
      loop_duration_estimate: 1.0,
      periodic_motion: true,
      loop_confidence: 0.9,
      strobe_frequency_hz: 10.0,
      duty_cycle: 0.5,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.aim.hMoveMode === "speed", "unknown motion h should remain speed mode");
  assert(Math.abs(ms.aim.hMoveOffset) > 1e-6, "unknown motion_type should use decoder-fallback sine (nonzero), not zero");
  assert(ms.warnings.includes("measured_motion_type_unknown_fallback"), "unknown motion_type warning expected");
  assert(ms.warnings.includes("CH15_CH16_sine_waveform_approximate_unverified"), "decoder sine approximation warning expected for unknown fallback");
  assert(ms.fixture.parameterTiers.motion === "DECODER_FALLBACK", "unknown motion tier should be decoder fallback");
}

function testLowConfidenceDirectionUnsigned() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement.h = { mode: "speed", val: 200 };
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "horizontal_sweep",
      loop_duration_estimate: 1.0,
      periodic_motion: true,
      loop_confidence: 1.0,
      motion_direction: "right_to_left",
      motion_direction_confidence: 0.2,
      x_range_norm_roi: 0.3,
      y_range_norm_roi: 0.2,
      strobe_frequency_hz: 10.0,
      duty_cycle: 0.5,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.measured && ms.measured.hSign === 0, "low-confidence direction should be unsigned");
}

function testDominantColorsDriveBeamColor() {
  const lr = buildRenderer();
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "static",
      periodic_motion: false,
      loop_confidence: 0.0,
      dominant_colors: ["blue", "cyan"],
      strobe_frequency_hz: 12.0,
      duty_cycle: 0.5,
    },
  };
  const c0 = lr._beamColor(st, 0);
  const c1 = lr._beamColor(st, 1);
  assert(c0[0] === 60 && c0[1] === 90 && c0[2] === 255, "first dominant color should map to blue palette");
  assert(c1[0] === 40 && c1[1] === 230 && c1[2] === 230, "second dominant color should map to cyan palette");
}

function testMultiDominantColorsCyclePerBeam() {
  const lr = buildRenderer();
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "static",
      periodic_motion: false,
      loop_confidence: 0.0,
      dominant_colors: ["blue", "cyan", "green", "magenta", "red", "white"],
      strobe_frequency_hz: 12.0,
      duty_cycle: 0.5,
    },
  };
  const c0 = lr._beamColor(st, 0);
  const c1 = lr._beamColor(st, 1);
  const c2 = lr._beamColor(st, 2);
  const c6 = lr._beamColor(st, 6);
  assert(c0[0] === 60 && c0[1] === 90 && c0[2] === 255, "beam 0 should be blue palette");
  assert(c1[0] === 40 && c1[1] === 230 && c1[2] === 230, "beam 1 should be cyan palette");
  assert(c2[0] === 40 && c2[1] === 255 && c2[2] === 70, "beam 2 should be green palette");
  assert(c6[0] === 60 && c6[1] === 90 && c6[2] === 255, "beam 6 should wrap back to blue palette");
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.fixture.parameterTiers.color === "MEASURED_PARAM", "multi-color should remain measured");
}

function testHeadlineTierDowngradesWhenAnyParamDecoder() {
  const lr = buildRenderer();
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "static",
      periodic_motion: false,
      loop_confidence: 0.9,
      dominant_colors: ["blue"],
      strobe_frequency_hz: 15.0,
      duty_cycle: 0.6,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.fixture.parameterTiers.color === "MEASURED_PARAM", "color should be measured");
  assert(ms.fixture.parameterTiers.strobe === "MEASURED_PARAM", "strobe should be measured");
  assert(ms.fixture.parameterTiers.count === "DECODER_FALLBACK", "count remains decoder fallback without derived count");
  assert(ms.fixture.headlineTier === "DECODER_FALLBACK", "headline should be minimum tier across params");
}

function testMeasuredLayoutSpreadAndDerivedCountTiers() {
  const lr = buildRenderer();
  lr.setCaptureGeometry({
    combined_bbox: [60, 153, 1219, 581],
    aperture_box_width_px: 495,
    boxes: [
      { label: "image_left", bbox: [60, 156, 554, 578] },
      { label: "image_right", bbox: [646, 153, 1219, 581] },
    ],
  });
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "static",
      periodic_motion: false,
      loop_confidence: 0.9,
      dominant_colors: ["blue"],
      strobe_frequency_hz: 15.0,
      duty_cycle: 0.6,
      angle_range_deg: 24.0,
      density_beam_count_derived: 8,
      density_evidence: "inferred",
    },
  };
  const ms = lr._buildMotionState(st, 0, 2);
  assert(ms.fixture.parameterTiers.spread === "MEASURED_PARAM", "spread should be measured from angle_range_deg");
  assert(ms.fixture.parameterTiers.count === "MEASURED_PARAM", "derived count should be measured tier");
  assert(ms.fixture.parameterTiers.position === "MEASURED_PARAM", "position should use capture geometry");
  assert(ms.warnings.includes("density_evidence_inferred"), "derived density should warn inferred evidence");
}

function testFixtureGeometryOriginMapsLeftAndRight() {
  const lr = buildRenderer();
  const geo = {
    combined_bbox: [60, 153, 1219, 581],
    aperture_box_width_px: 495,
    boxes: [
      { label: "image_left", bbox: [60, 156, 554, 578] },
      { label: "image_right", bbox: [646, 153, 1219, 581] },
    ],
  };
  const dims = { cx: 450, cy: 400, scale: 350 };
  const left = lr._fixtureGeometryOrigin(geo, 0, 2, dims);
  const right = lr._fixtureGeometryOrigin(geo, 1, 2, dims);
  assert(left && right, "both fixture origins should resolve");
  assert(left.ox0 < dims.cx, "left fixture should sit left of center");
  assert(right.ox0 > dims.cx, "right fixture should sit right of center");
  assert(left.apGap > 0 && right.apGap > 0, "aperture gap should be positive");
}

function testMotionExtentPrefersApertureNormalization() {
  const lr = buildRenderer();
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "horizontal_sweep",
      periodic_motion: true,
      loop_confidence: 0.9,
      loop_duration_estimate: 1.0,
      motion_direction: "left_to_right",
      motion_direction_confidence: 0.9,
      x_range_norm_aperture: 0.42,
      x_range_norm_roi: 0.05,
      y_range_norm_aperture: 0.18,
      y_range_norm_roi: 0.9,
    },
  };
  const measured = lr._extractMeasuredMotion(st);
  assert(approx(measured.xExtent, 0.42), "x extent should prefer aperture normalization");
  assert(approx(measured.yExtent, 0.18), "y extent should prefer aperture normalization");
}

function testValidationFalseNeverEmitsRenderAuthority() {
  const lr = buildRenderer();
  const st = baseState();
  st.captureLookup = {
    hit: true,
    vector_match: true,
    validation_backed: false,
    quality: { usable_evidence: true },
    metrics: {
      motion_type: "horizontal_sweep",
      loop_duration_estimate: 1.2,
      periodic_motion: true,
      loop_confidence: 0.9,
      dominant_colors: ["green"],
      strobe_frequency_hz: 8.0,
      duty_cycle: 0.5,
      motion_direction: "left_to_right",
      motion_direction_confidence: 0.9,
      x_range_norm_roi: 0.2,
      y_range_norm_roi: 0.2,
    },
  };
  const ms = lr._buildMotionState(st, 0, 1);
  const tiers = Object.values(ms.fixture.parameterTiers || {});
  assert(!tiers.includes("EXACT_CAPTURE_RENDER_AUTHORITY"), "validation false should block render-authority tier");
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

function testCh19WaveQuarantinedByDefault() {
  const lr = buildRenderer();
  const st = baseState();
  st.waves = { axis: "x", speed: 64 };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.warnings.includes("CH19_wave_quarantined_off"), "CH19 active but quarantined off by default");
}

function testFanMotionQuarantinedRigidByDefault() {
  const lr = buildRenderer();
  const st = baseState();
  st.movement = { h: { mode: "speed", val: 96 }, v: { mode: "off", val: 0 } };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.warnings.includes("fan_motion_quarantined_rigid_off"), "motion active, fan quarantine off");
}

function testFanMotionScanPhaseWarning() {
  const lr = buildRenderer(undefined, "scan_phase");
  const st = baseState();
  st.movement = { h: { mode: "speed", val: 96 }, v: { mode: "off", val: 0 } };
  const ms = lr._buildMotionState(st, 0, 1);
  assert(ms.warnings.includes("fan_motion_quarantine_scan_phase_experimental"), "scan_phase warning");
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
    testStrobeGateNoTranslationalOffset,
    testHorizontalSweepTranslatesHAxisOnly,
    testUnknownMotionTypeUsesDecoderFallbackSine,
    testLowConfidenceDirectionUnsigned,
    testDominantColorsDriveBeamColor,
    testMultiDominantColorsCyclePerBeam,
    testHeadlineTierDowngradesWhenAnyParamDecoder,
    testMeasuredLayoutSpreadAndDerivedCountTiers,
    testFixtureGeometryOriginMapsLeftAndRight,
    testMotionExtentPrefersApertureNormalization,
    testValidationFalseNeverEmitsRenderAuthority,
    testWarningsForCaptureQualityAndFallback,
    testFixtureMetadataAndSecondPatternDiagnostics,
    testCh19WaveQuarantinedByDefault,
    testFanMotionQuarantinedRigidByDefault,
    testFanMotionScanPhaseWarning,
    testInterpCarriesPowerAndPosition,
  ];
  for (const t of tests) t();
  process.stdout.write(`ok ${tests.length} renderer MotionState checks\n`);
}

run();
