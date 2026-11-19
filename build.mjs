#!/usr/bin/env node
// Bundles <folder>/main.js into one self-contained HTML page: out/<folder name>.html (three.js, the model's GLB and
// the fonts inlined). Opens from file://, works offline, can be published as it is.
//
//   node build.mjs examples/colibri          → out/colibri.html
//   node build.mjs ../my-machine --out dist  → dist/my-machine.html
//
// Inside a page, import the kit by name from anywhere: 'lamina-kit/page.js', 'lamina-kit/rig.js'.
// Derived from the build script of elvarofficial/teardown and whaleyxbt/claude-motion (MIT).
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEPS = process.env.LAMINA_DEPS || path.join(HERE, 'node_modules');
const esbuild = createRequire(path.join(DEPS, 'x.js'))('esbuild');
const args = process.argv.slice(2);
const oi = args.indexOf('--out');
const OUT = path.resolve(oi >= 0 ? args[oi + 1] : 'out');
const dirs = args.filter((a, i) => !a.startsWith('--') && i !== oi + 1 - (oi < 0 ? 1e9 : 0));
if (!dirs.length) {
  console.error('usage: node build.mjs <folder with main.js> [--out dir]');
  process.exit(1);
}
fs.mkdirSync(OUT, {recursive: true});
const b64 = (f) => fs.readFileSync(path.join(DEPS, f)).toString('base64');
const FONTS =
  [400, 600, 700].map((w) => `@font-face{font-family:'JetBrains Mono';font-weight:${w};font-style:normal;font-display:block;src:url(data:font/woff2;base64,${b64(`@fontsource/jetbrains-mono/files/jetbrains-mono-latin-${w}-normal.woff2`)}) format('woff2');}`).join('\n') +
  `\n@font-face{font-family:'Inter';font-weight:100 900;font-style:normal;font-display:block;src:url(data:font/woff2;base64,${b64('@fontsource-variable/inter/files/inter-latin-wght-normal.woff2')}) format('woff2');}`;
const kit = {
  name: 'lamina-kit',
  setup(b) {
    b.onResolve({filter: /^lamina-kit\//}, (a) => ({path: path.join(HERE, 'kit', a.path.slice('lamina-kit/'.length))}));
  },
};
for (const d of dirs) {
  const dir = path.resolve(d);
  const name = path.basename(dir);
  const t0 = Date.now();
  const res = await esbuild.build({
    plugins: [kit], entryPoints: [path.join(dir, 'main.js')], bundle: true, nodePaths: [DEPS], format: 'esm', minify: !process.env.LAMINA_DEBUG,
    write: false, target: 'es2022', legalComments: 'none', loader: {'.glb': 'base64'}, logLevel: 'warning',
  });
  const js = res.outputFiles[0].text.replace(/<\/script/g, '<\\/script');
  const html = `<!doctype html>
<html lang="${process.env.LAMINA_LANG || 'es'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${name}</title>
<style>
${FONTS}
*{box-sizing:border-box}
html,body{margin:0}
</style>
</head>
<body>
<div id="app"></div>
<script type="module">
${js}
</script>
</body>
</html>
`;
  const out = path.join(OUT, `${name}.html`);
  fs.writeFileSync(out, html);
  console.log(`${out}  ${(html.length / 1024).toFixed(0)} KB  ${Date.now() - t0} ms`);
}
