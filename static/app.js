// VirtualLaserNode — channel inspector frontend.
// Consumes the /stream SSE feed and draws a 512-channel heatmap per universe
// plus the fixture patch. (Step 6 renderer will be added alongside this.)

const COLS = 32, ROWS = 16, CELL = 20;
const uniEls = {};   // universe -> {canvas, ctx, meta}
const fxEls = {};

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
  const d = JSON.parse(e.data);
  document.getElementById('nuni').textContent = Object.keys(d.universes).length;
  document.getElementById('polls').textContent = d.polls;
  if (d.composed) {
    laser.update(d.composed);
  } else if (d.decoded) {
    laser.update(d.decoded);
  }
  
  if (d.decoded) { renderDecoded(d.decoded); }
  
  if (d.fixture_models && d.fixture_models.length > 0) {
    const conf = d.fixture_models[0].confidence;
    const el = document.getElementById('confidence');
    if (el) {
        el.textContent = conf || "unknown";
        if (conf === 'measured_exact') el.style.background = '#0a3';
        else if (conf === 'measured_estimated') el.style.background = '#a80';
        else el.style.background = '#800';
        el.style.color = '#fff';
    }
  }
  for (const u in d.universes) {
    const us = d.universes[u];
    drawUni(u, us.values);
    ensureUni(u).meta.textContent = 'fps ' + us.fps + ' · src ' + us.src + ' · pkts ' + us.pkts;
  }
  d.fixtures.forEach((f, i) => {
    const vals = (d.universes[f.universe] || {}).values;
    if (vals) drawFx(f, i, vals);
  });
};
