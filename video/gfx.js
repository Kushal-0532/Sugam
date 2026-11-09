// Watercolour + ink motion graphics. Pure function of time: seek(t). 24 fps, 1080x1350.
const NS = 'http://www.w3.org/2000/svg';
const INK = '#2f3e46', RED = '#bc4749', GRN = '#6a994e', BLU = '#a7c4d2';
const WASH = { blue: BLU, ok: GRN, ask: BLU, block: RED, red: RED, green: GRN };
const FPS = 24, BLOOM = 20 / FPS; // washes spread over 20 frames
const stage = document.getElementById('stage');
const TL = window.TL;
const tl = gsap.timeline({ paused: true });

const el = (tag, a = {}, p = stage) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
const rng = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
let _seed = 100; const nextSeed = () => (_seed += 17);

function smooth(p) { // closed Catmull-Rom -> bezier
  const n = p.length; let d = `M${p[0][0].toFixed(1)} ${p[0][1].toFixed(1)}`;
  for (let i = 0; i < n; i++) {
    const a = p[(i - 1 + n) % n], b = p[i], c = p[(i + 1) % n], e = p[(i + 2) % n];
    d += `C${(b[0] + (c[0] - a[0]) / 6).toFixed(1)} ${(b[1] + (c[1] - a[1]) / 6).toFixed(1)} ${(c[0] - (e[0] - b[0]) / 6).toFixed(1)} ${(c[1] - (e[1] - b[1]) / 6).toFixed(1)} ${c[0].toFixed(1)} ${c[1].toFixed(1)}`;
  }
  return d + 'Z';
}
function blobD(x, y, w, h, seed, pad = 10) {
  const r = rng(seed), n = 28, cx = x + w / 2, cy = y + h / 2, pts = [];
  for (let i = 0; i < n; i++) {
    const a = i / n * 2 * Math.PI, c = Math.cos(a), s = Math.sin(a);
    const px = Math.sign(c) * Math.abs(c) ** 0.3 * (w / 2 + pad), py = Math.sign(s) * Math.abs(s) ** 0.3 * (h / 2 + pad);
    pts.push([cx + px + (r() - .5) * 7, cy + py + (r() - .5) * 7]);
  }
  return smooth(pts);
}
// wash: pigment pool, two layers, bleeds past the ink via #bleed. Starts hidden; bloom() reveals it.
function wash(P, x, y, w, h, color, op = .5, pad = 12) {
  const g = el('g', { opacity: 0, filter: 'url(#bleed)', style: 'mix-blend-mode:multiply' }, P);
  const s = nextSeed();
  el('path', { d: blobD(x, y, w, h, s, pad), fill: color, opacity: op }, g);
  el('path', { d: blobD(x + w * .08, y + h * .1, w * .84, h * .8, s + 3, 0), fill: color, opacity: op * .55 }, g);
  g._cx = x + w / 2; g._cy = y + h / 2; return g;
}
const bloom = (g, at, to = 1) => { tl.fromTo(g, { opacity: 0, scale: .9, svgOrigin: `${g._cx} ${g._cy}` }, { opacity: to, scale: 1, svgOrigin: `${g._cx} ${g._cy}`, duration: BLOOM, ease: 'power2.out' }, at); };

// brush ink: jittered double stroke, drawn with dashoffset
function inkPath(P, d, sw = 3.5, color = INK) {
  const g = el('g', { fill: 'none', stroke: color, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, P);
  const a = el('path', { d, 'stroke-width': sw, pathLength: 1, 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 }, g);
  const b = el('path', { d, 'stroke-width': sw * .45, opacity: .55, transform: 'translate(1.6 1.2)', pathLength: 1, 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 }, g);
  g._p = [a, b]; return g;
}
const draw = (g, at, dur = .5) => tl.to(g._p, { strokeDashoffset: 0, duration: dur, ease: 'power1.inOut' }, at);
const erase = (g, at, dur = .3) => tl.to(g._p, { strokeDashoffset: -1, duration: dur, ease: 'power1.in' }, at);
function rectD(x, y, w, h, seed, j = 2.6) {
  const r = rng(seed), P = [], step = 38, J = () => (r() - .5) * 2 * j;
  const edge = (x0, y0, x1, y1) => { const n = Math.max(2, Math.round(Math.hypot(x1 - x0, y1 - y0) / step)); for (let i = 0; i < n; i++) P.push([x0 + (x1 - x0) * i / n + J(), y0 + (y1 - y0) * i / n + J()]); };
  edge(x, y, x + w, y); edge(x + w, y, x + w, y + h); edge(x + w, y + h, x, y + h); edge(x, y + h, x, y);
  return 'M' + P.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L') + `L${P[0][0] + 14} ${P[0][1] + 1}`;
}
const brushRect = (P, x, y, w, h, sw = 3.5, color = INK) => inkPath(P, rectD(x, y, w, h, nextSeed()), sw, color);
function ellipseD(cx, cy, rx, ry, seed) {
  const r = rng(seed); let d = ''; const n = 40;
  for (let i = 0; i <= n + 3; i++) { const a = i / n * 2 * Math.PI, k = 1 + (r() - .5) * .06 + i * .0016; d += (i ? 'L' : 'M') + (cx + Math.cos(a) * rx * k).toFixed(1) + ' ' + (cy + Math.sin(a) * ry * k).toFixed(1); }
  return d;
}
function T(P, str, x, y, size, o = {}) {
  const t = el('text', { x, y, 'font-size': size, fill: o.fill || INK, 'text-anchor': o.anchor || 'start', class: o.cls || '' }, P);
  const lines = String(str).split('\n'); t._ts = lines.map((l, i) => { const s = el('tspan', { x, dy: i ? size * (o.lh || 1.22) : 0 }, t); s.textContent = l; return s; });
  return t;
}
// underline fitted to a text's real width; refit on every seek (webfont may load after build)
// word wrap by real measured width: a line breaks only when the next word would not fit. Runs on seek until the
// webfont is loaded (measuring the fallback font would break lines in the wrong places).
const WRAPS = []; let wrapped = false;
function wrapText(t, str, maxW, after) { WRAPS.push(() => {
  const words = str.split(/\s+/), lines = []; let cur = '';
  for (const w of words) { const c = cur ? cur + ' ' + w : w; t.textContent = c; if (cur && t.getComputedTextLength() > maxW) { lines.push(cur); cur = w; } else cur = c; }
  lines.push(cur); t.textContent = '';
  const lh = +t.getAttribute('font-size') * (t._lh || 1.22);
  lines.forEach((l, i) => { const s = el('tspan', { x: t.getAttribute('x'), dy: i ? lh : 0 }, t); s.textContent = l; });
  if (after) after(lines.length, lh);
}); }
const ULINES = [];
function uline(P, t, y, sw) { const u = inkPath(P, 'M0 0L1 0', sw, RED); ULINES.push([u, t, y]); return u; }
function fitUlines() { ULINES.forEach(([u, t, y]) => { const b = t.getBBox(), x0 = b.x - 12, x1 = b.x + b.width + 12, w = x1 - x0;
  const d = `M${x0.toFixed(1)} ${y + 3}C${(x0 + w * .3).toFixed(1)} ${y - 6} ${(x0 + w * .7).toFixed(1)} ${y + 7} ${x1.toFixed(1)} ${y - 2}`; u._p.forEach(p => p.setAttribute('d', d)); }); }
const fade = (g, a, b, fi = .25, fo = .3) => { tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: fi }, a); tl.to(g, { opacity: 0, duration: fo }, b); };

