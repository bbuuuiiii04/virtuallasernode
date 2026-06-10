// VirtualLaserNode — channel inspector frontend.
// Consumes the /stream SSE feed and draws a 512-channel heatmap per universe
// plus the fixture patch. (Step 6 renderer will be added alongside this.)

const COLS = 32, ROWS = 16, CELL = 20;
const uniEls = {};   // universe -> {canvas, ctx, meta}
const fxEls = {};
function authorityColor(tier) {
  return tier === "EXACT_CAPTURE_RENDER_AUTHORITY" ? "#0a3" : "#b00";
}

function ensureUni(u) {
  if (uniEls[u]) return uniEls[u];
  const wrap = document.createElement('div'); wrap.className = 'uni';
  const lbl = document.createElement('div');
  lbl.innerHTML = '<b style="color:#e8edf6">Universe ' + u +
    '</b> <span class="muted" id="um' + u + '"></span>';
  const cv = document.createElement('canvas');
  cv.width = COLS * CELL; cv.height = ROWS * CELL;
  wrap.appendChild(lbl); wrap.appendChild(cv);
  document.getElementById('unis').appendChild(wrap);
  uniEls[u] = { canvas: cv, ctx: cv.getContext('2d'),
                meta: document.getElementById('um' + u) };
  return uniEls[u];
}

function drawUni(u, values) {
  const o = ensureUni(u), ctx = o.ctx;
  for (let i = 0; i < 512; i++) {
    const v = values[i] || 0, x = (i % COLS) * CELL, y = Math.floor(i / COLS) * CELL;
    // heat ramp: dark -> cyan -> white
    const t = v / 255;
    const r = Math.round(20 + t * t * 235), g = Math.round(30 + t * 200), b = Math.round(50 + t * 150);
    ctx.fillStyle = v ? 'rgb(' + r + ',' + g + ',' + b + ')' : '#0e1118';
    ctx.fillRect(x, y, CELL - 1, CELL - 1);
  }
}

function ensureFx(f, idx) {
  if (fxEls[idx]) return fxEls[idx];
  const box = document.createElement('div'); box.className = 'fx';
  // Build the title with textContent (not innerHTML) so fixture names that
  // become external can't inject markup.
  const h3 = document.createElement('h3');
  h3.textContent = f.name + ' ';
  const meta = document.createElement('span'); meta.className = 'muted';
  meta.textContent = 'U' + f.universe + ' · ch ' + f.start + '–' + (f.start + f.count - 1);
  h3.appendChild(meta); box.appendChild(h3);
  const rows = [];
  for (let c = 0; c < f.count; c++) {
    const row = document.createElement('div'); row.className = 'ch';
    row.innerHTML = '<span class="n muted">ch' + (f.start + c) + '</span>' +
      '<span class="bar"><i style="width:0%"></i></span><span class="v">0</span>';
    box.appendChild(row);
    rows.push({ bar: row.querySelector('i'), v: row.querySelector('.v') });
  }
  document.getElementById('fixtures').appendChild(box);
  fxEls[idx] = { rows, f }; return fxEls[idx];
}

function drawFx(f, idx, values) {
  const o = ensureFx(f, idx);
  for (let c = 0; c < f.count; c++) {
    const v = values[f.start - 1 + c] || 0;
    o.rows[c].bar.style.width = (v / 255 * 100).toFixed(0) + '%';
    o.rows[c].v.textContent = v;
  }
}

// ---- decoded fixture state panel ----
function dline(parent, key, val) {
  const r = document.createElement('div'); r.className = 'dline';
  const k = document.createElement('span'); k.className = 'dk'; k.textContent = key;
  const b = document.createElement('b'); b.textContent = val;
  r.appendChild(k); r.appendChild(b); parent.appendChild(r);
  return b;
}
function fmtAS(o) { return (!o || o.mode === 'off') ? '—' : (o.mode + ' ' + o.val); }

