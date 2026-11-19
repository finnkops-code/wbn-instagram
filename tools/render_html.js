// node tools/render_html.js <html> <out.png> [selector]  -> element screenshot at 2x
const { chromium } = require('playwright');
(async () => {
  const [, , html, out, sel] = process.argv;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 700, height: 1600 }, deviceScaleFactor: 2 });
  await p.goto('file://' + require('path').resolve(html));
  await p.waitForLoadState('networkidle');
  const el = await p.$(sel || 'body');
  await el.screenshot({ path: out, omitBackground: true });
  const box = await p.$eval('#adslot', e => { const r = e.getBoundingClientRect(); return [r.top, r.height]; }).catch(() => null);
  console.log(JSON.stringify({ adslot: box }));
  await b.close();
})();