function typeIn(t, lines, at, dur) { // grapheme-safe typewriter
  const segs = lines.map(l => [...new Intl.Segmenter().segment(l)].map(s => s.segment));
  const total = segs.reduce((a, b) => a + b.length, 0), o = { k: 0 };
  const upd = () => { let k = Math.round(o.k); t._ts.forEach((ts, i) => { const n = Math.min(k, segs[i].length); ts.textContent = segs[i].slice(0, n).join(''); k -= n; }); };
  upd(); tl.to(o, { k: total, duration: dur, ease: 'none', onUpdate: upd }, at);
}
function wordIn(t, lines, at, dur) { // word by word
  const words = lines.map(l => l.split(' ')), total = words.flat().length, o = { k: 0 };
  const upd = () => { let k = Math.round(o.k); t._ts.forEach((ts, i) => { const n = Math.min(k, words[i].length); ts.textContent = words[i].slice(0, n).join(' '); k -= n; }); };
  upd(); tl.to(o, { k: total, duration: dur, ease: 'none', onUpdate: upd }, at);
}
// waveform of ink strokes. amps optional (real audio), else synthetic from seed.
function wave(P, x, y, w, h, amps, color, at, dur) {
  const n = 44, r = rng(nextSeed()), g = el('g', { stroke: color, 'stroke-linecap': 'round', 'stroke-width': 6 }, P), L = [];
  for (let i = 0; i < n; i++) {
    const a = amps ? amps[Math.floor(i / n * amps.length)] : (.25 + .75 * r()) * Math.sin(Math.PI * (i + 1) / (n + 1)) ** .6;
    const cx = x + (i + .5) * w / n, hh = Math.max(3, a * h / 2);
    L.push(el('line', { x1: cx, x2: cx, y1: y - hh, y2: y + hh, opacity: 0 }, g));
  }
  const o = { k: 0 }, upd = () => L.forEach((l, i) => l.setAttribute('opacity', i < o.k ? .85 : 0));
  upd(); tl.to(o, { k: n, duration: dur, ease: 'none', onUpdate: upd }, at); return g;
}

// ---------- fixed layer: pipeline bar ----------
const NODES = ['VOICE', 'PRISMA', 'ROUTER', 'SAFETY', 'PHONE', 'TIMBRE'], NW = 156, NG = 16, NX0 = 24, NY = 55, NH = 70;
const nx = i => NX0 + i * (NW + NG), ncx = i => nx(i) + NW / 2;
const bar = el('g'); const barRect = [], packetPts = [];
NODES.forEach((n, i) => {
  barRect.push(brushRect(bar, nx(i), NY, NW, NH, 3.5)); T(bar, n, ncx(i), NY + 47, 38, { anchor: 'middle' });
  if (i < 5) { const l = inkPath(bar, `M${nx(i) + NW + 2} ${NY + 35}L${nx(i + 1) - 2} ${NY + 35}`, 3); barRect.push(l); }
});
const DEMO0 = TL.scenes.find(s => s.take).start; // bar + phone frame draw in when the first take starts (hidden under title/arch before)
nextSeed(); nextSeed(); // were the PRISMA/TIMBRE "G" badge washes (removed in v3, read as smudges); keeps every later shape's jitter identical
barRect.forEach((b, i) => { if (b._p) draw(b, DEMO0 - .3 + i * .03, .4); if (b._w) bloom(b._w, DEMO0); });
tl.fromTo(bar, { opacity: 0 }, { opacity: 1, duration: .4 }, DEMO0 - .4);
const packet = el('g', { filter: 'url(#bleed)' }); const pk = el('circle', { cx: ncx(0), cy: NY + NH + 12, r: 9, fill: INK, opacity: 0 }, packet);