function renderDecoded(list) {
  const root = document.getElementById('decoded');
  root.textContent = '';
  list.forEach(d => {
    const box = document.createElement('div'); box.className = 'fx';
    const h = document.createElement('h3'); h.textContent = d.name + ' ';
    const m = document.createElement('span'); m.className = 'muted';
    m.textContent = 'U' + d.universe;
    h.appendChild(m); box.appendChild(h);

    // CH1=1 is "1%" not 0% — never round a powered fixture down to 0.
    dline(box, 'power', d.power ? ('ON ' + Math.max(1, Math.round(d.dimmer * 100)) + '%') : 'OFF');
    const cb = dline(box, 'colour', d.color.label + (d.color.animated ? ' (' + d.color.speed + ')' : ''));
    if (d.color.rgb) {
      const sw = document.createElement('span'); sw.className = 'sw';
      sw.style.background = 'rgb(' + d.color.rgb.join(',') + ')';
      cb.appendChild(sw);
    }
    const sel = d.pattern.selection;
    const selTxt = sel.play_all ? 'all' : (sel.index != null ? ('#' + sel.index) : '—');
    dline(box, 'pattern', d.pattern.kind + ' g' + d.pattern.group + ' ' + selTxt + ' · size ' + d.pattern.size);
    dline(box, 'position', '(' + d.position.x + ', ' + d.position.y + ')' +
      (d.position.blanked ? ' BLANK' : d.position.centered ? ' centre' : ''));
    dline(box, 'rotation', 'Z ' + fmtAS(d.rotation.z) + ' · X ' + fmtAS(d.rotation.x) + ' · Y ' + fmtAS(d.rotation.y));
    dline(box, 'movement', 'H ' + fmtAS(d.movement.h) + ' · V ' + fmtAS(d.movement.v));
    dline(box, 'zoom', fmtAS(d.zoom));
    dline(box, 'scan', d.scan.mode + ' ' + d.scan.speed);
    dline(box, 'strobe', d.strobe.on ? ('on ' + d.strobe.speed) : 'off');
    dline(box, '2nd pattern', d.second_pattern ? 'active' : '—');
    root.appendChild(box);
  });
}

// Laser render stage (renderer.js runs its own rAF loop; we only feed it state)
const laser = new LaserRenderer(document.getElementById('stage'));

function initQuarantinePreviewControls() {
  const ch19Sel = document.getElementById('q-ch19');
  const fanSel = document.getElementById('q-fan');
  const statusEl = document.getElementById('q-status');
  if (!ch19Sel || !fanSel || !laser.setQuarantinePreview) return;

  const params = new URLSearchParams(window.location.search || '');
  const quickPreview = params.get('quarantinePreview') === '1';
  let ch19 = params.get('ch19Quarantine') || '';
  let fan = params.get('fanMotionQuarantine') || '';
  if (!ch19 && !fan) {
    try {
      ch19 = localStorage.getItem('vln_quarantine_ch19') || '';
      fan = localStorage.getItem('vln_quarantine_fan') || '';
    } catch (e) {}
  }
  if (quickPreview) {
    if (!ch19) ch19 = 'fixed';
    if (!fan) fan = 'scan_phase';
  }

  const apply = (ch19Wave, fanMotion) => {
    laser.setQuarantinePreview({ ch19Wave: ch19Wave, fanMotion: fanMotion });
    ch19Sel.value = ch19Wave || 'off';
    fanSel.value = fanMotion || 'off';
    if (statusEl) {
      const p = laser.getQuarantinePreview ? laser.getQuarantinePreview() : {};
      statusEl.textContent = 'active: CH19=' + (p.ch19Wave || 'off') + ', fan=' + (p.fanMotion || 'off');
    }
  };

  apply(ch19 || 'off', fan || 'off');
  ch19Sel.addEventListener('change', () => apply(ch19Sel.value, fanSel.value));
  fanSel.addEventListener('change', () => apply(ch19Sel.value, fanSel.value));
}
initQuarantinePreviewControls();

