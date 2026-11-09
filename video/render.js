// usage: node render.js [from] [to] [step]   (24 fps frames -> out/fNNNNN.png)
// mock page by default; REAL=1 renders transparent hole for the phone recording.
const puppeteer = require('puppeteer-core'), fs = require('fs'), path = require('path');
(async () => {
  const [from = 0, to = 1403, step = 1] = process.argv.slice(2).map(Number);
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--allow-file-access-from-files'] });
  const p = await b.newPage();
  p.on('console', m => console.log('page:', m.text())); p.on('pageerror', e => console.log('pageerror:', e.message));
  await p.setViewport({ width: 1080, height: 1350 });
  await p.goto('file://' + path.join(__dirname, 'index.html'));
  await p.evaluate(() => document.fonts.ready);
  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  const t0 = Date.now();
  for (let i = from; i <= to; i += step) {
    await p.evaluate(t => seek(t), i / 24);
    await p.screenshot({ path: path.join(__dirname, 'out', `f${String(i).padStart(5, '0')}.png`), omitBackground: true });
  }
  console.log(`frames ${from}..${to} step ${step}: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  await b.close();
})();