// ---------- phone frame (hole is transparent for the recording) ----------
const phone = el('g'); const pf = brushRect(phone, 30, 230, 474, 1060, 5); draw(pf, DEMO0 - .5, .8);
if (TL.mock) { const m = el('g', {}, phone); el('rect', { x: 30, y: 230, width: 474, height: 1060, rx: 40, fill: '#f4efe6' }, m); const mw = wash(m, 36, 236, 462, 1048, BLU, .22, 0); bloom(mw, .4); T(m, '[ phone recording ]', 267, 760, 34, { anchor: 'middle', fill: INK }); }
else { /* real run: hole stays transparent */ }

// ---------- scene tag + timer ----------
const tagG = [];
function sceneTag(s) { if (!s.tag) return; const g = el('g', { opacity: 0 }); T(g, s.tag, 34, 212, 36); fade(g, s.start + .4, s.end - .3); tagG.push(g); }
const timerT = el('text', { x: 500, y: 212, 'font-size': 32, 'text-anchor': 'end', fill: INK, opacity: 0 });
const speedT = el('text', { x: 267, y: 1262, 'font-size': 52, 'text-anchor': 'middle', fill: RED, opacity: 0, stroke: '#f4efe6', 'stroke-width': 9, 'paint-order': 'stroke' });
const mm = v => `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, '0')}`;
function updateTimer(t) { return; // no speed-ups in this cut: no timer / speed label

  const s = TL.scenes.find(x => t >= x.start && t < x.end && x.id <= 4);
  if (!s || t < s.start + .4) { timerT.setAttribute('opacity', 0); speedT.setAttribute('opacity', 0); return; }
  timerT.setAttribute('opacity', 1); timerT.textContent = '';
  const real = (t - s.start) * s.speed; speedT.textContent = `${s.speed}× speed`; speedT.setAttribute('opacity', s.speed > 1 ? 1 : 0);
  timerT.textContent = `${mm(real)} real`;
}

// ---------- cards ----------
const CX = 530, CW = 520;
function card(P, y, h, title, color, at, chip) {
  const g = el('g', { opacity: 0, 'data-box': `${CX} ${y} ${CW} ${h}` }, P), w = wash(g, CX, y, CW, h, color, .32, 12), b = brushRect(g, CX, y, CW, h, 3.5);
  T(g, title, CX + 22, y + 42, 34); if (chip) T(g, chip, CX + CW - 20, y + 42, 28, { anchor: 'end' });
  tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: .2 }, at); bloom(w, at); draw(b, at, .6);
  return g;
}
const tick = (P, x, y, at) => { const t = inkPath(P, `M${x} ${y}l9 11l20 -24`, 4.5, GRN); draw(t, at, .3); };

