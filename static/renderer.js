// VirtualLaserNode — step 6 renderer (AERIAL BEAM view).
// Renders the volumetric laser BEAMS shooting into the haze (what a crowd sees
// in the air), NOT the galvo figure on a wall. Each fixture is a source that
// throws a fan of beams; DMX drives colour, brightness, aim (position), sweep
// (movement), spin (rotation), spread (size/zoom), and strobe. Consumes the SSE
// `decoded` feed; interpolates a fixed time behind latest for smooth motion.

(function () {
  "use strict";
  const TAU = Math.PI * 2;

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
            srcGlowBoost: 130 },
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
      const total = s.next.length;
      for (let i = 0; i < total; i++) {
        try {
          const prevFix = s.prev[i] || s.next[i];
          const layers = this._layers(prevFix, s.next[i], s.frac);
          for (const st of layers) drew = this._drawFan(ctx, st, i, total, dims) || drew;
        } catch (e) { /* never kill the rAF loop */ }
      }
      if (!drew) {
        ctx.globalCompositeOperation = "source-over";
        ctx.clearRect(0, 0, dims.W, dims.H);
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
        power: fx.power, dimmer: fx.dimmer, size: fx.pattern.size,
        position: fx.position, color: fx.color, strobe: fx.strobe,
        gradient: fx.gradient, rotation: fx.rotation, movement: fx.movement,
        zoom: fx.zoom, scan: fx.scan, waves: fx.waves,
        patternGroup: fx.pattern.group, patternIndex: sel.index || 0,
        // CALIBRATED: CH3>=128 dynamic groups self-animate and IGNORE CH5-19.
        dynamic: fx.pattern.kind === "dynamic",
      };
    }
    _second(sp, fx) {
      const sel = sp.selection || {};
      return {
        power: fx.power, dimmer: fx.dimmer, size: sp.size, position: sp.position,
        color: sp.color, strobe: sp.strobe, gradient: sp.gradient,
        rotation: sp.rotation, movement: sp.movement, zoom: sp.zoom, scan: sp.scan,
        waves: sp.waves,
        patternGroup: sp.group, patternIndex: sel.index || 0,
        dynamic: false,            // second pattern (CH20-36) is static-only
      };
    }
    _interp(p, n, f) {
      const power = p.power || n.power;
      const dimmer = lerp(p.dimmer, n.dimmer, f);
      return {
        // dynamic ignores CH6/7, so its position.blanked must not hide it
        visible: power && dimmer > 0.002 && (p.dynamic || !p.position.blanked),
        dimmer,
        posX: lerp(p.position.x, n.position.x, f),
        posY: lerp(p.position.y, n.position.y, f),
        size: lerp(p.size, n.size, f),
        color: p.color, strobeOn: p.strobe.on, strobeSpeed: p.strobe.speed,
        gradient: p.gradient, rotation: p.rotation, movement: p.movement, zoom: p.zoom,
        scan: p.scan, waves: p.waves,
        patternGroup: p.patternGroup, patternIndex: p.patternIndex, dynamic: p.dynamic,
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
    _strobeVisible(st) {
      if (!st.strobeOn) return true;
      return Math.sin(this.clock * TAU * CAL.rates.strobeHz * (st.strobeSpeed / 255)) > 0;
    }
    _beamColor(st, i) {
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
      if (!st.visible) return false;
      if (st.strobeOn && !this._strobeVisible(st)) return false;
      const mirror = idx % 2 === 1;

      // ---- FIXED apertures: 2 fixtures on a T-bar near top-centre, each a
      // dual-aperture box. Origins are BOLTED DOWN — only beam DIRECTIONS change.
      // Pure 2D screen-space fan (no perspective) so beams never spaghetti. ----
      const fixGap = dims.scale * CAL.geometry.fixGapFrac;   // half-gap between the 2 fixtures (clearly separated)
      const apGap = dims.scale * CAL.geometry.apGapFrac;     // gap between a fixture's 2 apertures (4 distinct points)
      const ox0 = dims.cx + (total > 1 ? (idx / (total - 1) * 2 - 1) * fixGap : 0);
      const oy = dims.cy;                           // fixed, near the top

      // ---- pattern density / size / scan / waves (calibrated, unchanged) ----
      let spread, count;
      if (st.dynamic) {
        spread = CAL.dynamic.spread; count = CAL.dynamic.count;  // self-contained; CH5 size + zoom ignored
      } else {
        const zf = st.zoom.mode === "size" ? CAL.zoom.min + (st.zoom.val / 127) * CAL.zoom.range : 1;
        const pat = this._patternShape(st.patternGroup, st.patternIndex);  // CH3/CH4 density
        spread = pat.spread * (0.7 + (1 - st.size / 255) * 0.9) * zf;
        // 4 apertures each draw the fan, so keep per-aperture count modest.
        count = Math.max(2, Math.round(pat.n * (0.32 + (1 - st.size / 255) * 0.45)));
      }
      const sm = (!st.dynamic && st.scan) ? st.scan.mode : "line";   // CH10 scan
      const scanN = sm === "line-bright" ? 1.2 : (sm === "dot" ? 0.55 : 0.9);
      const dim = st.dimmer * (sm === "line-bright" ? 1.0 : (sm === "dot" ? 0.6 : 0.85));
      count = Math.max(2, Math.round(count * scanN));
      const wscale = Math.max(0.5, Math.min(2.6, 12 / count));
      const wave = (!st.dynamic && st.waves && st.waves.axis !== "off") ? st.waves : null;
      const colMid = this._beamColor(st, count >> 1);

      // ---- 2D fan geometry from the FIXED origin ----
      const UP = -Math.PI / 2;                       // screen -y points up (beams fan UP)
      const spreadAng = Math.min(CAL.geometry.spreadAngMax, CAL.geometry.spreadAngGain * spread); // fan angular width (rad)
      const L = Math.hypot(dims.W, dims.H);          // beams run off-frame
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
      let aimX = st.posX + this._sweep(st.movement.h);
      let aimY = st.posY + this._sweep(st.movement.v);
      if (!st.dynamic && (Math.abs(aimX) > CAL.geometry.aimXBlank || Math.abs(aimY) > CAL.geometry.aimYBlank)) return false;
      if (st.dynamic) {                              // self-animation, ignores CH5-19
        const m = mirror ? -1 : 1;
        spinZ = this.clock * CAL.dynamic.spinRate * m;
        aimX = Math.sin(this.clock * CAL.dynamic.aimXRate) * CAL.dynamic.aimXAmp * m;
        aimY = 0;
      }
      const shiftY = -aimY * dims.scale * CAL.geometry.vShiftGain;        // vertical re-aim = screen shift
      const baseAng = UP + inward + spinZ + aimX * CAL.geometry.panGain;  // horizontal re-aim = pan

      let drew = false;
      for (let ap = 0; ap < 2; ap++) {               // two apertures per box
        const ox = ox0 + (ap === 0 ? -apGap : apGap);
        const p0 = [ox, oy];
        const ends = [];
        for (let i = 0; i < count; i++) {
          const fr = count > 1 ? i / (count - 1) : 0.5;
          const ang = baseAng + (fr - 0.5) * spreadAng;
          const ex = ox + Math.cos(ang) * L * sqX;
          const ey = oy + Math.sin(ang) * L * sqY + shiftY;
          const rgb = this._beamColor(st, i);
          if (wave) {
            const dx = ex - ox, dy = ey - oy, beamLen = Math.hypot(dx, dy);
            const spd = Math.max(0, Math.min(127, wave.speed || 0)) / 127;
            const amp = beamLen * (0.015 + spd * 0.065), rate = 0.5 + spd * 2.5;
            const pts = [p0];
            for (let j = 1; j < 10; j++) {
              const along = j / 10;
              const disp = amp * Math.sin(Math.PI * along) *
                           Math.sin(TAU * (2.5 * along - this.clock * rate));
              pts.push([ox + dx * along + (wave.axis === "x" ? disp : 0),
                        oy + dy * along + (wave.axis === "y" ? disp : 0)]);
            }
            pts.push([ex, ey]);
            this._beam(ctx, pts, rgb, dim, wscale);
          } else {
            this._beam(ctx, ox, oy, ex, ey, rgb, dim, wscale);
          }
          ends.push([ex, ey]);
          drew = true;
        }
        if (ends.length > 1) this._hazeWedgePts(ctx, p0, ends, colMid, dim);
        this._sourceGlow(ctx, ox, oy, this._beamColor(st, 0), dim);
      }
      this._frameAmbient = [(colMid[0] * dim) | 0, (colMid[1] * dim) | 0, (colMid[2] * dim) | 0];
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
    }
  }

  LaserRenderer.DEFAULTS = DEFAULTS;   // exposed for console inspection + parity tests
  window.LaserRenderer = LaserRenderer;
})();