const es = new EventSource('/stream');
es.onopen = () => {
  document.getElementById('dot').className = 'dot live';
  document.getElementById('conn').textContent = 'live';
};
es.onerror = () => {
  document.getElementById('dot').className = 'dot';
  document.getElementById('conn').textContent = 'reconnecting…';
};
es.onmessage = (e) => {
  let d = {};
  try {
    d = JSON.parse(e.data);
  } catch (err) {
    console.error("Malformed SSE payload", err);
    return;
  }
  const universes = d.universes && typeof d.universes === "object" ? d.universes : {};
  const fixtures = Array.isArray(d.fixtures) ? d.fixtures : [];
  const decoded = Array.isArray(d.decoded) ? d.decoded : [];
  const composed = Array.isArray(d.composed) ? d.composed : [];
  const fixtureModels = Array.isArray(d.fixture_models) ? d.fixture_models : [];

  document.getElementById('nuni').textContent = Object.keys(universes).length;
  document.getElementById('polls').textContent = d.polls || 0;
  const sourceState = composed.length ? composed : decoded;
  const captureGeometry = d.analysis_geometry || null;
  if (captureGeometry && laser.setCaptureGeometry) {
    laser.setCaptureGeometry(captureGeometry);
  }
  const renderState = sourceState.map((fx, i) => {
    const fm = fixtureModels[i] || {};
    const cl = fm.capture_lookup || null;
    return {
      ...fx,
      __capture_lookup: cl,
      __provenance_label: cl && cl.provenance_label ? cl.provenance_label : 'MEASURED_FIXTURE_MODEL',
      __model_status: fm.model_status || 'unknown',
      __model_confidence: fm.confidence || 'unknown',
      __capture_geometry: captureGeometry,
    };
  });
  laser.update(renderState);
  
  if (decoded.length) { renderDecoded(decoded); }
  
  const diagEl = document.getElementById('diagnostics');
  if (d.fixture_models && d.fixture_models.length > 0) {
    const fm = d.fixture_models[0] || {};
    const conf = fm.confidence;
    const el = document.getElementById('confidence');
    if (el) {
        el.textContent = conf || "unknown";
        if (conf === 'measured_exact') el.style.background = '#0a3';
        else if (conf === 'measured_estimated') el.style.background = '#a80';
        else el.style.background = '#800';
        el.style.color = '#fff';
    }
    if (diagEl) {
        diagEl.style.display = 'block';
        diagEl.textContent = '';
        const appendLine = (label, value) => {
            const div = document.createElement('div');
            div.style.marginBottom = '4px';
            const b = document.createElement('b');
            b.textContent = label + ': ';
            div.appendChild(b);
            const span = document.createElement('span');
            span.textContent = value;
            div.appendChild(span);
            diagEl.appendChild(div);
            // Return the value span so callers can style it (e.g. colour the
            // headline). Callers must still null-guard before using it.
            return span;
        };
        appendLine('Unsupported', (fm.unsupported || []).join(', ') || 'None');
        appendLine('Coverage', JSON.stringify(fm.coverage || {}));
        const cl = fm.capture_lookup || {};
        const dbg = laser.getDebugState ? laser.getDebugState() : {};
        const motion = Array.isArray(dbg.motionStates) ? dbg.motionStates : [];
        const primary = motion.find(m => m && m.fixture && m.fixture.layerKind === 'primary') || {};
        const paramTiers = (primary.fixture && primary.fixture.parameterTiers) || {};
        const headlineTier = (primary.fixture && primary.fixture.headlineTier) || 'DECODER_FALLBACK';
        const headline = appendLine('Headline Authority', headlineTier);
        if (headline && headline.style) {
            headline.style.color = authorityColor(headlineTier);
            headline.style.fontWeight = '700';
        }
        appendLine('Vector Provenance', cl.provenance_label || 'unknown');
        appendLine('Capture Hit', String(!!cl.hit));
        appendLine('Capture Fallback', cl.fallback_reason || 'none');
        const cueMatches = Array.isArray(cl.cue_matches) ? cl.cue_matches : [];
        const cueAliases = Array.isArray(cl.cue_aliases) ? cl.cue_aliases : cueMatches;
        appendLine('Cue Aliases (' + String(cl.cue_alias_count || cueAliases.length || 0) + ')',
          cueAliases.length ? cueAliases.map(c => c.cue_name || c.cue_id).join(', ') : 'None');
        appendLine('Identity Resolved', String(!!cl.cue_identity_resolved));
        const tierDiv = document.createElement('div');
        tierDiv.style.margin = '6px 0 8px';
        const keys = ['color', 'motion', 'spread', 'count', 'position', 'strobe', 'dots'];
        const rows = keys.map(k => k + '=' + (paramTiers[k] || 'DECODER_FALLBACK'));
        tierDiv.textContent = 'Parameter Tiers: ' + rows.join(' | ');
        diagEl.appendChild(tierDiv);
        appendLine('Composition Applied', (fm.composition_applied || []).join(', ') || 'None');
        appendLine('Composition Supported', (fm.composition_supported || []).join(', ') || 'None');
        appendLine('Composition Missing', JSON.stringify(fm.composition_missing || []));
        appendLine('Gating Missing/Partial', (fm.gating_missing || []).join(', ') + ' / ' + (fm.gating_partial || []).join(', '));
        const vis = primary.visibility || {};
        const aim = primary.aim || {};
        const strobe = primary.strobe || {};
        const warns = Array.isArray(primary.warnings) ? primary.warnings : [];
        appendLine('Sound Override', String(!!dbg.soundOverride));
        appendLine('Motion Provenance', primary.fixture && primary.fixture.motionProvenance ? primary.fixture.motionProvenance : 'unknown');
        appendLine('Visible Before/After Strobe', String(!!vis.visibleBeforeStrobe) + ' / ' + String(!!vis.visibleAfterStrobe));
        appendLine('Visibility Kill Reason', vis.killReason || 'none');
        appendLine('CH10 Draw Mode', (primary.scan && primary.scan.drawMode) || 'unknown');
        appendLine('Aim hFinal/vFinal', [
          Number.isFinite(aim.hFinal) ? aim.hFinal.toFixed(3) : '0.000',
          Number.isFinite(aim.vFinal) ? aim.vFinal.toFixed(3) : '0.000'
        ].join(' / '));
        appendLine('Strobe Square Gate', [
          'active=' + String(!!strobe.active),
          'open=' + String(!!strobe.gateOpen),
          'duty=' + (Number.isFinite(strobe.duty) ? strobe.duty.toFixed(3) : '0.000'),
          'phase=' + (Number.isFinite(strobe.phase) ? strobe.phase.toFixed(3) : '0.000')
        ].join(', '));
        appendLine('Motion Warnings', warns.length ? warns.join(', ') : 'None');
        appendLine('Toggle Sound Override', '?soundOverride=1 (URL)');
        const byLayer = motion.reduce((acc, m) => {
          if (!m || !m.fixture) return acc;
          const key = m.fixture.layerKind || 'unknown';
          if (!acc[key]) acc[key] = [];
          acc[key].push(m);
          return acc;
        }, {});
        const trustRoot = document.createElement('div');
        trustRoot.className = 'diag-trust';
        const trustTitle = document.createElement('div');
        trustTitle.className = 'diag-title';
        trustTitle.textContent = 'Renderer trust diagnostics';
        trustRoot.appendChild(trustTitle);
        ['primary', 'second_pattern'].forEach(layerKey => {
          const layerStates = byLayer[layerKey] || [];
          if (!layerStates.length) return;
          const section = document.createElement('div');
          section.className = 'diag-layer';
          const head = document.createElement('div');
          head.className = 'diag-layer-head';
          head.textContent = layerKey + ' (' + layerStates.length + ')';
          section.appendChild(head);
          layerStates.slice(0, 4).forEach((ms, idx) => {
            const row = document.createElement('div');
            row.className = 'diag-layer-row';
            const visState = ms.visibility && ms.visibility.visibleAfterStrobe ? 'visible' : 'hidden';
            const kill = ms.visibility && ms.visibility.killReason ? ms.visibility.killReason : 'none';
            const warnsTxt = Array.isArray(ms.warnings) && ms.warnings.length ? ms.warnings.slice(0, 3).join(', ') : 'none';
            const warnsCount = Array.isArray(ms.warnings) ? ms.warnings.length : 0;
            row.textContent = [
              '#' + idx,
              ms.fixture.name || 'fixture',
              'U' + String(ms.fixture.universe || 0),
              'capture=' + (ms.fixture.captureProvenance || 'unknown'),
              'motion=' + (ms.fixture.motionProvenance || 'unknown'),
              'model=' + (ms.fixture.modelStatus || 'unknown'),
              'vis=' + visState,
              'kill=' + kill,
              'warn=' + warnsTxt,
              'warnCount=' + String(warnsCount)
            ].join(' | ');
            section.appendChild(row);
          });
          trustRoot.appendChild(section);
        });
        diagEl.appendChild(trustRoot);
    }
  } else {
    const el = document.getElementById('confidence');
    if (el) { el.textContent = 'model: unavailable'; el.style.background = '#444'; el.style.color = '#fff'; }
    if (diagEl) { diagEl.style.display = 'none'; }
  }
  for (const u in universes) {
    const us = universes[u];
    drawUni(u, us.values || []);
    ensureUni(u).meta.textContent = 'fps ' + (us.fps || 0) + ' · src ' + (us.src || 'none') + ' · pkts ' + (us.pkts || 0);
  }
  fixtures.forEach((f, i) => {
    if (!f || f.universe == null) return;
    const vals = (universes[f.universe] || {}).values || [];
    drawFx(f, i, vals);
  });
};