function buildScene(s) {
  const P = el('g'), a = s.start;
  sceneTag(s);
  // HEARD
  if (s.heard) {
    const h = s.heard, g = card(P, 190, 330, 'HEARD', BLU, h.at, 'Gnani Prisma v3.0');
    wave(g, CX + 24, 262, CW - 48, 46, h.amps, INK, h.at + .1, h.dur);
    const ta = h.textAt ?? h.at + h.dur * .5, td = h.textDur ?? h.dur, tg = h.textAt ? ta + td + .1 : h.at + h.dur * 1.6;
    const tt = T(g, h.text, CX + 24, 342, 36, { cls: 'te' }); typeIn(tt, h.text.split('\n'), ta, td);
    const gl = T(g, 'gloss: ' + h.gloss, CX + 24, 342 + (h.text.split('\n').length - 1) * 44 + 48, 26, { fill: INK, lh: 1.15 });
    tl.fromTo(gl, { opacity: 0 }, { opacity: .8, duration: .4 }, tg);
    const ch = T(g, `${h.lang} · ${h.stt}`, CX + 24, 502, 26, { fill: RED }); tl.fromTo(ch, { opacity: 0 }, { opacity: 1, duration: .3 }, tg);
    tl.to(g, { opacity: 0, duration: .3 }, s.end - .35);
  }
  // ROUTER
  if (s.route) {
    const r = s.route, g = card(P, 535, 265, 'ROUTER', BLU, r.at, 'Jev decides');
    const l1 = T(g, `intent: ${r.intent}   lang: ${r.lang}`, CX + 24, 614, 32, { fill: RED }); tl.fromTo(l1, { opacity: 0 }, { opacity: 1, duration: .3 }, r.at + .3);
    if (r.stepCount) { const sc = T(g, '', CX + CW - 20, 614, 28, { anchor: 'end' }); const o = { k: 0 }; const n = r.steps.length;
      tl.to(o, { k: n, duration: r.steps[n - 1][0] - r.steps[0][0], ease: 'none', onUpdate: () => { const k = Math.ceil(o.k); sc.textContent = k ? `step ${k} / ${r.stepCount} max` : ''; } }, r.steps[0][0]); }
    r.steps.forEach(([t, txt], i) => { const y = 664 + i * 34; const st = T(g, txt, CX + 64, y, 30); tl.fromTo(st, { opacity: 0 }, { opacity: 1, duration: .25 }, t); tick(g, CX + 26, y - 4, t + .35); });
    tl.to(g, { opacity: 0, duration: .3 }, s.end - .35);
  }
  // SAFETY
  if (s.safety) {
    const f = s.safety, col = WASH[f.state], g = card(P, 815, 190, 'SAFETY', col, f.at, 'deterministic rules'); // 815..1005: 2-line reason fits
    const wd = T(g, f.word, CX + 24, 910, 54, { fill: f.state === 'block' ? RED : f.state === 'ok' ? GRN : INK });
    tl.fromTo(wd, { opacity: 0, scale: 1.25, svgOrigin: `${CX + 24} 895` }, { opacity: 1, scale: 1, duration: .25, ease: 'back.out(2)' }, f.at + .3);
    T(g, f.why, CX + 24, 950, 28, { fill: INK });
    tl.to(g, { opacity: 0, duration: .3 }, s.end - .35);
  }
  // SAID
  [].concat(s.said || []).forEach(d => {
    const g = card(P, 1020, 270, 'SAID', BLU, d.at, 'Gnani Timbre v3.0 · Lakshmi');
    wave(g, CX + 24, 1094, CW - 48, 34, d.amps, GRN, d.at + .1, d.dur);
    const tt = T(g, d.text, CX + 24, 1150, 36, { cls: /[ఀ-౿]/.test(d.text) ? 'te' : '' }); wordIn(tt, d.text.split('\n'), d.at + .3, d.dur);
    const gl = T(g, d.gloss, CX + 24, 1150 + 44 * (d.text.split('\n').length - 1) + 42, 26, { fill: INK, lh: 1.15 }); tl.fromTo(gl, { opacity: 0 }, { opacity: .8, duration: .4 }, d.at + d.dur);
    tl.to(g, { opacity: 0, duration: .3 }, d.end ?? s.end - .35);
  });
  // footer note
  if (s.note) { const n = T(P, s.note + (TL.mock ? '' : ''), 34, 1328, 30, { fill: INK }); fade(n, s.noteAt ?? a + .8, s.end - .3); }
  // taps: ink ripple + short line + label inside phone
  (s.taps || []).forEach(([t, px, py, lab]) => {
    const x = 30 + px, y = 230 + py, c1 = inkPath(P, ellipseD(x, y, 22, 22, nextSeed()), 4, RED), c2 = inkPath(P, ellipseD(x, y, 40, 40, nextSeed()), 3, RED);
    draw(c1, t, .25); draw(c2, t + .1, .3); erase(c1, t + 1.1); erase(c2, t + 1.1);
    const ln = inkPath(P, `M${x} ${y - 42}L${x + 30} ${y - 90}`, 3.5), lb = T(P, lab, x + 36, y - 94, 30, { fill: INK });
    draw(ln, t + .15, .25); tl.fromTo(lb, { opacity: 0 }, { opacity: 1, duration: .25 }, t + .35); erase(ln, t + 1.2); tl.to(lb, { opacity: 0, duration: .3 }, t + 1.2);
  });
  // circled call button + NOT tapped stamp
  if (s.circle) {
    const [t, px, py, lab] = s.circle, x = 30 + px, y = 230 + py, c = inkPath(P, ellipseD(x, y, 78, 78, nextSeed()), 6, RED);
    draw(c, t, .5); const w = wash(P, x - 150, y - 150, 300, 300, RED, .22, 0); bloom(w, t + .1);
    stamp(P, lab, 267, 1050, t + .7, s.end - .3, -7); // below the Call button, not over it
    const sb = T(P, s.sub, 540, 1328, 30, { fill: RED }); fade(sb, t + 1.1, s.end - .3);
    erase(c, s.end - .4); tl.to(w, { opacity: 0, duration: .3 }, s.end - .4);
  }
  if (s.stamp) stamp(P, s.stamp[1], 267, 700, s.stamp[0], s.end - .3, -8);
  // pipeline events (persistent bar)
  s.pipe.forEach(([t, node, state, sub]) => {
    const i = NODES.indexOf(node), w = wash(bar, nx(i), NY, NW, NH, WASH[state], .6, 10); bloom(w, t);
    tl.to(w, { opacity: .35, duration: .6 }, t + 1.2); tl.to(w, { opacity: 0, duration: .3 }, s.end - .3);
    const sb = T(bar, sub, ncx(i), NY + NH + 40, 28, { anchor: 'middle', fill: state === 'block' ? RED : INK }); fade(sb, t + .3, s.end - .3, .2, .3);
    const prev = packetPts[packetPts.length - 1];
    if (!prev || prev.s !== s.id) { tl.set(pk, { attr: { cx: ncx(i) } }, t - .6); }
    tl.to(pk, { attr: { cx: ncx(i) }, duration: Math.min(.5, .5), ease: 'power2.inOut' }, t - .5);
    tl.fromTo(pk, { opacity: 0 }, { opacity: 1, duration: .1 }, t - .5);
    packetPts.push({ s: s.id, t });
  });
  if (s.pipe.length) tl.to(pk, { opacity: 0, duration: .3 }, s.end - .3);
  // agent loop arrow (PHONE back to ROUTER)
  if (s.loop) {
    const [l0, l1] = s.loop, xa = ncx(4), xb = ncx(2), d = `M${xa} ${NY - 4}C${xa} ${NY - 46} ${xb} ${NY - 46} ${xb} ${NY - 6}`;
    const lp = inkPath(P, d, 4, RED); draw(lp, l0, .6); const hd = inkPath(P, `M${xb - 9} ${NY - 20}L${xb} ${NY - 5}L${xb + 10} ${NY - 19}`, 4, RED); draw(hd, l0 + .5, .15);
    const lt = T(P, 'agent loop', (xa + xb) / 2, NY - 20, 28, { anchor: 'middle', fill: RED }); fade(lt, l0 + .5, l1);
    erase(lp, l1); erase(hd, l1, .2);
  }
}
function stamp(P, text, x, y, a, b, rot) {
  const g = el('g', { opacity: 0 }, P), w = wash(g, x - 200, y - 60, 400, 120, RED, .5, 14), r = brushRect(g, x - 205, y - 62, 410, 124, 7, RED);
  const tx = T(g, text, x, y + 22, 74, { anchor: 'middle', fill: RED }); g.setAttribute('transform', `rotate(${rot} ${x} ${y})`);
  tl.fromTo(g, { opacity: 0, scale: 1.4, svgOrigin: `${x} ${y}` }, { opacity: 1, scale: 1, svgOrigin: `${x} ${y}`, duration: .25, ease: 'power3.in' }, a);
  bloom(w, a + .2); draw(r, a + .1, .3); tl.to(g, { opacity: 0, duration: .3 }, b);
}

