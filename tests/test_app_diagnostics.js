#!/usr/bin/env node
"use strict";

// Guards BLOCKER 1: the SSE onmessage handler in static/app.js must not throw,
// and the "Headline Authority" diagnostics line must be a real element returned
// by appendLine() so it can be colour-styled. Before the fix appendLine()
// returned undefined and `headline.style.color = ...` threw inside onmessage,
// crashing the whole diagnostics panel / render feed.

const fs = require("fs");
const vm = require("vm");
const path = require("path");

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const ctxStub = {
  fillStyle: "", strokeStyle: "", lineWidth: 1,
  globalCompositeOperation: "source-over", lineCap: "round",
  beginPath() {}, moveTo() {}, lineTo() {}, closePath() {}, fill() {},
  stroke() {}, arc() {}, fillRect() {}, clearRect() {},
  createLinearGradient() { return { addColorStop() {} }; },
  createRadialGradient() { return { addColorStop() {} }; },
};

function makeEl(tag) {
  const el = {
    tagName: (tag || "div").toUpperCase(),
    style: {},
    className: "",
    _text: "",
    _html: "",
    value: "off",
    children: [],
    width: 900, height: 560, clientWidth: 900, clientHeight: 560,
    set textContent(v) { this._text = v; this.children = []; },
    get textContent() { return this._text; },
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    appendChild(c) { this.children.push(c); return c; },
    querySelector() { return makeEl(); },
    addEventListener() {},
    getContext() { return ctxStub; },
  };
  return el;
}

function collectSpansWithColor(node, found) {
  if (!node || !node.children) return found;
  for (const child of node.children) {
    if (child && child.style && child.style.color) found.push(child);
    collectSpansWithColor(child, found);
  }
  return found;
}

function buildContext() {
  const elements = {};
  const document = {
    getElementById(id) {
      if (!elements[id]) elements[id] = makeEl();
      return elements[id];
    },
    createElement() { return makeEl(); },
    addEventListener() {},
    hidden: false,
  };
  let lastEventSource = null;
  class EventSource {
    constructor() {
      this.onopen = null;
      this.onerror = null;
      this.onmessage = null;
      lastEventSource = this;
    }
  }
  const windowStub = {
    __VLN_CAL: {},
    __VLN_DEBUG_SOUND_OVERRIDE: false,
    location: { search: "" },
    devicePixelRatio: 1,
    addEventListener() {},
    localStorage: {
      _data: {},
      getItem(k) { return this._data[k] || null; },
      setItem(k, v) { this._data[k] = String(v); },
    },
  };
  const context = {
    console,
    performance: { now: () => 1000 },
    window: windowStub,
    document,
    EventSource,
    fetch: undefined,
    URLSearchParams,
    requestAnimationFrame() {},
    setInterval() {},
    setTimeout,
    clearTimeout,
    Math,
    Date,
    JSON,
  };
  context.globalThis = context;
  vm.createContext(context);

  const root = path.resolve(__dirname, "..");
  for (const name of ["ch19_wave.js", "fan_motion.js"]) {
    vm.runInContext(
      fs.readFileSync(path.join(root, "archive", "experiments", "quarantine", "static", name), "utf8"),
      context,
      { filename: name },
    );
  }
  const rendererSrc = fs.readFileSync(path.join(root, "static", "renderer.js"), "utf8");
  vm.runInContext(rendererSrc, context, { filename: "renderer.js" });
  context.LaserRenderer = context.window.LaserRenderer;

  const appSrc = fs.readFileSync(path.resolve(__dirname, "..", "static", "app.js"), "utf8");
  vm.runInContext(appSrc, context, { filename: "app.js" });

  return { context, elements, getEventSource: () => lastEventSource };
}

function sampleFixture() {
  return {
    name: "Laser 1",
    universe: 0,
    power: true,
    dimmer: 1,
    color: { rgb: [60, 90, 255], mode: "solid", speed: "off", label: "blue", animated: false },
    pattern: { kind: "static", group: 0, selection: { index: 0, play_all: false }, size: 0 },
    position: { x: 0, y: 0, blanked: false, centered: true },
    rotation: { z: { mode: "off" }, x: { mode: "off" }, y: { mode: "off" } },
    movement: { h: { mode: "off", val: 0 }, v: { mode: "off", val: 0 } },
    zoom: { mode: "off", val: 0 },
    scan: { mode: "line", speed: 0 },
    strobe: { on: false, speed: 0 },
    second_pattern: null,
  };
}

function testOnMessageDoesNotThrowAndHeadlineIsStyled() {
  const { elements, getEventSource } = buildContext();
  const es = getEventSource();
  assert(es && typeof es.onmessage === "function", "app.js should register an SSE onmessage handler");

  const fixture = sampleFixture();
  const frame = {
    universes: {},
    fixtures: [],
    decoded: [fixture],
    composed: [fixture],
    fixture_models: [
      {
        model_status: "measured",
        confidence: "measured_estimated",
        unsupported: [],
        coverage: {},
        composition_applied: [],
        composition_supported: [],
        composition_missing: [],
        gating_missing: [],
        gating_partial: [],
        capture_lookup: {
          hit: true,
          vector_match: true,
          validation_backed: false,
          provenance_label: "EXACT_VECTOR_MATCH",
          fallback_reason: null,
          cue_aliases: [{ cue_id: "a", cue_name: "X" }],
          cue_alias_count: 1,
          cue_identity_resolved: true,
          cue_matches: [{ cue_id: "a", cue_name: "X" }],
        },
      },
    ],
    polls: 1,
  };

  // Must not throw (this is the crash BLOCKER 1 describes).
  es.onmessage({ data: JSON.stringify(frame) });

  const diag = elements["diagnostics"];
  assert(diag && diag.children.length > 0, "diagnostics panel should be populated");
  const styled = collectSpansWithColor(diag, []);
  assert(styled.length > 0, "headline authority element should be returned by appendLine and colour-styled");
}

function run() {
  const tests = [testOnMessageDoesNotThrowAndHeadlineIsStyled];
  for (const t of tests) t();
  process.stdout.write(`ok ${tests.length} app diagnostics checks\n`);
}

run();
