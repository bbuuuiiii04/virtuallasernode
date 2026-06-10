// VirtualLaserNode — step 6 renderer (AERIAL BEAM view).
// Renders the volumetric laser BEAMS shooting into the haze (what a crowd sees
// in the air), NOT the galvo figure on a wall. Each fixture is a source that
// throws a fan of beams; DMX drives colour, brightness, aim (position), sweep
// (movement), spin (rotation), spread (size/zoom), and strobe. Consumes the SSE
// `decoded` feed; interpolates a fixed time behind latest for smooth motion.

(function () {
  "use strict";
  const TAU = Math.PI * 2;
  const AUTHORITY_TIER = {
    DECODER_FALLBACK: 1,
    MODEL_COMPOSED: 2,
    MEASURED_PARAM: 3,
    EXACT_CAPTURE_RENDER_AUTHORITY: 4,
  };
  const COLOR_PALETTE = {
    red: [255, 40, 40],
    green: [40, 255, 70],
    blue: [60, 90, 255],
    cyan: [40, 230, 230],
    magenta: [255, 60, 220],
    yellow: [255, 230, 60],
    white: [255, 255, 255],
    orange: [255, 150, 40],
    purple: [150, 60, 255],
    pink: [255, 120, 200],
  };

  // ---- Calibration ---------------------------------------------------------
  // Tunable constants live in calibration.json (single source of truth) so the
  // render can be retuned WITHOUT editing code. DEFAULTS below mirror that file
  // exactly; CAL = DEFAULTS overlaid with window.__VLN_CAL (synchronous — used
  // by the headless calib harnesses) and/or /calibration.json (fetched live
  // from the server). Every consumer reads CAL.* so a calibration.json edit +
  // hard-refresh retunes movement/geometry/beam look. USER PRIORITY = movement:
  // rates.* and geometry.{panGain,vShiftGain,inwardLean,spreadAngGain}.
  const DEFAULTS = {
    rates: { spinRps: 0.18, spinAngleMax: Math.PI, sweepMinHz: 0.08,
             sweepMaxHz: 0.9, strobeHz: 16, colorHue: 30, rotPitchYawRps: 0.16 },
    timing: { renderBehindMs: 50, trailFade: 0.38 },
    geometry: { sourceYFrac: 0.72, scaleFrac: 0.62, fixGapFrac: 0.17,
                apGapFrac: 0.085, inwardLean: 0.10, spreadAngGain: 1.7,
                spreadAngMax: 2.4, panGain: 0.5, vShiftGain: 0.70,
                squashMax: 0.6, aimXBlank: 0.95, aimYBlank: 0.50 },
    beam: { halo: 6, mid: 2.4, core: 1.1, srcGlow: 18, coreWhiteBoost: 90,
            srcGlowBoost: 130, tipGlow: 4.5, ambientStrength: 0.085 },
    zoom: { min: 0.55, range: 0.9 },
    dynamic: { spinRate: 0.7, aimXRate: 0.4, aimXAmp: 0.18, spread: 1.2, count: 7,
               colorBase: 0, colorSpread: 14, colorRate: 30 },
    patternShape: {
      folder1: { n: 6, spread: 1.0 }, folder2: { n: 4, spread: 0.7 },
      folder3: { n: 14, spread: 1.4 }, folder4: { n: 20, spread: 1.6 },
      animation: { n: 8, spread: 1.1 },
    },
    color: { gradientSpreadBase: 6, gradientSpreadRange: 26 },
  };
  const BLOCKED_CAL_KEYS = new Set(["__proto__", "prototype", "constructor"]);
  function isPlainObject(v) {
    if (!v || typeof v !== "object" || Array.isArray(v)) return false;
    const proto = Object.getPrototypeOf(v);
    return proto === Object.prototype || proto === null;
  }
  function deepMerge(dst, src, shape) {
    if (!isPlainObject(src) || !isPlainObject(shape)) return dst;
    for (const k of Object.keys(src)) {
      if (BLOCKED_CAL_KEYS.has(k) || !Object.prototype.hasOwnProperty.call(shape, k)) continue;
      const v = src[k];
      const expected = shape[k];
      if (isPlainObject(expected)) {
        if (isPlainObject(dst[k])) deepMerge(dst[k], v, expected);
      } else if (typeof expected === "number") {
        if (typeof v === "number" && Number.isFinite(v)) dst[k] = v;
      }
    }
    return dst;
  }
  const CAL = JSON.parse(JSON.stringify(DEFAULTS));
  if (typeof window !== "undefined" && window.__VLN_CAL) deepMerge(CAL, window.__VLN_CAL, DEFAULTS);
  function loadCalibration() {
    if (typeof fetch !== "function") return Promise.resolve();
    return fetch("/calibration.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (j) deepMerge(CAL, j, DEFAULTS); })
      .catch(() => {});   // no server (file:// harness) -> keep DEFAULTS
  }

  const lerp = (a, b, f) => a + (b - a) * f;

  function hsv(h, s, v) {
    const i = Math.floor(h * 6), f = h * 6 - i;
    const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
    let r, g, b;
    switch (i % 6) {
      case 0: r = v; g = t; b = p; break; case 1: r = q; g = v; b = p; break;
      case 2: r = p; g = v; b = t; break; case 3: r = p; g = q; b = v; break;
      case 4: r = t; g = p; b = v; break; default: r = v; g = p; b = q;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
  }
  const HUE_LUT = [];
  for (let i = 0; i < 256; i++) HUE_LUT.push(hsv(i / 256, 1, 1));

  class LaserRenderer {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.buffer = [];
      this.clock = 0;
      this._lastNow = performance.now();
      let soundOverride = false;
      try {
        const params = new URLSearchParams(window.location.search || "");
        soundOverride = params.get("soundOverride") === "1";
      } catch (e) {}
      this.debug = {
        soundOverride: !!(window.__VLN_DEBUG_SOUND_OVERRIDE || soundOverride),
      };
      this._lastMotionStates = [];
      this._frameMotionStates = [];
      this._captureGeometry = null;
      this._ch19ModeResolved = null;
      this._fanMotionModeResolved = null;
      try {
        if (typeof window !== "undefined" && window.__VLN_CAPTURE_GEOMETRY) {
          this.setCaptureGeometry(window.__VLN_CAPTURE_GEOMETRY);
        }
      } catch (e) {}
      this._resize();
      loadCalibration().then(() => this._resize());   // apply live calibration.json
      window.addEventListener("resize", () => this._resize());
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) { this._lastNow = performance.now(); this.buffer.length = 0; }
      });
      requestAnimationFrame(() => this._loop());
    }

    update(decoded) {
      if (!decoded) return;
      const t = performance.now();
      if (this.buffer.length && t - this.buffer[this.buffer.length - 1].t > 1000)
        this.buffer.length = 0;            // reconnect/first-frame: drop stale
      this.buffer.push({ t, decoded });
      while (this.buffer.length > 10) this.buffer.shift();
    }

    setSoundOverride(enabled) {
      this.debug.soundOverride = !!enabled;
    }

    setCaptureGeometry(geo) {
      this._captureGeometry = (geo && typeof geo === "object") ? geo : null;
    }

    _ch19QuarantineMode() {
      if (this._ch19ModeResolved !== null) return this._ch19ModeResolved;
      const Q = (typeof VLNQuarantineCH19Wave !== "undefined") ? VLNQuarantineCH19Wave : null;
      if (Q && Q.resolveModeFromEnv) {
        this._ch19ModeResolved = Q.resolveModeFromEnv({
          flag: (typeof window !== "undefined") ? window.__VLN_QUARANTINE_CH19_WAVE : null,
          location: (typeof window !== "undefined") ? window.location : null,
        });
      } else {
        this._ch19ModeResolved = "off";
      }
      return this._ch19ModeResolved;
    }

    _ch19WaveActive(st) {
      return !!(st && !st.dynamic && st.waves && st.waves.axis !== "off");
    }

    _drawCh19Beam(ctx, ox, oy, ex, ey, fr, wave, rgb, dim, wscale, spreadAng, metrics) {
      const mode = this._ch19QuarantineMode();
      const Q = (typeof VLNQuarantineCH19Wave !== "undefined") ? VLNQuarantineCH19Wave : null;
      if (!wave || mode === "off" || !Q) {
        this._beam(ctx, ox, oy, ex, ey, rgb, dim, wscale);
        return { ex: ex, ey: ey };
      }
      if (mode === "legacy" && Q.legacySpaghettiPoints) {
        const pts = Q.legacySpaghettiPoints(ox, oy, ex, ey, wave, this.clock);
        this._beam(ctx, pts, rgb, dim, wscale);
        const last = pts[pts.length - 1];
        return { ex: last[0], ey: last[1] };
      }
      if (mode === "fixed" && Q.fixedCoherentEndpoints) {
        const ep = Q.fixedCoherentEndpoints(
          ox, oy, ex, ey, fr, wave, this.clock, spreadAng, this.dims.scale, metrics);
        this._beam(ctx, ox, oy, ep.ex, ep.ey, rgb, dim, wscale);
        return { ex: ep.ex, ey: ep.ey };
      }
      this._beam(ctx, ox, oy, ex, ey, rgb, dim, wscale);
      return { ex: ex, ey: ey };
    }

    _fanMotionQuarantineMode() {
      if (this._fanMotionModeResolved !== null) return this._fanMotionModeResolved;
      const Q = (typeof VLNQuarantineFanMotion !== "undefined") ? VLNQuarantineFanMotion : null;
      if (Q && Q.resolveModeFromEnv) {
        this._fanMotionModeResolved = Q.resolveModeFromEnv({
          flag: (typeof window !== "undefined") ? window.__VLN_QUARANTINE_FAN_MOTION : null,
          location: (typeof window !== "undefined") ? window.location : null,
        });
      } else {
        this._fanMotionModeResolved = "off";
      }
      return this._fanMotionModeResolved;
    }

    _periodicSweepOffset(hz, sign, amp) {
      const hzAbs = Math.abs(Number(hz) || 0);
      const s = sign >= 0 ? 1 : -1;
      if (!hzAbs) return 0;
      const mode = this._fanMotionQuarantineMode();
      const Q = (typeof VLNQuarantineFanMotion !== "undefined") ? VLNQuarantineFanMotion : null;
      if (mode === "sweep_triangle" && Q && Q.speedWaveform) {
        return Q.speedWaveform("sweep_triangle", this.clock, hzAbs, s) * amp;
      }
      return Math.sin(this.clock * TAU * hzAbs * s) * amp;
    }

    _fanMotionChannelsActive(st) {
      if (!st) return false;
      const mh = st.movement && st.movement.h;
      const mv = st.movement && st.movement.v;
      const rz = st.rotation && st.rotation.z;
      return !!(mh && mh.mode !== "off") || !!(mv && mv.mode !== "off")
        || !!(rz && rz.mode === "speed");
    }

    /** Dev preview only — clears cached quarantine mode; not production-default. */
    setQuarantinePreview(opts) {
      opts = opts || {};
      if (typeof window !== "undefined") {
        if (Object.prototype.hasOwnProperty.call(opts, "ch19Wave")) {
          window.__VLN_QUARANTINE_CH19_WAVE = opts.ch19Wave;
        }
        if (Object.prototype.hasOwnProperty.call(opts, "fanMotion")) {
          window.__VLN_QUARANTINE_FAN_MOTION = opts.fanMotion;
        }
        try {
          if (Object.prototype.hasOwnProperty.call(opts, "ch19Wave")) {
            localStorage.setItem("vln_quarantine_ch19", String(opts.ch19Wave || "off"));
          }
          if (Object.prototype.hasOwnProperty.call(opts, "fanMotion")) {
            localStorage.setItem("vln_quarantine_fan", String(opts.fanMotion || "off"));
          }
        } catch (e) {}
      }
      this._ch19ModeResolved = null;
      this._fanMotionModeResolved = null;
    }

    getQuarantinePreview() {
      return {
        ch19Wave: this._ch19QuarantineMode(),
        fanMotion: this._fanMotionQuarantineMode(),
      };
    }

    getDebugState() {
      return {
        soundOverride: !!this.debug.soundOverride,
        motionStates: this._lastMotionStates.slice(),
      };
    }

    _resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      let w = Math.round(this.canvas.clientWidth * dpr);
      let h = Math.round(this.canvas.clientHeight * dpr);
      if (w > 1600) { const k = 1600 / w; w = 1600; h = Math.round(h * k); }
      if (w < 1 || h < 1) return;
      this.canvas.width = w; this.canvas.height = h;
      // Sources sit LOW (real rig: fixtures on stands), beams fan UPWARD.
      this.dims = { W: w, H: h, cx: w / 2, cy: h * CAL.geometry.sourceYFrac,
                    scale: Math.min(w, h) * CAL.geometry.scaleFrac };
      this.ctx.clearRect(0, 0, w, h);
    }

    _sample(now) {
      const buf = this.buffer;
      if (buf.length === 0) return null;
      if (buf.length === 1) return { prev: buf[0].decoded, next: buf[0].decoded, frac: 1 };
      const rt = now - CAL.timing.renderBehindMs;
      let i = buf.length - 2;
      for (let j = 0; j < buf.length - 1; j++) { if (rt < buf[j + 1].t) { i = j; break; } }
      const a = buf[i], b = buf[i + 1];
      let frac = (rt - a.t) / (b.t - a.t);
      if (!isFinite(frac)) frac = 1;
      frac = Math.max(0, Math.min(1, frac));
      return { prev: a.decoded, next: b.decoded, frac };
    }

    _loop() {
      requestAnimationFrame(() => this._loop());
      const now = performance.now();
      let dt = (now - this._lastNow) / 1000; this._lastNow = now;
      if (dt > 0.05) dt = 0.05; if (dt < 0) dt = 0;
      this.clock += dt;

      if (!this.dims) { this._resize(); if (!this.dims) return; }
      const ctx = this.ctx, dims = this.dims;
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "rgba(0,0,0," + CAL.timing.trailFade + ")";
      ctx.fillRect(0, 0, dims.W, dims.H);
      ctx.globalCompositeOperation = "lighter";
      ctx.lineCap = "round";

      const s = this._sample(now);
      if (!s) return;
      let drew = false;
      this._frameAmbient = null;
      this._frameMotionStates = [];
      const total = s.next.length;
      for (let i = 0; i < total; i++) {
        try {
          const prevFix = s.prev[i] || s.next[i];
          const layers = this._layers(prevFix, s.next[i], s.frac);
          for (const st of layers) drew = this._drawFan(ctx, st, i, total, dims) || drew;
        } catch (e) { /* never kill the rAF loop */ }
      }
      this._lastMotionStates = this._frameMotionStates.slice();
      if (!drew) {
        ctx.globalCompositeOperation = "source-over";
        ctx.clearRect(0, 0, dims.W, dims.H);
      } else if (this._frameAmbient) {
        const a = this._frameAmbient;
        const alpha = CAL.beam.ambientStrength ?? 0.085;
        ctx.globalCompositeOperation = "source-over";
        const grad = ctx.createRadialGradient(dims.cx, dims.cy, dims.scale * 0.2, dims.cx, dims.cy, dims.scale * 1.4);
        grad.addColorStop(0, "rgba(" + a[0] + "," + a[1] + "," + a[2] + "," + alpha + ")");
        grad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, dims.W, dims.H);
      }
    }

    // ---- interpolation layers (primary + optional second pattern) ----------
    _layers(p, n, f) {
      const out = [this._interp(this._primary(p), this._primary(n), f)];
      if (n.second_pattern) {
        const ps = p.second_pattern ? this._second(p.second_pattern, p) : null;
        const ns = this._second(n.second_pattern, n);
        out.push(this._interp(ps || ns, ns, f));
      }
      return out;
    }
    _primary(fx) {
      const sel = fx.pattern.selection || {};
      return {
        name: fx.name,
        universe: fx.universe,
        power: fx.power, dimmer: fx.dimmer, size: fx.pattern.size,
        position: fx.position, color: fx.color, strobe: fx.strobe,
        control: fx.control || { sound_gated: false },
        gradient: fx.gradient, rotation: fx.rotation, movement: fx.movement,
        zoom: fx.zoom, scan: fx.scan, waves: fx.waves,
        patternGroup: fx.pattern.group, patternIndex: sel.index || 0,
        // CALIBRATED: CH3>=128 dynamic groups self-animate and IGNORE CH5-19.
        dynamic: fx.pattern.kind === "dynamic",
        captureLookup: fx.__capture_lookup || null,
        provenanceLabel: fx.__provenance_label || "MEASURED_FIXTURE_MODEL",
        modelStatus: fx.__model_status || "unknown",
        modelConfidence: fx.__model_confidence || "unknown",
        layerKind: "primary",
      };
    }
    _second(sp, fx) {
      const sel = sp.selection || {};
      return {
        name: fx.name,
        universe: fx.universe,
        power: fx.power, dimmer: fx.dimmer, size: sp.size, position: sp.position,
        color: sp.color, strobe: sp.strobe, gradient: sp.gradient,
        control: fx.control || { sound_gated: false },
        rotation: sp.rotation, movement: sp.movement, zoom: sp.zoom, scan: sp.scan,
        waves: sp.waves,
        patternGroup: sp.group, patternIndex: sel.index || 0,
        dynamic: false,            // second pattern (CH20-36) is static-only
        captureLookup: fx.__capture_lookup || null,
        provenanceLabel: fx.__provenance_label || "MEASURED_FIXTURE_MODEL",
        modelStatus: fx.__model_status || "unknown",
        modelConfidence: fx.__model_confidence || "unknown",
        layerKind: "second_pattern",
      };
    }
    _interp(p, n, f) {
      const power = p.power || n.power;
      const dimmer = lerp(p.dimmer, n.dimmer, f);
      const position = n.position || p.position || { x: 0, y: 0, blanked: false };
      const strobe = p.strobe || n.strobe || { on: false, speed: 0 };
      return {
        // dynamic ignores CH6/7, so its position.blanked must not hide it
        visible: power && dimmer > 0.002 && (p.dynamic || !position.blanked),
        name: n.name || p.name || "fixture",
        universe: n.universe || p.universe || 0,
        power,
        dimmer,
        position,
        posX: lerp((p.position || {}).x || 0, (n.position || {}).x || 0, f),
        posY: lerp((p.position || {}).y || 0, (n.position || {}).y || 0, f),
        size: lerp(p.size, n.size, f),
        color: p.color || n.color || { rgb: [255, 255, 255], mode: "solid", speed: "off" },
        strobeOn: !!strobe.on, strobeSpeed: Number(strobe.speed) || 0,
        gradient: p.gradient || n.gradient || 0,
        rotation: p.rotation || n.rotation || { z: { mode: "off" }, x: { mode: "off" }, y: { mode: "off" } },
        movement: p.movement || n.movement || { h: { mode: "off", val: 0 }, v: { mode: "off", val: 0 } },
        zoom: p.zoom || n.zoom || { mode: "off", val: 0 },
        scan: p.scan || n.scan || { mode: "line", speed: 0 },
        waves: p.waves || n.waves || { axis: "off", speed: 0 },
        patternGroup: p.patternGroup, patternIndex: p.patternIndex, dynamic: p.dynamic,
        control: n.control || p.control || { sound_gated: false },
        captureLookup: n.captureLookup || p.captureLookup || null,
        provenanceLabel: n.provenanceLabel || p.provenanceLabel || "MEASURED_FIXTURE_MODEL",
        modelStatus: n.modelStatus || p.modelStatus || "unknown",
        modelConfidence: n.modelConfidence || p.modelConfidence || "unknown",
        layerKind: n.layerKind || p.layerKind || "primary",
      };
    }

    _clamp(v, lo, hi, dflt) {
      const n = Number(v);
      if (!Number.isFinite(n)) return dflt;
      return Math.max(lo, Math.min(hi, n));
    }

    _directionSigns(direction) {
      const s = String(direction || "").toLowerCase();
      let h = 0, v = 0, r = 0, z = 0;
      if (s.includes("right_to_left") || s.includes("leftward")) h = -1;
      else if (s.includes("left_to_right") || s.includes("rightward")) h = 1;
      if (s.includes("up_to_down") || s.includes("downward")) v = -1;
      else if (s.includes("down_to_up") || s.includes("upward")) v = 1;
      if (s.includes("clockwise")) r = 1;
      else if (s.includes("counterclockwise")) r = -1;
      if (s.includes("growing")) z = 1;
      else if (s.includes("shrinking")) z = -1;
      return { h, v };
    }

    _withTier(validationBacked, measuredApplied) {
      if (!measuredApplied) return "DECODER_FALLBACK";
      if (validationBacked) return "EXACT_CAPTURE_RENDER_AUTHORITY";
      return "MEASURED_PARAM";
    }

    _isUsableEvidence(cl) {
      const q = cl && cl.quality ? cl.quality : null;
      return !!(q && q.usable_evidence);
    }

    _fixtureBoxLabel(idx, total) {
      if (total <= 1) return "image_left";
      return idx === 0 ? "image_left" : "image_right";
    }

    _fixtureGeometryOrigin(geo, idx, total, dims) {
      if (!geo || !dims) return null;
      const boxes = Array.isArray(geo.boxes) ? geo.boxes : [];
      const label = this._fixtureBoxLabel(idx, total);
      let box = boxes.find((b) => b && b.label === label);
      if (!box && boxes.length >= 2 && total > 1) {
        box = boxes[Math.min(idx, boxes.length - 1)];
      }
      if (!box || !Array.isArray(box.bbox) || box.bbox.length !== 4) return null;
      const cb = Array.isArray(geo.combined_bbox) && geo.combined_bbox.length === 4
        ? geo.combined_bbox : null;
      if (!cb) return null;
      const bcx = (box.bbox[0] + box.bbox[2]) / 2;
      const bcy = (box.bbox[1] + box.bbox[3]) / 2;
      const ccx = (cb[0] + cb[2]) / 2;
      const ccy = (cb[1] + cb[3]) / 2;
      const cbW = Math.max(1, cb[2] - cb[0]);
      const cbH = Math.max(1, cb[3] - cb[1]);
      const relX = (bcx - ccx) / cbW;
      const relY = (bcy - ccy) / cbH;
      const span = dims.scale * 0.95;
      const apW = Number(geo.aperture_box_width_px);
      const apGap = Number.isFinite(apW) && apW > 0
        ? dims.scale * (apW / cbW) * 0.12
        : dims.scale * CAL.geometry.apGapFrac;
      return {
        ox0: dims.cx + relX * span,
        oy: dims.cy + relY * span * 0.35,
        apGap: Math.max(dims.scale * 0.02, apGap),
      };
    }

    _positionFromCaptureGeometry(idx, total) {
      const geo = this._captureGeometry;
      if (!geo) return false;
      const probe = { cx: 450, cy: 400, scale: 350 };
      return !!this._fixtureGeometryOrigin(geo, idx, total, probe);
    }

    _extractMeasuredLayout(st) {
      const cl = st.captureLookup;
      if (!cl || !cl.hit || !cl.vector_match || st.layerKind !== "primary" || !this._isUsableEvidence(cl)) {
        return { applied: false, reason: "no_exact_vector_capture" };
      }
      const m = cl.metrics || {};
      const angleDeg = this._clamp(m.angle_range_deg, 1, 120, null);
      const derivedCount = Number.isFinite(Number(m.density_beam_count_derived))
        ? Number(m.density_beam_count_derived) : null;
      const densityEvidence = String(m.density_evidence || "inferred");
      if (angleDeg === null && derivedCount === null) {
        return { applied: false, reason: "missing_geometry_metrics" };
      }
      return {
        applied: true,
        spreadAngRad: angleDeg !== null ? (angleDeg * Math.PI / 180) : null,
        count: derivedCount,
        densityEvidence,
      };
    }

    _extractMeasuredColor(st) {
      const cl = st.captureLookup;
      if (!cl || !cl.hit || !cl.vector_match || st.layerKind !== "primary" || !this._isUsableEvidence(cl)) {
        return { applied: false, reason: "no_exact_vector_capture" };
      }
      const metrics = cl.metrics || {};
      const names = Array.isArray(metrics.dominant_colors) ? metrics.dominant_colors : [];
      const mapped = [];
      const unknown = [];
      for (const rawName of names) {
        const key = String(rawName || "").toLowerCase().trim();
        if (!key) continue;
        if (Object.prototype.hasOwnProperty.call(COLOR_PALETTE, key)) mapped.push(COLOR_PALETTE[key].slice());
        else unknown.push(key);
      }
      if (!mapped.length || unknown.length) {
        return {
          applied: false,
          reason: unknown.length ? "unknown_dominant_color_name" : "missing_dominant_colors",
          unknown,
        };
      }
      // 1 color -> solid; 2 -> per-beam alternation; >=3 -> per-beam cycle
      // through the measured palette (a measured rainbow spread). All colours
      // come from dominant_colors only; none are invented.
      return { applied: true, colors: mapped };
    }

    _extractMeasuredMotion(st) {
      const cl = st.captureLookup;
      if (!cl || !cl.hit || st.layerKind !== "primary") {
        return { active: false, source: "FALLBACK_MOTIONSTATE" };
      }
      const m = cl.metrics || {};
      const periodicMotion = !!m.periodic_motion;
      const loopConfidence = Number.isFinite(Number(m.loop_confidence)) ? Number(m.loop_confidence) : null;
      const directionConfidence = Number.isFinite(Number(m.motion_direction_confidence))
        ? Number(m.motion_direction_confidence) : null;
      const dir = this._directionSigns(m.motion_direction);
      const directionLabel = String(m.motion_direction || "");
      const signedDirection = directionConfidence !== null
        && directionConfidence >= 0.6
        && (dir.h !== 0 || dir.v !== 0);
      const loopDuration = this._clamp(m.loop_duration_estimate, 0.001, 9999, null);
      const loopHz = (periodicMotion && loopConfidence !== null && loopConfidence >= 0.5 && loopDuration)
        ? 1 / loopDuration : null;
      const strobeHz = this._clamp(m.strobe_frequency_hz, 0.0, 60.0, null);
      const strobeDuty = this._clamp(m.duty_cycle, 0.05, 0.95, null);
      const xExtent = this._clamp(m.x_range_norm_aperture ?? m.x_range_norm_roi, 0.05, 1.2, null);
      const yExtent = this._clamp(m.y_range_norm_aperture ?? m.y_range_norm_roi, 0.05, 1.2, null);
      const motionType = String(m.motion_type || "unknown");
      const translational = motionType === "horizontal_sweep" || motionType === "vertical_sweep";
      const nonTranslational = new Set(["static", "smooth_rotation", "wave_deformation", "pulse_zoom", "color_chase", "strobe_gate"]);
      const knownMotionType = translational || nonTranslational.has(motionType);
      return {
        active: true,
        source: "MEASURED_MOTION_ANALYSIS",
        motionType,
        knownMotionType,
        translational,
        periodicMotion,
        loopConfidence,
        loopHz,
        strobeHz,
        strobeDuty,
        xExtent,
        yExtent,
        direction: directionLabel,
        directionConfidence,
        signedDirection,
        hSign: signedDirection ? dir.h : 0,
        vSign: signedDirection ? dir.v : 0,
      };
    }

    _moveOffset(c, axis, measured) {
      if (!c || c.mode === "off") return { mode: "off", offset: 0, source: "none" };
      const val = Number(c.val);
      if (!Number.isFinite(val)) return { mode: "off", offset: 0, source: "none" };
      if (c.mode === "position") {
        return {
          mode: "position",
          offset: (val / 127 - 0.5) * 2,
          source: "channel_position",
        };
      }
      // speed mode. The KIND of motion comes from the capture motion_type
      // (plan 3.4), applied PER AXIS — never from "CH15/CH16 > 127" alone:
      //   horizontal_sweep -> measured translation on H only
      //   vertical_sweep   -> measured translation on V only
      //   other known types (static/rotation/wave/zoom/color_chase/strobe_gate)
      //                    -> NO measured translational offset on either axis
      //   unknown motion_type -> decoder/CAL sine fallback (NOT zeroed) + warning
      const fallbackHz = this._sweepHz(val);
      const decoderFallback = () => ({
        mode: "speed",
        offset: this._periodicSweepOffset(fallbackHz, 1, 1),
        source: "FALLBACK_MOTIONSTATE",
      });
      if (!measured.active) return decoderFallback();
      const axisMeasured = (axis === "h" && measured.motionType === "horizontal_sweep")
        || (axis === "v" && measured.motionType === "vertical_sweep");
      if (axisMeasured) {
        const hz = measured.loopHz ? measured.loopHz : fallbackHz;
        const signRaw = axis === "h" ? measured.hSign : measured.vSign;
        const sign = measured.signedDirection && signRaw ? signRaw : 1;
        const extent = axis === "h" ? measured.xExtent : measured.yExtent;
        const amp = extent ? extent : 1.0;
        return {
          mode: "speed",
          offset: this._periodicSweepOffset(hz, sign, amp),
          source: measured.source,
        };
      }
      if (measured.knownMotionType) {
        // Known non-translational type, or translation on the OTHER axis:
        // this axis gets no measured translational offset.
        return { mode: "speed", offset: 0, source: measured.source };
      }
      // Unknown motion_type: fall back to the decoder/CAL sine for this axis.
      return decoderFallback();
    }

    _buildMotionState(st, idx, total) {
      const measured = this._extractMeasuredMotion(st);
      const cl = st.captureLookup || null;
      const validationBacked = !!(cl && cl.validation_backed);
      const colorMeasured = this._extractMeasuredColor(st);
      const colorTier = this._withTier(validationBacked, colorMeasured.applied);
      const motionMeasuredApplied = measured.active && measured.knownMotionType;
      const motionTier = this._withTier(validationBacked, motionMeasuredApplied);
      const power = !!st.power;
      const dimmer = Number(st.dimmer) || 0;
      const positionBlanked = !!(st.position && st.position.blanked);
      const soundGated = !!(st.control && st.control.sound_gated);
      const soundOverride = !!this.debug.soundOverride;
      const dynamicBlankingBypassed = !!(st.dynamic && positionBlanked);
      let killReason = null;
      if (!power) killReason = "power_off";
      else if (dimmer <= 0.002) killReason = "dimmer_zero";
      else if (positionBlanked && !st.dynamic) killReason = "position_blanked";
      else if (soundGated && !soundOverride) killReason = "sound_gated";
      const visibleBeforeStrobe = killReason === null;

      const activeStrobe = !!st.strobeOn;
      const fallbackStrobeHz = CAL.rates.strobeHz * Math.max(0, (st.strobeSpeed || 0) / 255);
      const strobeHz = activeStrobe
        ? (measured.active && measured.strobeHz ? measured.strobeHz : fallbackStrobeHz)
        : 0;
      const strobeDuty = activeStrobe
        ? (measured.active && measured.strobeDuty ? measured.strobeDuty : 0.5)
        : 1.0;
      const strobePhase = strobeHz > 0 ? (((this.clock * strobeHz) % 1) + 1) % 1 : 0;
      const strobeGateOpen = !activeStrobe || strobePhase < strobeDuty;
      const visibleAfterStrobe = visibleBeforeStrobe && strobeGateOpen;

      const drawMode = (st.scan && st.scan.mode === "line-bright") ? "bright_line"
        : (st.scan && st.scan.mode === "dot") ? "dot"
          : "beam_line";
      const hMove = this._moveOffset(st.movement && st.movement.h, "h", measured);
      const vMove = this._moveOffset(st.movement && st.movement.v, "v", measured);

      const warnings = [];
      const quality = cl && cl.quality ? cl.quality : null;
      if (st.layerKind === "second_pattern") warnings.push("second_pattern_decoder_driven_with_warning");
      if (st.waves && st.waves.axis !== "off") {
        const qMode = this._ch19QuarantineMode();
        if (qMode === "off") warnings.push("CH19_wave_quarantined_off");
        else if (qMode === "legacy") warnings.push("CH19_wave_quarantined_legacy_spaghetti");
        else if (qMode === "fixed") warnings.push("CH19_wave_quarantine_fixed_experimental");
      }
      if (this._fanMotionChannelsActive(st)) {
        const fmMode = this._fanMotionQuarantineMode();
        if (fmMode === "off") warnings.push("fan_motion_quarantined_rigid_off");
        else if (fmMode === "legacy_rigid") warnings.push("fan_motion_quarantined_legacy_rigid");
        else if (fmMode === "scan_phase") warnings.push("fan_motion_quarantine_scan_phase_experimental");
        else if (fmMode === "sweep_triangle") warnings.push("fan_motion_quarantine_sweep_triangle_experimental");
      }
      const usedDecoderSine = (hMove.mode === "speed" && hMove.source === "FALLBACK_MOTIONSTATE")
        || (vMove.mode === "speed" && vMove.source === "FALLBACK_MOTIONSTATE");
      if (usedDecoderSine) {
        warnings.push("CH15_CH16_sine_waveform_approximate_unverified");
      }
      if (st.modelStatus !== "measured") warnings.push("model_not_measured_status");
      if (st.modelConfidence && st.modelConfidence !== "measured_exact" && st.modelConfidence !== "measured_estimated") {
        warnings.push("model_confidence_non_measured");
      }
      if (cl && !cl.hit && cl.fallback_reason) warnings.push("capture_lookup_" + cl.fallback_reason);
      if (quality && quality.usable_evidence === false) warnings.push("capture_quality_usable_evidence_false");
      if (quality && quality.geometry_clipped_low === true) warnings.push("capture_quality_geometry_clipped_low");
      if (quality && quality.recapture_pending_manifest === true) warnings.push("capture_quality_recapture_pending");
      if ((st.provenanceLabel || "") === "MANUAL_DECODER") warnings.push("manual_decoder_fallback_active");
      if (measured.active && measured.directionConfidence !== null && measured.directionConfidence < 0.6) {
        warnings.push("measured_motion_direction_low_confidence");
      }
      if (measured.active && !measured.knownMotionType) warnings.push("measured_motion_type_unknown_fallback");
      if (!colorMeasured.applied && colorMeasured.reason === "unknown_dominant_color_name") {
        warnings.push("measured_color_unknown_name_fallback");
      }
      if (!measured.active) warnings.push("fallback_motionstate_active");

      const shapeRef = cl && cl.shape_ref ? String(cl.shape_ref) : null;
      const shapeAuthority = !!(cl && cl.shape_authority && shapeRef);
      const visibleGeometrySource = "DECODER_FALLBACK_DRAWFAN";
      const projectionSource = shapeAuthority ? "NOT_WIRED_PR_G3" : "DECODER_FALLBACK_DRAWFAN";
      if (shapeAuthority) {
        warnings.push("shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3");
      }

      const layoutMeasured = this._extractMeasuredLayout(st);
      const positionMeasured = this._positionFromCaptureGeometry(idx, total);
      if (layoutMeasured.applied && layoutMeasured.densityEvidence === "inferred") {
        warnings.push("density_evidence_inferred");
      }

      const paramTiers = {
        color: colorTier,
        motion: motionTier,
        spread: this._withTier(validationBacked, layoutMeasured.applied && layoutMeasured.spreadAngRad !== null),
        count: layoutMeasured.applied && layoutMeasured.count !== null
          ? this._withTier(validationBacked, true) : "DECODER_FALLBACK",
        position: this._withTier(validationBacked, positionMeasured),
        strobe: this._withTier(validationBacked, measured.active && measured.strobeHz !== null),
        dots: "DECODER_FALLBACK",
      };
      const headlineTier = Object.keys(paramTiers).reduce((best, key) => {
        return AUTHORITY_TIER[paramTiers[key]] < AUTHORITY_TIER[best] ? paramTiers[key] : best;
      }, "EXACT_CAPTURE_RENDER_AUTHORITY");

      return {
        epochMs: performance.now(),
        fixture: {
          index: idx,
          total,
          name: st.name || "fixture",
          universe: st.universe || 0,
          mirror: idx % 2 === 1,
          modelStatus: st.modelStatus || "unknown",
          modelConfidence: st.modelConfidence || "unknown",
          captureProvenance: st.provenanceLabel || "MEASURED_FIXTURE_MODEL",
          motionProvenance: measured.active ? "MEASURED_MOTION_ANALYSIS" : "FALLBACK_MOTIONSTATE",
          headlineTier,
          parameterTiers: paramTiers,
          validationBacked,
          layerKind: st.layerKind || "primary",
        },
        visibility: {
          power,
          dimmer,
          positionBlanked,
          soundGated,
          soundOverride,
          dynamicBlankingBypassed,
          visibleBeforeStrobe,
          visibleAfterStrobe,
          killReason,
        },
        aim: {
          hStatic: Number(st.posX) || 0,
          vStatic: Number(st.posY) || 0,
          hMoveMode: hMove.mode,
          vMoveMode: vMove.mode,
          hMoveOffset: hMove.offset,
          vMoveOffset: vMove.offset,
          hFinal: (Number(st.posX) || 0) + hMove.offset,
          vFinal: (Number(st.posY) || 0) + vMove.offset,
        },
        scan: {
          mode: (st.scan && st.scan.mode) || "line",
          drawMode,
        },
        strobe: {
          active: activeStrobe,
          gateOpen: strobeGateOpen,
          phase: strobePhase,
          duty: strobeDuty,
          frequencyHz: strobeHz,
          source: measured.active && measured.strobeHz ? measured.source : "FALLBACK_MOTIONSTATE",
          waveform: "square",
        },
        measured: measured.active ? measured : null,
        colorMeasured: colorMeasured.applied ? colorMeasured : null,
        shape: {
          shape_ref: shapeRef,
          topology_class: cl && cl.topology_class ? cl.topology_class : null,
          shape_point_count: cl && cl.shape_point_count ? cl.shape_point_count : 0,
          shape_evidence: cl && cl.shape_evidence ? cl.shape_evidence : null,
          shape_fallback_reason: cl && cl.shape_fallback_reason ? cl.shape_fallback_reason : null,
          shape_quality_flags: cl && Array.isArray(cl.shape_quality_flags) ? cl.shape_quality_flags : [],
          shape_source_capture_path: cl && cl.shape_source_capture_path ? cl.shape_source_capture_path : null,
          internal_shape_authority: shapeAuthority,
          visible_geometry_source: visibleGeometrySource,
          projection_source: projectionSource,
        },
        warnings,
      };
    }

    // ---- rate helpers ------------------------------------------------------
    _spec(v) { return v / 128; }
    _sweepHz(v) { return CAL.rates.sweepMinHz + this._spec(v) * (CAL.rates.sweepMaxHz - CAL.rates.sweepMinHz); }
    _spin(r) {
      if (!r || r.mode === "off") return 0;
      if (r.mode === "angle") return (r.val / 127) * CAL.rates.spinAngleMax;
      return this.clock * TAU * CAL.rates.spinRps * this._spec(r.val);
    }
    _sweep(c) {
      if (!c || c.mode === "off") return 0;
      if (c.mode === "position") return (c.val / 127 - 0.5) * 2;          // -1..1
      return Math.sin(this.clock * TAU * this._sweepHz(c.val));            // -1..1
    }
    // rotation channel -> angle: angle mode = fixed, speed mode = integrate.
    _rotA(r, maxAng, rps) {
      if (!r || r.mode === "off") return 0;
      if (r.mode === "angle") return (r.val / 127) * maxAng;
      return this.clock * TAU * rps * this._spec(r.val);
    }
    // rotate a 3D unit dir by roll(z) -> pitch(x) -> yaw(y)
    _rot3(d, roll, pitch, yaw) {
      let cz = Math.cos(roll), sz = Math.sin(roll);
      let x = d.x * cz - d.y * sz, y = d.x * sz + d.y * cz, z = d.z;
      const cx = Math.cos(pitch), sx = Math.sin(pitch);
      const y2 = y * cx - z * sx; z = y * sx + z * cx; y = y2;
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const x2 = x * cy + z * sy; z = -x * sy + z * cy; x = x2;
      return { x: x, y: y, z: z };
    }
    // perspective-project a 3D point (z toward viewer +) to screen px, or null
    _proj(P, dims) {
      const CAM = 3.0, w = CAM - P.z;
      if (w <= 0.25) return null;            // behind camera
      const f = CAM / w;
      return [dims.cx + P.x * f * dims.scale, dims.cy - P.y * f * dims.scale];
    }
    _hazeWedgePts(ctx, p0, ends, rgb, dim) {
      const r = (rgb[0] * dim) | 0, g = (rgb[1] * dim) | 0, b = (rgb[2] * dim) | 0;
      ctx.beginPath(); ctx.moveTo(p0[0], p0[1]);
      let rad = 0;
      for (const e of ends) { ctx.lineTo(e[0], e[1]); rad = Math.max(rad, Math.hypot(e[0] - p0[0], e[1] - p0[1])); }
      ctx.closePath();
      const grad = ctx.createRadialGradient(p0[0], p0[1], 0, p0[0], p0[1], rad || 1);
      grad.addColorStop(0, "rgba(" + r + "," + g + "," + b + ",0.15)");
      grad.addColorStop(0.4, "rgba(" + r + "," + g + "," + b + ",0.04)");
      grad.addColorStop(1, "rgba(" + r + "," + g + "," + b + ",0)");
      ctx.fillStyle = grad; ctx.fill();
    }
    _beamColor(st, i) {
      const measured = this._extractMeasuredColor(st);
      if (measured.applied) {
        if (measured.colors.length === 1) return measured.colors[0];
        return measured.colors[i % measured.colors.length];
      }
      const c = st.color;
      if (st.dynamic) {
        // CH3>=128 macros can still obey fixed CH8 colours. Fall back to the
        // calibrated self-colour cycle only for animated/no-RGB colour modes.
        if (c.rgb) return c.rgb;
        const h = ((Math.floor(this.clock * CAL.dynamic.colorRate)
                    + CAL.dynamic.colorBase
                    + i * CAL.dynamic.colorSpread) % 256 + 256) % 256;
        return HUE_LUT[h];
      }
      if (c.rgb) return c.rgb;
      const dir = c.speed === "reverse" ? -1 : (c.speed === "off" ? 0 : 1);
      // CALIBRATED 2026-06-05: GRADIENT (CH8 240-255) = the WHOLE pattern is one
      // colour cycling over time (spread 0 -> all beams same hue). FLOWING/
      // colourful (CH8 44-239) = per-beam rainbow spread across the fan.
      const spread = c.mode === "gradient" ? 0
                     : CAL.color.gradientSpreadBase
                       + Math.round((st.gradient || 0) / 255 * CAL.color.gradientSpreadRange);
      const h = ((Math.floor(this.clock * CAL.rates.colorHue * dir) + i * spread) % 256 + 256) % 256;
      return HUE_LUT[h];
    }

    // CH3 group (raw) -> beam-fan density + spread family. CALIBRATED 2026-06-05
    // by eye on the real lasers: folder1-2 (0-31) sparse 2-beam X, folder3-4
    // (32-63) dense wide fans, animation (64+) mid. CH4 index adds variation so
    // different selections differ. Approximate (exact shapes aren't in the DMX).
    _patternShape(group, index) {
      const g = (group || 0) & 0x7f;
      const ps = CAL.patternShape;
      let f;
      if (g <= 15)      { f = ps.folder1; }     // folder 1
      else if (g <= 31) { f = ps.folder2; }     // folder 2 (sparse X)
      else if (g <= 47) { f = ps.folder3; }     // folder 3 (dense)
      else if (g <= 63) { f = ps.folder4; }     // folder 4 (densest)
      else              { f = ps.animation; }   // animation
      return { n: f.n + ((index || 0) % 4), spread: f.spread };
    }

    // ---- the beam fan ------------------------------------------------------
    _drawFan(ctx, st, idx, total, dims) {
      const motion = this._buildMotionState(st, idx, total);
      this._frameMotionStates.push(motion);
      if (!motion.visibility.visibleAfterStrobe) return false;
      const mirror = motion.fixture.mirror;

      const layout = this._extractMeasuredLayout(st);
      const geo = this._captureGeometry;
      const measuredOrigin = geo ? this._fixtureGeometryOrigin(geo, idx, total, dims) : null;

      let ox0, oy, apGap;
      if (measuredOrigin) {
        ox0 = measuredOrigin.ox0;
        oy = measuredOrigin.oy;
        apGap = measuredOrigin.apGap;
      } else {
        const fixGap = dims.scale * CAL.geometry.fixGapFrac;
        apGap = dims.scale * CAL.geometry.apGapFrac;
        ox0 = dims.cx + (total > 1 ? (idx / (total - 1) * 2 - 1) * fixGap : 0);
        oy = dims.cy;
      }

      let spreadAng, count;
      if (st.dynamic) {
        spreadAng = Math.min(CAL.geometry.spreadAngMax, CAL.geometry.spreadAngGain * CAL.dynamic.spread);
        count = CAL.dynamic.count;
      } else {
        const zf = st.zoom.mode === "size" ? CAL.zoom.min + (st.zoom.val / 127) * CAL.zoom.range : 1;
        const sizeScale = (0.7 + (1 - st.size / 255) * 0.9) * zf;
        const countScale = (0.32 + (1 - st.size / 255) * 0.45);
        if (layout.applied && layout.spreadAngRad !== null) {
          spreadAng = Math.min(CAL.geometry.spreadAngMax, layout.spreadAngRad * sizeScale);
        } else {
          const pat = this._patternShape(st.patternGroup, st.patternIndex);
          spreadAng = Math.min(CAL.geometry.spreadAngMax, CAL.geometry.spreadAngGain * pat.spread * sizeScale);
        }
        if (layout.applied && layout.count !== null) {
          count = Math.max(2, Math.round(layout.count * countScale));
        } else {
          const pat = this._patternShape(st.patternGroup, st.patternIndex);
          count = Math.max(2, Math.round(pat.n * countScale));
        }
      }
      const drawMode = motion.scan.drawMode;
      const scanN = drawMode === "bright_line" ? 1.2 : (drawMode === "dot" ? 0.55 : 0.9);
      const dim = st.dimmer * (drawMode === "bright_line" ? 1.0 : (drawMode === "dot" ? 0.6 : 0.85));
      count = Math.max(2, Math.round(count * scanN));
      const wscale = Math.max(0.5, Math.min(2.6, 12 / count));
      const waveRaw = this._ch19WaveActive(st) ? st.waves : null;
      const waveMetrics = (st.captureLookup && st.captureLookup.metrics) ? st.captureLookup.metrics : null;
      const colMid = this._beamColor(st, count >> 1);

      // ---- 2D fan geometry from the FIXED origin ----
      const UP = -Math.PI / 2;
      const L = Math.hypot(dims.W, dims.H);
      // both fans point UP & spread symmetrically; a SLIGHT inward lean makes the
      // two (separated) sources cross into the X. Big leans skew it — keep small.
      const inward = (idx === 0 ? 1 : -1) * CAL.geometry.inwardLean;  // left leans slightly right, right slightly left
      // rotation: Z spins the fan (angle/speed); X/Y squash it (NO 3D perspective):
      let spinZ = this._spin(st.rotation.z) * (mirror ? -1 : 1);
      const pitch = this._rotA(st.rotation.x, 1.0, CAL.rates.rotPitchYawRps);
      const yaw = this._rotA(st.rotation.y, 1.0, CAL.rates.rotPitchYawRps);
      const sqMax = CAL.geometry.squashMax;
      const sqY = 1 - Math.min(sqMax, Math.abs(Math.sin(pitch)) * sqMax);
      const sqX = 1 - Math.min(sqMax, Math.abs(Math.sin(yaw)) * sqMax);
      // position/movement RE-AIM: pivot the fan from the fixed origin toward a
      // shifted landing — origin stays put. +H = screen-right, +V = screen-up.
      let aimX = motion.aim.hFinal;
      let aimY = motion.aim.vFinal;
      if (!st.dynamic && (Math.abs(aimX) > CAL.geometry.aimXBlank || Math.abs(aimY) > CAL.geometry.aimYBlank)) return false;
      if (st.dynamic) {                              // self-animation, ignores CH5-19
        const m = mirror ? -1 : 1;
        spinZ = this.clock * CAL.dynamic.spinRate * m;
        aimX = Math.sin(this.clock * CAL.dynamic.aimXRate) * CAL.dynamic.aimXAmp * m;
        aimY = 0;
      }
      const shiftY = -aimY * dims.scale * CAL.geometry.vShiftGain;
      const fmMode = this._fanMotionQuarantineMode();
      const FM = (typeof VLNQuarantineFanMotion !== "undefined") ? VLNQuarantineFanMotion : null;

      let drew = false;
      for (let ap = 0; ap < 2; ap++) {
        const ox = ox0 + (ap === 0 ? -apGap : apGap);
        const p0 = [ox, oy];
        const ends = [];
        for (let i = 0; i < count; i++) {
          const fr = count > 1 ? i / (count - 1) : 0.5;
          let bAimX = aimX;
          let bAimY = aimY;
          let angDelta = 0;
          if (fmMode === "scan_phase" && FM && FM.beamAimDelta) {
            const d = FM.beamAimDelta(fr, i, count, st.scan, this.clock);
            bAimX += d.aimXDelta;
            bAimY += d.aimYDelta;
            angDelta = d.angDelta;
          }
          const ang = UP + inward + spinZ + bAimX * CAL.geometry.panGain
            + angDelta + (fr - 0.5) * spreadAng;
          const bShiftY = -bAimY * dims.scale * CAL.geometry.vShiftGain;
          const ex = ox + Math.cos(ang) * L * sqX;
          const ey = oy + Math.sin(ang) * L * sqY + bShiftY;
          const rgb = this._beamColor(st, i);
          const drawnEnd = this._drawCh19Beam(
            ctx, ox, oy, ex, ey, fr, waveRaw, rgb, dim, wscale, spreadAng, waveMetrics);
          if (drawMode === "dot") this._dotBurst(ctx, drawnEnd.ex, drawnEnd.ey, rgb, dim, wscale);
          ends.push([drawnEnd.ex, drawnEnd.ey]);
          drew = true;
        }
        if (ends.length > 1) this._hazeWedgePts(ctx, p0, ends, colMid, dim);
        this._sourceGlow(ctx, ox, oy, this._beamColor(st, 0), dim);
      }
      const amb = [(colMid[0] * dim) | 0, (colMid[1] * dim) | 0, (colMid[2] * dim) | 0];
      if (!this._frameAmbient) this._frameAmbient = amb;
      else {
        this._frameAmbient = [
          Math.max(this._frameAmbient[0], amb[0]),
          Math.max(this._frameAmbient[1], amb[1]),
          Math.max(this._frameAmbient[2], amb[2]),
        ];
      }
      return drew;
    }

    _hazeWedge(ctx, sx, sy, aim, spread, len, rgb, dim) {
      const r = (rgb[0] * dim) | 0, g = (rgb[1] * dim) | 0, b = (rgb[2] * dim) | 0;
      const steps = 16;
      ctx.beginPath(); ctx.moveTo(sx, sy);
      for (let i = 0; i <= steps; i++) {
        const a = aim + (i / steps - 0.5) * spread;
        ctx.lineTo(sx + Math.cos(a) * len, sy + Math.sin(a) * len);
      }
      ctx.closePath();
      const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, len);
      grad.addColorStop(0, "rgba(" + r + "," + g + "," + b + ",0.20)");
      grad.addColorStop(0.32, "rgba(" + r + "," + g + "," + b + ",0.06)");
      grad.addColorStop(1, "rgba(" + r + "," + g + "," + b + ",0)");
      ctx.fillStyle = grad; ctx.fill();
    }

    _beam(ctx, x0, y0, x1, y1, rgb, dim, wscale) {
      let pts;
      if (Array.isArray(x0)) {
        pts = x0; rgb = y0; dim = x1; wscale = y1;
      } else {
        pts = [[x0, y0], [x1, y1]];
      }
      wscale = wscale || 1;
      if (pts.length < 2) return;
      const first = pts[0], last = pts[pts.length - 1];
      const r = (rgb[0] * dim) | 0, g = (rgb[1] * dim) | 0, b = (rgb[2] * dim) | 0;
      const cs = r + "," + g + "," + b;
      const strokePts = () => {
        ctx.beginPath(); ctx.moveTo(first[0], first[1]);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
        ctx.stroke();
      };
      // haze halo (wide, faint) — beam visible "in the air", fading with distance
      let grad = ctx.createLinearGradient(first[0], first[1], last[0], last[1]);
      grad.addColorStop(0, "rgba(" + cs + ",0.22)");
      grad.addColorStop(0.65, "rgba(" + cs + ",0.07)");
      grad.addColorStop(1, "rgba(" + cs + ",0)");
      ctx.strokeStyle = grad; ctx.lineWidth = CAL.beam.halo * wscale;
      strokePts();
      // mid glow
      grad = ctx.createLinearGradient(first[0], first[1], last[0], last[1]);
      grad.addColorStop(0, "rgba(" + cs + ",0.5)");
      grad.addColorStop(0.7, "rgba(" + cs + ",0.12)");
      grad.addColorStop(1, "rgba(" + cs + ",0)");
      ctx.strokeStyle = grad; ctx.lineWidth = CAL.beam.mid * wscale;
      strokePts();
      // bright core (near-white at source). coreWhiteBoost desaturates the hue —
      // calibration.json beam.coreWhiteBoost lets it be dialled down without code.
      const wb_ = CAL.beam.coreWhiteBoost;
      const wr = Math.min(255, r + wb_), wg = Math.min(255, g + wb_), wb = Math.min(255, b + wb_);
      grad = ctx.createLinearGradient(first[0], first[1], last[0], last[1]);
      grad.addColorStop(0, "rgba(" + wr + "," + wg + "," + wb + ",1)");
      grad.addColorStop(0.55, "rgba(" + cs + ",0.6)");
      grad.addColorStop(1, "rgba(" + cs + ",0)");
      ctx.strokeStyle = grad; ctx.lineWidth = CAL.beam.core * wscale;
      strokePts();
      // tip accent gives endpoint presence without changing motion geometry.
      const tipR = (CAL.beam.tipGlow ?? 4.5) * wscale;
      const tip = ctx.createRadialGradient(last[0], last[1], 0, last[0], last[1], tipR);
      tip.addColorStop(0, "rgba(" + cs + ",0.35)");
      tip.addColorStop(1, "rgba(" + cs + ",0)");
      ctx.fillStyle = tip;
      ctx.beginPath(); ctx.arc(last[0], last[1], tipR, 0, TAU); ctx.fill();
    }

    _sourceGlow(ctx, x, y, rgb, dim) {
      const gb = CAL.beam.srcGlowBoost;
      const r = Math.min(255, ((rgb[0] * dim) | 0) + gb);
      const g = Math.min(255, ((rgb[1] * dim) | 0) + gb);
      const b = Math.min(255, ((rgb[2] * dim) | 0) + gb);
      const er = (rgb[0] * dim) | 0, eg = (rgb[1] * dim) | 0, eb = (rgb[2] * dim) | 0;
      const grad = ctx.createRadialGradient(x, y, 0, x, y, CAL.beam.srcGlow);
      grad.addColorStop(0, "rgba(" + r + "," + g + "," + b + ",0.9)");
      grad.addColorStop(1, "rgba(" + er + "," + eg + "," + eb + ",0)");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(x, y, CAL.beam.srcGlow, 0, TAU); ctx.fill();
      const ringR = CAL.beam.srcGlow * 1.2;
      const ring = ctx.createRadialGradient(x, y, CAL.beam.srcGlow * 0.7, x, y, ringR);
      ring.addColorStop(0, "rgba(" + er + "," + eg + "," + eb + ",0.18)");
      ring.addColorStop(1, "rgba(" + er + "," + eg + "," + eb + ",0)");
      ctx.fillStyle = ring;
      ctx.beginPath(); ctx.arc(x, y, ringR, 0, TAU); ctx.fill();
    }

    _dotBurst(ctx, x, y, rgb, dim, wscale) {
      const r = (rgb[0] * dim) | 0, g = (rgb[1] * dim) | 0, b = (rgb[2] * dim) | 0;
      const inner = Math.max(1, 1.1 * wscale);
      const outer = Math.max(inner + 1, 4 * wscale);
      const grad = ctx.createRadialGradient(x, y, inner * 0.1, x, y, outer);
      grad.addColorStop(0, "rgba(" + r + "," + g + "," + b + ",0.9)");
      grad.addColorStop(0.45, "rgba(" + r + "," + g + "," + b + ",0.35)");
      grad.addColorStop(1, "rgba(" + r + "," + g + "," + b + ",0)");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(x, y, outer, 0, TAU); ctx.fill();
    }
  }

  LaserRenderer.DEFAULTS = DEFAULTS;   // exposed for console inspection + parity tests
  window.LaserRenderer = LaserRenderer;
})();