TL.scenes.filter(s => s.take).forEach(buildScene);

// transitions between takes: phone dips to paper (no hard cut, never black) + light wash swipe along the bar
TL.scenes.filter(s => s.take && s.start > DEMO0).map(s => s.start).forEach(t => {
  const d = el('rect', { x: 26, y: 226, width: 482, height: 1068, rx: 40, fill: '#f4efe6', opacity: 0 });
  tl.to(d, { opacity: 1, duration: .25 }, t - .25); tl.to(d, { opacity: 0, duration: .35 }, t + .05);
  const w = inkPath(stage, `M-20 ${NY + 38}L1100 ${NY + 38}`, 46, BLU); w._p.forEach(p => p.setAttribute('opacity', .6)); draw(w, t - .2, .22); erase(w, t + .05, .22);
});

// ---------- scene 5: results ----------
// full paper sheet: paper + fibre + grain, opaque (covers phone hole and bar)
function sheet(P) { const g = el('g', { 'data-cover': 1 }, P); el('rect', { width: 1080, height: 1350, fill: '#f4efe6' }, g); el('rect', { width: 1080, height: 1350, filter: 'url(#fibre)', opacity: .5 }, g); el('rect', { width: 1080, height: 1350, filter: 'url(#grain)', opacity: .55 }, g); return g; }
(function results() {
  const s = TL.scenes.find(x => x.id === 'results'), R = TL.results, a = s.start, g = el('g', { opacity: 0 });
  const x = 60, y = 140, w = 960, h = 1150;
  const outro = sheet(stage); tl.fromTo(outro, { opacity: 0 }, { opacity: 1, duration: .4 }, a - .1); // stays to the end: no phone/bar behind results + end card
  stage.appendChild(g); g.setAttribute('data-box', `${x} ${y} ${w} ${h}`);
  tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: .3 }, a + .2); tl.to(g, { opacity: 0, duration: .35 }, s.end - .4);
  const bg = wash(g, x, y, w, h, BLU, .22, 14); bloom(bg, a + .2); draw(brushRect(g, x, y, w, h, 4), a + .2, .7);
  T(g, 'Agent eval', x + 40, y + 70, 56); T(g, R.tag, x + 40, y + 120, 32, { fill: RED });
  // 72 strokes: 49 green, 23 faded red
  const r = rng(77), cols = 12, cw = 66, ch = 56, gx = x + 74, gy = y + 190, order = []; const marks = [];
  for (let i = 0; i < R.total; i++) { const c = i % cols, ro = Math.floor(i / cols), ok = i < R.pass; const px = gx + c * cw, py = gy + ro * ch;
    const m = inkPath(g, `M${px} ${py + 22}C${px + 14} ${py + 4} ${px + 30} ${py + 40} ${px + 46} ${py + 18}`, 9, ok ? GRN : RED); if (!ok) m._p.forEach(p => p.setAttribute('opacity', .5)); marks.push(m); }
  marks.forEach((m, i) => draw(m, a + 1 + i * .02, .2));
  const big = T(g, R.pct, x + 40, y + 640, 150, { fill: GRN }), bsub = T(g, `${R.pass} of ${R.total} tasks passed`, x + 40, y + 712, 40);
  tl.fromTo(big, { opacity: 0, scale: 1.2, svgOrigin: `${x + 40} ${y + 600}` }, { opacity: 1, scale: 1, svgOrigin: `${x + 40} ${y + 600}`, duration: .3 }, a + 2.8); tl.fromTo(bsub, { opacity: 0 }, { opacity: 1, duration: .3 }, a + 3);
  const med = T(g, `median ${R.median} per task`, x + 40, y + 780, 46); tl.fromTo(med, { opacity: 0 }, { opacity: 1, duration: .3 }, a + 3.4);
  R.notes.forEach((n, i) => { const yy = y + 850 + i * 52; const t = T(g, '· ' + n, x + 40, yy, 38, { fill: INK }); tl.fromTo(t, { opacity: 0 }, { opacity: 1, duration: .3 }, a + 3.8 + i * .4); });
})();

