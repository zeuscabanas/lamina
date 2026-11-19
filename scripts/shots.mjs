#!/usr/bin/env node
// Looks at a built page the way a reviewer would, in headless Chromium with WebGL: a shot of the top, one of every
// figure, a phone-width shot, and a check of every control (each pause button must hold the figure still, each
// slider must change something, each part button must select). Prints console errors. Read every PNG.
//
//   node scripts/shots.mjs out/colibri.html [--out out/shots]
//
// Set CHROMIUM to use a browser other than the one `npx playwright install chromium` downloaded.
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const {chromium} = createRequire(path.join(process.env.LAMINA_DEPS || path.join(HERE, '..', 'node_modules'), 'x.js'))('playwright');
const args = process.argv.slice(2);
const page_ = path.resolve(args[0]);
const oi = args.indexOf('--out');
const OUT = path.resolve(oi >= 0 ? args[oi + 1] : path.join(path.dirname(page_), 'shots'));
fs.mkdirSync(OUT, {recursive: true});
const b = await chromium.launch({executablePath: process.env.CHROMIUM || undefined, args: ['--ignore-gpu-blocklist', '--enable-webgl', '--enable-unsafe-swiftshader']});
const p = await b.newPage({viewport: {width: 1280, height: 950}});
const errs = [];
p.on('pageerror', (e) => errs.push(String(e)));
p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
await p.goto('file://' + page_);
await p.waitForFunction(() => window.PAGE, null, {timeout: 60000});
await p.waitForTimeout(3000);
await p.screenshot({path: path.join(OUT, 'top.png')});
const n = await p.locator('.fig').count();
let bad = 0;
const fail = (m) => (bad++, console.log('FAIL', m));
for (let i = 0; i < n; i++) {
  const f = p.locator('.fig').nth(i);
  await f.scrollIntoViewIfNeeded();
  await p.waitForTimeout(2500);
  await f.screenshot({path: path.join(OUT, `fig${i + 1}.png`)});
  const phase = () => p.evaluate((k) => PAGE.figs[k].phase, i);
  const pp = f.locator('[data-pp]');
  if (await pp.count()) {
    const before = await phase();
    await p.waitForTimeout(500);
    if ((await phase()) === before) fail(`fig ${i + 1}: not moving before pause`);
    await pp.click();
    const a = await phase();
    await p.waitForTimeout(700);
    if ((await phase()) !== a) fail(`fig ${i + 1}: pause does not hold`);
    await pp.click();
  }
  for (const r of await f.locator('input[type=range]').all()) {
    const out0 = await f.locator('.ctl').innerText();
    const [lo, hi] = [Number(await r.getAttribute('min')), Number(await r.getAttribute('max'))];
    const v0 = await r.inputValue();
    await r.fill(String(Number(v0) > (lo + hi) / 2 ? lo : hi));
    await p.waitForTimeout(500);
    if ((await f.locator('.ctl').innerText()) === out0) fail(`fig ${i + 1}: a slider changes nothing`);
    await r.fill(v0);
  }
  const parts = f.locator('[data-part]');
  if (await parts.count()) {
    await parts.nth(Math.floor((await parts.count()) / 2)).click();
    await p.waitForTimeout(2000);
    if ((await p.evaluate((k) => PAGE.figs[k].sel, i)) < 0) fail(`fig ${i + 1}: part button does not select`);
    await f.screenshot({path: path.join(OUT, `fig${i + 1}-part.png`)});
    await parts.nth(Math.floor((await parts.count()) / 2)).click();
  }
}
await p.setViewportSize({width: 390, height: 800});
await p.locator('.fig').first().scrollIntoViewIfNeeded();
await p.waitForTimeout(2500);
await p.screenshot({path: path.join(OUT, 'phone.png')});
if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) fail('the page scrolls sideways at 390 px');
for (const e of errs) fail('console: ' + e);
console.log(`${n} figures · shots in ${OUT}`);
console.log(bad ? `checks failed: ${bad}` : 'checks passed');
await b.close();
process.exit(bad ? 1 : 0);
