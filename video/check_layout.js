// usage: node check_layout.js [step=0.25]   Seeks the whole timeline and reports, for every visible text:
// outside its [data-box] card (6 px margin), overlapping another text, or off-canvas. Exit 1 on any problem.
const puppeteer = require('puppeteer-core'), path = require('path');
(async () => {
  const step = Number(process.argv[2] || .25);
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--allow-file-access-from-files'] });
  const p = await b.newPage(); const errs = [];
  p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await p.setViewport({ width: 1080, height: 1350 });
  await p.goto('file://' + path.join(__dirname, 'index.html')); await p.evaluate(() => document.fonts.ready);
  const res = await p.evaluate(step => {
    const op = e => { let o = 1; for (; e && e.tagName !== 'svg'; e = e.parentNode) o *= parseFloat(getComputedStyle(e).opacity); return o; };
    const box = e => { for (; e && e.tagName !== 'svg'; e = e.parentNode) if (e.getAttribute && e.getAttribute('data-box')) return e; return null; };
    const inter = (a, c) => Math.max(0, Math.min(a.right, c.right) - Math.max(a.left, c.left)) * Math.max(0, Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top));
    const out = {}, add = (k, t) => { if (!(k in out)) out[k] = t.toFixed(2); };
    const texts = [...document.querySelectorAll('text')].filter(t => !t.classList.contains('emo')), covers = [...document.querySelectorAll('[data-cover]')];
    // hidden under a later, visible opaque sheet (title / arch / outro)?
    const under = e => covers.some(c => op(c) > .95 && !c.contains(e) && (e.compareDocumentPosition(c) & Node.DOCUMENT_POSITION_FOLLOWING));
    // glyph-ish rect: drop the font's extra ascent/descent so neighbouring lines don't false-alarm
    const rect = e => { const r = e.getBoundingClientRect(), f = +e.getAttribute('font-size') || 30; return { left: r.left, right: r.right, top: r.top + .15 * f, bottom: r.bottom - .1 * f, width: r.width, height: r.height - .25 * f }; };
    for (let t = 0; t <= window.DURATION; t += step) {
      seek(t);
      const vis = texts.filter(e => e.textContent.trim() && op(e) > .5 && !under(e)).map(e => ({ e, r: rect(e), bx: box(e), s: e.textContent.trim().slice(0, 40) }));
      for (const v of vis) {
        if (v.r.left < 2 || v.r.right > 1078 || v.r.top < 2 || v.r.bottom > 1348) add(`OFF-CANVAS "${v.s}" ${[v.r.left, v.r.top, v.r.right, v.r.bottom].map(Math.round)}`, t);
        if (v.bx) { const [x, y, w, h] = v.bx.getAttribute('data-box').split(' ').map(Number), m = 6;
          if (v.r.left < x + m || v.r.right > x + w - m || v.r.top < y + 2 || v.r.bottom > y + h - m) add(`OUT-OF-BOX "${v.s}" text ${[v.r.left, v.r.top, v.r.right, v.r.bottom].map(Math.round)} box ${[x, y, x + w, y + h]}`, t); }
      }
      for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
        const A = vis[i], B = vis[j], ov = inter(A.r, B.r), mn = Math.min(A.r.width * A.r.height, B.r.width * B.r.height);
        if (ov > 40 && ov > .04 * mn) add(`OVERLAP "${A.s}" x "${B.s}" (${Math.round(ov)} px²)`, t);
      }
    }
    return out;
  }, step);
  const keys = Object.keys(res);
  keys.sort((a, c) => res[a] - res[c]).forEach(k => console.log(`t=${res[k]}  ${k}`));
  errs.forEach(e => console.log('PAGE ERROR', e));
  console.log(keys.length || errs.length ? `${keys.length} layout problems, ${errs.length} page errors` : 'layout OK: no text outside its box, no overlaps, no page errors');
  await b.close(); process.exit(keys.length || errs.length ? 1 : 0);
})();