// ---------- scene 6: end card ----------
(function end() {
  const s = TL.scenes.find(x => x.id === 'end'), E = TL.end, a = s.start, g = el('g', { opacity: 0 });
  tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: .4 }, a); // outro sheet (results) is behind it
  const w = wash(g, 90, 300, 900, 200, BLU, .35, 14); bloom(w, a + .2);
  const et = T(g, E.title, 540, 440, 140, { anchor: 'middle' });
  if (E.tag) { const tg = T(g, E.tag, 540, 548, 42, { anchor: 'middle', fill: RED }); tl.fromTo(tg, { opacity: 0 }, { opacity: 1, duration: .3 }, a + .9); }
  const u = uline(g, et, 440 + 140 * .3, 7); draw(u, a + .8, .6); // fitted to the word, not the card
  E.lines.forEach((l, i) => { const t = T(g, l, 540, 612 + i * 62, 44, { anchor: 'middle', fill: INK }); tl.fromTo(t, { opacity: 0 }, { opacity: 1, duration: .3 }, a + 1 + i * .3); });
  const uw = wash(g, 130, 925, 820, 130, GRN, .35, 12); bloom(uw, a + 2.2); draw(brushRect(g, 130, 925, 820, 130, 4), a + 2.2, .6);
  const url = T(g, TL.repo, 540, 1010, 62, { anchor: 'middle' }); tl.fromTo(url, { opacity: 0 }, { opacity: 1, duration: .3 }, a + 2.6);
  T(g, 'Prisma + Timbre by Gnani AI', 540, 1150, 40, { anchor: 'middle', fill: INK });
  T(g, 'Built for the Great Indian AI Internship Challenge', 540, 1210, 34, { anchor: 'middle', fill: INK });
})();
// ---------- architecture explainer (after title, before the takes) ----------
// emoji packets travel the real pipeline: audio -> Prisma -> guardrails -> Jev router -> workflow | agent -> phone -> Timbre -> you
(function arch() {
  const s = TL.scenes.find(x => x.id === 'arch'); if (!s) return;
  const a = s.start, A = t => a + t, g = sheet(stage);
  tl.to(g, { opacity: 0, duration: .5 }, s.end - .5); // reveals the first take (phone shows its first frame, never black)
  const hd = T(g, 'How Sugam works', 540, 140, 80, { anchor: 'middle' }); fade(hd, A(.1), s.end, .4, .01);
  draw(uline(g, hd, 140 + 80 * .3, 6), A(.6), .5);
  const node = (x, y, w, h, title, sub, at, o = {}) => {
    const n = el('g', { opacity: 0, 'data-box': `${x} ${y} ${w} ${h}` }, g), b = brushRect(n, x, y, w, h, 3.5);
    T(n, title, x + 20, y + 48, 38); if (o.chip) T(n, o.chip, x + w - 18, y + 46, 26, { anchor: 'end', fill: RED });
    if (o.emo) T(n, o.emo, x + w - 34, y + 50, 36, { anchor: 'middle', cls: 'emo' });
    if (sub) { const st = T(n, '', x + 20, y + 88, 28); st._lh = 1.2; wrapText(st, sub, w - 40); }
    tl.fromTo(n, { opacity: 0 }, { opacity: 1, duration: .25 }, at); draw(b, at, .5);
    return { n, x, y, w, h, hi(t, col = BLU, keep = .18) { const w0 = wash(n, x, y, w, h, col, .5, 10); n.insertBefore(w0, n.firstChild); bloom(w0, t); tl.to(w0, { opacity: keep, duration: .6 }, t + 2.2); } };
  };
  const arrow = (pts, at, col = INK, lab, lx, ly) => {
    const d = 'M' + pts.map(p => p.join(' ')).join('L'), [p0, p1] = pts.slice(-2), an = Math.atan2(p1[1] - p0[1], p1[0] - p0[0]);
    const hdD = `M${(p1[0] - 16 * Math.cos(an - .5)).toFixed(1)} ${(p1[1] - 16 * Math.sin(an - .5)).toFixed(1)}L${p1[0]} ${p1[1]}L${(p1[0] - 16 * Math.cos(an + .5)).toFixed(1)} ${(p1[1] - 16 * Math.sin(an + .5)).toFixed(1)}`;
    draw(inkPath(g, d, 3.5, col), at, .4); draw(inkPath(g, hdD, 3.5, col), at + .35, .12);
    if (lab) { const l = T(g, lab, lx, ly, 26, { anchor: 'middle', fill: RED }); tl.fromTo(l, { opacity: 0 }, { opacity: 1, duration: .3 }, at + .3); }
  };
  // packet: emoji on a paper disc; shows at `show`, travels pts during [go, go+dur], hides at `hide`
  const packet = (emo, pts, show, go, dur, hide) => {
    const p = el('g', { opacity: 0, transform: `translate(${pts[0][0]} ${pts[0][1]})` }, g);
    const q = el('g', {}, p); el('circle', { r: 29, fill: '#f4efe6', stroke: INK, 'stroke-width': 3 }, q); T(q, emo, 0, 13, 36, { anchor: 'middle', cls: 'emo' });
    const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const o = { k: 0 }, upd = () => { const d = o.k * L[L.length - 1]; let i = 1; while (i < L.length - 1 && L[i] < d) i++;
      const f = (d - L[i - 1]) / (L[i] - L[i - 1] || 1), x = pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, y = pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f;
      p.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)})`); };
    tl.fromTo(p, { opacity: 0 }, { opacity: 1, duration: .15 }, A(show)); tl.fromTo(q, { scale: .4, svgOrigin: '0 0' }, { scale: 1, svgOrigin: '0 0', duration: .25, ease: 'back.out(2)' }, A(show)); // scale on inner g: outer translate stays ours
    tl.to(o, { k: 1, duration: dur, ease: 'power1.inOut', onUpdate: upd }, A(go)); tl.to(p, { opacity: 0, duration: .2 }, A(hide));
  };
  const pop = (P, txt, x, y, size, t0, t1, o = {}) => { const e = T(P, txt, x, y, size, o); fade(e, A(t0), A(t1)); return e; };

  // nodes (t = seconds into this scene)
  const YOU = node(40, 210, 250, 150, 'You speak', 'Telugu, Hindi, English or a mix', A(.5), { chip: 'Indic' }); // only te/hi/en tested: never claim more
  const PRI = node(390, 210, 300, 150, 'Gnani Prisma', 'speech to text, detects the language', A(.8), { chip: 'STT' });
  const WRD = node(790, 210, 250, 150, 'Guardrails', 'fixed rules: block apps + payments', A(1.1));
  const TIM = node(40, 450, 300, 150, 'Gnani Timbre', 'text to speech, speaks the reply', A(1.4), { chip: 'TTS' });
  const RTR = node(560, 450, 480, 150, 'Router', 'routes: workflow or agent', A(1.7), { chip: 'Jev decides' });
  const HND = node(190, 680, 300, 210, 'Workflow', 'fixed steps in code; the LLM only picks task + time/query', A(2.0)); // Anthropic: workflow = predefined code paths
  const LOP = node(560, 680, 480, 270, 'Agent', null, A(2.3), { chip: 'LLM picks each step · max 25' }); // agent = LLM directs its own steps
  const PHN = node(190, 1030, 700, 110, 'Android phone', 'bot taps and types (uiautomator2 over USB)', A(2.6), { emo: '📱' });
  const steps = ['1. read the screen (UI tree)', '2. Jev / Groq: pick ONE action', '3. guardrails check it (fixed rules)', '4. bot taps or types, looks again'];
  steps.forEach((l, i) => T(LOP.n, l, 615, 765 + i * 44, 28));
  draw(inkPath(LOP.n, 'M598 898C568 898 568 750 596 750', 3.5, RED), A(2.8), .5); draw(inkPath(LOP.n, 'M584 740L598 750L586 762', 3.5, RED), A(3.2), .15);
  arrow([[290, 285], [388, 285]], A(2.9), INK, 'audio', 339, 322);
  arrow([[690, 285], [788, 285]], A(3.0), INK, 'text', 739, 322);
  arrow([[915, 360], [915, 448]], A(3.1));
  arrow([[600, 600], [588, 632], [470, 648], [352, 662], [340, 678]], A(3.2), INK, 'tasks with predefined steps', 420, 624);
  arrow([[915, 600], [915, 678]], A(3.3), INK, 'tasks with unknown steps', 762, 648);
  arrow([[340, 890], [340, 1028]], A(3.4));
  arrow([[700, 950], [700, 1028]], A(3.5), INK, 'tap', 668, 996); arrow([[840, 1030], [840, 952]], A(3.5), INK, 'screen', 893, 996);
  arrow([[190, 1085], [110, 1085], [110, 602]], A(3.6), INK);
  arrow([[165, 450], [165, 362]], A(3.7));

  // captions
  const CB = el('g', { 'data-box': '40 1160 1000 180' }, g); draw(brushRect(CB, 40, 1160, 1000, 180, 3.5), A(.3), .6); bloom(wash(CB, 40, 1160, 1000, 180, BLU, .22, 10), A(.3));
  [[.4, 4.0, 'Sugam turns one spoken sentence into actions on a real Android phone. Here is how it works.'],
   [4.0, 8.0, '1 · You speak in Telugu, Hindi, English or a mix of them. The laptop microphone records your voice.'],
   [8.0, 12.2, '2 · Gnani Prisma v3.0 (speech to text) turns the audio into text and detects which language you spoke.'],
   [12.2, 16.2, '3 · Guardrails run first: fixed rules, not AI. Blocked apps (like WhatsApp) and payment requests stop right here.'],
   [16.2, 20.4, '4 · The router reads the text and picks the route: Jev decides, and a Groq LLM steps in when Jev is unsure.'],
   [20.4, 24.6, '5 · Tasks with predefined steps (alarm, call, YouTube) run as a workflow: the steps are fixed in code, the LLM only fills in details like the time.'],
   [24.6, 32.0, '6 · Tasks with unknown steps go to the agent, which works them out live. Each step: read the screen, the LLM picks ONE action, guardrails check it, the bot taps. Then it reads the screen again, until done.'],
   [32.0, 36.0, '7 · Gnani Timbre v3.0 (text to speech) says the result out loud, in the same language you spoke.'],
   [36.0, 39.0, 'Risky taps, like placing a call, wait for a spoken yes. Next: five real runs on a real phone.']].forEach(([t0, t1, txt]) => {
    const c = T(CB, '', 70, 0, 38); c._lh = 1.25; wrapText(c, txt, 930, (n, lh) => c.setAttribute('y', 1263 - (n - 1) * lh / 2)); // vertically centred in the box
    fade(c, A(t0) + .1, A(t1) - .2, .25, .2); // out fully before the next caption fades in
  });

  // 1 · you speak
  YOU.hi(A(4.0)); const yw = wave(YOU.n, 48, 392, 100, 22, null, INK, A(4.3), 1.6); tl.to(yw, { opacity: 0, duration: .4 }, A(7.0)); // under the box, clear of the Timbre arrow at x=165; gone once the audio reaches Prisma
  packet('🎙️', [[300, 285], [380, 285]], 4.3, 6.2, .9, 7.3);
  // 2 · Prisma: audio becomes text
  PRI.hi(A(7.1)); pop(g, '“10:27 కి alarm పెట్టు”', 540, 412, 30, 8.4, 12.0, { anchor: 'middle', cls: 'te', fill: RED });
  packet('📝', [[700, 285], [780, 285]], 8.6, 10.3, .8, 11.3);
  // 3 · guardrails pass it
  WRD.hi(A(11.1)); tick(WRD.n, 995, 248, A(12.4));
  packet('📝', [[915, 372], [915, 438]], 13.0, 14.6, .7, 15.5);
  // 4 · router picks the task
  RTR.hi(A(15.3)); const tk = T(RTR.n, 'alarm → workflow', 580, 578, 28, { fill: RED }); typeIn(tk, ['alarm → workflow'], A(17.0), .8); tl.to(tk, { opacity: 0, duration: .25 }, A(24.3));
  // 5 · handler -> phone
  packet('⚙️', [[600, 612], [588, 640], [470, 652], [352, 664]], 20.5, 20.9, 1.0, 22.0); HND.hi(A(21.8));
  packet('👆', [[340, 902], [340, 1016]], 22.3, 22.7, .8, 23.9); PHN.hi(A(23.5)); tick(PHN.n, 770, 1072, A(23.8));
  // 6 · agent loop: two read/pick/check/tap rounds with the phone
  const tk2 = T(RTR.n, 'Bluetooth on → agent', 580, 578, 28, { fill: RED }); typeIn(tk2, ['Bluetooth on → agent'], A(24.6), .9); tl.to(tk2, { opacity: 0, duration: .25 }, A(32.0));
  packet('📝', [[915, 612], [915, 668]], 25.2, 25.6, .5, 26.3); LOP.hi(A(26.0));
  [26.4, 29.4].forEach((c, k) => {
    steps.forEach((_, i) => { const w = wash(LOP.n, 605, 765 + i * 44 - 30, 410, 40, RED, .4, 4); bloom(w, A(c + i * .6)); tl.to(w, { opacity: 0, duration: .3 }, A(c + i * .6 + .55)); });
    packet('👆', [[700, 962], [700, 1018]], c + 1.8, c + 2.0, .45, c + 2.55); packet('📱', [[840, 1018], [840, 962]], c + 2.45, c + 2.5, .45, c + 3.0);
  });
  // 7 · result spoken back
  packet('✅', [[178, 1085], [110, 1085], [110, 612]], 32.2, 32.5, 1.2, 33.9); TIM.hi(A(33.6)); wave(TIM.n, 60, 575, 180, 24, null, GRN, A(33.8), 1.4);
  packet('🔊', [[165, 438], [165, 372]], 34.2, 34.5, .7, 35.4); YOU.hi(A(35.2), GRN, .4);
  pop(g, '“అయిపోయింది” (Done.)', 208, 414, 30, 34.6, 38.6, { cls: 'te', fill: GRN });
})();
// problem line (accessibility angle), between title and arch
(function pitch() {
  const s = TL.scenes.find(x => x.id === 'pitch'); if (!s) return;
  const a = s.start, g = sheet(stage), L = TL.pitch;
  tl.to(g, { opacity: 0, duration: .45 }, s.end - .45);
  const w = wash(g, 80, 380, 920, 480, BLU, .25, 16); bloom(w, a + .1);
  const top = T(g, L.slice(0, 3).join('\n'), 540, 500, 72, { anchor: 'middle', lh: 1.25 }); wordIn(top, L.slice(0, 3), a + .15, 1.3);
  const pay = T(g, L[3], 540, 800, 72, { anchor: 'middle', fill: RED }); tl.fromTo(pay, { opacity: 0 }, { opacity: 1, duration: .35 }, a + 1.8);
  draw(uline(g, pay, 800 + 72 * .3, 6), a + 2.3, .5);
})();
// title overlay 0 - 3.2
(function title() {
  const g = el('g', { opacity: 0, 'data-cover': 1 }), w = wash(g, -20, -20, 1120, 1390, '#f4efe6', 1, 0);
  const cover = el('rect', { width: 1080, height: 1350, fill: '#f4efe6' }, g); g.insertBefore(cover, g.firstChild);
  const ts = TL.claim.map((l, i) => T(g, l, 540, [500, 660, 750][i], i ? 60 : 170, { anchor: 'middle' })); // name big, tagline smaller
  const u = uline(g, ts[0], 500 + 170 * .3, 7); // under "Sugam" only, fitted to its width
  tl.fromTo(g, { opacity: 1 }, { opacity: 0, duration: .5 }, 2.7);
  draw(u, 1.0, .7);
})();

if (TL.mock) { const m = T(stage, 'MOCK DATA - not final', 1050, 1328, 30, { anchor: 'end', fill: RED }); }

window.seek = t => {
  if (!wrapped) { WRAPS.forEach(f => f()); wrapped = document.fonts.check('38px Brush'); }
  tl.time(t, false); fitUlines();
  document.getElementById('wt').setAttribute('seed', (Math.floor(t * 12) * 7919) % 997 + 1); // on twos at 24 fps
  updateTimer(t);
};
window.DURATION = TL.dur;
seek(0);
