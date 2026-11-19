// lamina · the page. An explained page the Anatomy way, in 3D: a short text, then figures. Each figure is a framed card
// ("Fig n" and a title on top, a hint and a live readout at the bottom), a caption under it and one or two real
// controls. Every figure shows the same audited model (blender/tdb.py → .glb → kit/rig.js) through ONE WebGL renderer:
// each visible card is posed, rendered and copied to its own 2D canvas, so six figures cost one context. Dark theme,
// white and gold model, gold as the only accent.
//
//   const P = await createPage({title, model, onState});     // model: {root, meshes, update(state)}
//   P.header({...}); P.lead('…'); P.h2('01 — …', '…'); P.figure({...}); P.caption('…'); P.start();
//
// model.update(state) receives what the figure's step() returns. state.look(part, asm) -> 'solid' | 'ghost' | 'hide'
// decides every mesh; meshes carry userData.part and userData.asm (kit/rig.js sets them).
import * as THREE from 'three';

export const C = {ink: '#ece8df', mute: '#8d8a83', faint: '#3a3b40', line: '#26272b', or: '#d4a94e', bg: '#0e0f11', card: '#15161a', text: '#bdb9b0'};
const MONO = "'JetBrains Mono',ui-monospace,monospace";
export const es = (v, d = 1) => v.toFixed(d).replace('.', ',');
export const sgn = (v, d = 1) => (v >= 0 ? '+' : '−') + es(Math.abs(v), d);
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const D2R = Math.PI / 180;

const CSS = `
html,body{background:${C.bg};overflow:auto!important;height:auto!important}
#app{position:static!important;inset:auto!important;font-family:Inter,system-ui,sans-serif;color:${C.ink};-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.pg{max-width:1040px;margin:0 auto;padding:0 28px 96px}
.m{font-family:${MONO};text-transform:uppercase;letter-spacing:1.3px}
.hd{display:flex;align-items:stretch;gap:22px;margin:0 -28px 54px;border-bottom:1px solid ${C.line}}
.hd .tag{background:${C.or};color:#14110a;display:flex;align-items:center;gap:12px;padding:26px 26px;font:700 17px ${MONO};letter-spacing:1px}
.hd .tt{padding:18px 0 16px}
.hd .k{font-size:10px;color:${C.mute}}
.hd h1{font-size:40px;line-height:1;margin:6px 0 8px;letter-spacing:-1.2px;font-weight:700}
.hd h1 i{color:${C.or};font-style:normal;font-weight:500}
.hd .s{font-size:10.5px}
.lead{font-size:21px;line-height:1.5;max-width:760px;margin:0 0 20px;letter-spacing:-.2px}
p.tx{font-size:16px;line-height:1.65;max-width:680px;margin:0 0 16px;color:${C.text}}
h2{font-size:26px;letter-spacing:-.5px;margin:70px 0 14px;font-weight:700}
h2 .n{font:600 11px ${MONO};color:${C.or};letter-spacing:1.5px;display:block;margin-bottom:8px}
.fig{margin:26px 0 12px}
.card{position:relative;border:1px solid ${C.line};background:radial-gradient(ellipse 62% 70% at 50% 48%,#3a3c42 0%,#24262b 45%,${C.card} 100%);overflow:hidden}
.card canvas{display:block;width:100%;touch-action:pan-y;cursor:grab}
.card canvas.drag{cursor:grabbing}
.card .bp{position:absolute;inset:0;pointer-events:none}
.card .c{position:absolute;font:600 10px ${MONO};letter-spacing:1.4px;text-transform:uppercase;pointer-events:none}
.card .tl{left:16px;top:14px;color:${C.or}}
.card .tr{right:16px;top:14px}
.card .bl{left:16px;bottom:13px;color:${C.mute};font-weight:500}
.card .br{right:16px;bottom:13px;text-align:right}
.ctl{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;padding:12px 14px;border:1px solid ${C.line};border-top:none;background:#121316}
.btn{height:30px;padding:0 13px;border:1px solid ${C.faint};background:#1a1b1f;font:600 10px ${MONO};letter-spacing:1.2px;text-transform:uppercase;color:${C.ink};cursor:pointer;display:inline-flex;align-items:center;gap:8px}
.btn:hover{border-color:${C.ink}}
.btn.on{background:${C.ink};color:#111;border-color:${C.ink}}
.btn.pp{background:${C.or};border-color:${C.or};color:#14110a;min-width:92px;justify-content:center}
.sl{display:flex;align-items:center;gap:10px;font:600 10px ${MONO};letter-spacing:1.2px;text-transform:uppercase;flex:1;min-width:240px}
.sl input{flex:1;accent-color:${C.or};height:22px;cursor:pointer}
.sl b{min-width:64px;text-align:right}
.pb{display:flex;flex-wrap:wrap;gap:6px;padding:12px 14px 4px;border:1px solid ${C.line};border-top:none;background:#121316}
.pb .btn{height:28px;padding:0 10px}
.pb .btn.on{background:${C.or};border-color:${C.or};color:#14110a}
.pd{padding:8px 14px 14px;border:1px solid ${C.line};border-top:none;background:#121316;font-size:14px;line-height:1.5;color:${C.text};min-height:44px}
.pd b{color:${C.ink}}
.cap{font-size:14px;line-height:1.55;color:${C.mute};max-width:680px;margin:12px 0 0}
.cap b{color:${C.ink}}
table.sp{border-collapse:collapse;width:100%;max-width:760px;margin-top:10px}
table.sp td{border-top:1px solid ${C.line};padding:9px 0;font-size:14px;vertical-align:top}
table.sp td:first-child{font:600 10px ${MONO};letter-spacing:1.3px;text-transform:uppercase;color:${C.mute};width:210px;padding-top:12px}
.chain{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px;font:600 10px ${MONO};letter-spacing:1.1px;text-transform:uppercase}
.chain span{border:1px solid ${C.faint};padding:6px 9px;background:#1a1b1f}
.chain i{font-style:normal;color:${C.or};align-self:center}
.ft{margin-top:80px;padding-top:16px;border-top:1px solid ${C.line};font:500 9.5px ${MONO};letter-spacing:1.3px;text-transform:uppercase;color:${C.mute};display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
@media (max-width:640px){.hd h1{font-size:30px}.lead{font-size:18px}.card .tr,.card .bl{display:none}.card .br{left:14px;right:14px;font-size:9px}}
`;
const BP = `<svg class="bp" viewBox="0 0 1000 580" preserveAspectRatio="xMidYMid slice"><g fill="none" stroke="#d9d4c8" stroke-width=".7"><circle cx="500" cy="285" r="120" opacity=".22"/><circle cx="500" cy="285" r="235" opacity=".2"/><circle cx="500" cy="285" r="350" opacity=".16"/><path d="M20 285H372M628 285H980M500 20V157M500 413V560" opacity=".16"/><path d="M262 47h10m-5-5v10M728 47h10m-5-5v10M262 523h10m-5-5v10M728 523h10m-5-5v10" opacity=".4"/></g></svg>`;


/** opts: title, model {root (THREE.Object3D, metres), meshes, update(state)}, slow (default playback divider, 40),
 *  onState(state, fig) called after model.update for extras that live in the scene */
export async function createPage({title, model, slow = 40, onState}) {
  const style = document.createElement('style');
  style.textContent = CSS;
  document.head.appendChild(style);
  document.title = title;
  const app = document.getElementById('app');

  // ------------------------------------------------------------ one renderer, one scene, one bird
  const gl = document.createElement('canvas');
  const renderer = new THREE.WebGLRenderer({canvas: gl, antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance'});
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;
  const scene = new THREE.Scene();
  {
    const env = new THREE.Scene();
    env.background = new THREE.Color('#5d5f66');
    const box = (w, h, pos, k, col = '#ffffff') => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({color: new THREE.Color(col).multiplyScalar(k), side: THREE.DoubleSide}));
      m.position.set(...pos);
      m.lookAt(0, 0, 0);
      env.add(m);
    };
    box(12, 12, [0, 14, 2], 2.4);
    box(3, 14, [-12, 4, 6], 3.0);
    box(3, 14, [12, 4, -4], 1.8);
    box(18, 2, [0, 2, 14], 1.4, '#fff3e6');
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromScene(env, 0.02).texture;
    pm.dispose();
  }
  const sun = new THREE.DirectionalLight('#fffaf3', 2.4);
  sun.position.set(-0.5, 2.2, 0.9);
  sun.castShadow = true;
  Object.assign(sun.shadow.camera, {left: -0.25, right: 0.25, top: 0.25, bottom: -0.25, near: 0.5, far: 5});
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 16;
  sun.shadow.blurSamples = 16;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.001;
  scene.add(sun, sun.target, new THREE.HemisphereLight('#ffffff', '#6a6d75', 0.9));
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.ShadowMaterial({color: '#000000', opacity: 0.45}));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);
  const camera = new THREE.PerspectiveCamera(24, 1000 / 580, 0.01, 20);
  scene.add(model.root);

  // ------------------------------------------------------------ the page
  const pg = document.createElement('div');
  pg.className = 'pg';
  app.appendChild(pg);
  const add = (html) => {
    const d = document.createElement('div');
    d.innerHTML = html.trim();
    const n = d.firstElementChild;
    pg.appendChild(n);
    return n;
  };
  const figs = [];
  /** def: {n, title, hint, cam: {az, el, d, ty, tz, tx} (degrees, metres), controls (html), extra (html under the controls), setup(fig),
   *  step(fig, dt) -> the state handed to model.update (plus autoTurn, focusRe), readout(fig, state) -> html} */
  const figure = (def) => {
    const el = add(`<div class="fig"><div class="card">${BP}<canvas></canvas><div class="c tl">Fig ${def.n}</div><div class="c tr">${def.title}</div><div class="c bl">${def.hint ?? 'Arrastra para girar'}</div><div class="c br"></div></div>${def.controls ? `<div class="ctl">${def.controls}</div>` : ''}${def.extra ?? ''}</div>`);
    const cv = el.querySelector('canvas');
    const f = {def, el, cv, ctx: cv.getContext('2d'), out: el.querySelector('.br'), phase: 0.9, playing: true, speed: 1 / slow, az: 0, elv: 0, zoom: 1, t: 0, vis: false, q: (s) => el.querySelector(s)};
    let drag = null;
    cv.addEventListener('pointerdown', (e) => {
      drag = {x: e.clientX, y: e.clientY};
      cv.setPointerCapture(e.pointerId);
      cv.classList.add('drag');
    });
    cv.addEventListener('pointermove', (e) => {
      if (!drag) return;
      f.az -= (e.clientX - drag.x) * 0.4;
      f.elv = clamp(f.elv + (e.clientY - drag.y) * 0.25, -40, 60);
      drag = {x: e.clientX, y: e.clientY};
    });
    let moved = 0;
    cv.addEventListener('pointerdown', () => (moved = 0));
    cv.addEventListener('pointermove', (e) => drag && (moved += Math.abs(e.movementX) + Math.abs(e.movementY)));
    const end = (e) => {
      if (drag && moved < 5 && f.onPick && e?.type === 'pointerup') {
        const r = cv.getBoundingClientRect();
        f.pick = [((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1];
      }
      drag = null;
      cv.classList.remove('drag');
    };
    cv.addEventListener('pointerup', end);
    cv.addEventListener('pointercancel', end);
    const pp = f.q('[data-pp]');
    const setPlay = (on) => {
      f.playing = on;
      if (pp) pp.textContent = on ? '❚❚ Pausa' : '▶ Reanudar';
    };
    f.setPlay = setPlay;
    if (pp) pp.addEventListener('click', () => setPlay(!f.playing));
    for (const b of el.querySelectorAll('[data-speed]'))
      b.addEventListener('click', () => {
        f.speed = Number(b.dataset.speed);
        for (const o of el.querySelectorAll('[data-speed]')) o.classList.toggle('on', o === b);
        setPlay(true);
      });
    def.setup?.(f);
    figs.push(f);
    return f;
  };
  const range = (id, label, min, max, val, step = 0.01) => `<label class="sl">${label}<input type="range" data-${id} min="${min}" max="${max}" step="${step}" value="${val}"><b data-${id}-v></b></label>`;
  const speeds = `<span class="btn" data-speed="${1 / 200}">1/200</span><span class="btn on" data-speed="${1 / slow}">1/${slow}</span><span class="btn" data-speed="${1 / 8}">1/8</span>`;
  /** advance a figure's phase: hz cycles a second, slowed by the figure's speed */
  const beat = (f, dt, hz) => {
    if (f.playing) f.phase += 2 * Math.PI * hz * dt * f.speed;
  };
  const solid = () => 'solid';

  // ---------------------------------------------------------------- text blocks
  const header = ({code, icon = '', kicker, name, sub}) => add(`<div class="hd"><div class="tag">${icon}${code}</div><div class="tt"><div class="m k">${kicker}</div><h1>${name} <i>/</i></h1><div class="m s">${sub}</div></div></div>`);
  const lead = (html) => add(`<p class="lead">${html}</p>`);
  const text = (html) => add(`<p class="tx">${html}</p>`);
  const h2 = (kicker, title) => add(`<h2><span class="n">${kicker}</span>${title}</h2>`);
  const caption = (html) => add(`<p class="cap">${html}</p>`);
  const chain = (steps) => add(`<div class="chain">${steps.map((s) => `<span>${s}</span>`).join('<i>→</i>')}</div>`);
  const table = (rows) => add(`<table class="sp">${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>`);
  const footer = (left, right) => add(`<div class="ft"><span>${left}</span><span>${right} <span style="color:${C.or}">//////</span></span></div>`);
  /** the named-parts panel for a figure. parts: [[name, /regex over part names/, one line]...]. Spread the result into
   *  the figure's def ({...partsPanel(PARTS)}); in step() use fig.sel (index or −1) and partLook(fig) / fig.focusRe. */
  const partsPanel = (parts, empty = 'Elige una pieza de la lista, o tócala en el dibujo, para verla sola: el resto queda transparente.') => ({
    extra: `<div class="pb">${parts.map(([n], i) => `<span class="btn" data-part="${i}">${n}</span>`).join('')}</div><div class="pd"></div>`,
    setup: (f) => {
      f.sel = -1;
      const show = () => {
        for (const b of f.el.querySelectorAll('[data-part]')) b.classList.toggle('on', Number(b.dataset.part) === f.sel);
        f.q('.pd').innerHTML = f.sel < 0 ? empty : `<b>${parts[f.sel][0]}.</b> ${parts[f.sel][2]}`;
        f.focusRe = f.sel >= 0 ? parts[f.sel][1] : null;
      };
      f.select = (i) => {
        f.sel = i === f.sel ? -1 : i;
        show();
      };
      for (const b of f.el.querySelectorAll('[data-part]')) b.addEventListener('click', () => f.select(Number(b.dataset.part)));
      f.onPick = (part) => f.select(part ? parts.findIndex(([, re]) => re.test(part)) : f.sel);
      show();
    },
  });
  /** the look for a figure with a parts panel: the selected part solid, the rest a ghost */
  const partLook = (f) => (f.focusRe ? (part) => (f.focusRe.test(part) ? 'solid' : 'ghost') : solid);

  // ------------------------------------------------------------ the loop: pose, render and copy each visible figure
  const start = () => {
  const io = new IntersectionObserver((es_) => es_.forEach((e) => (figs.find((f) => f.cv === e.target).vis = e.isIntersecting)), {rootMargin: '120px'});
  figs.forEach((f) => io.observe(f.cv));
  let W = 0;
  let H = 0;
  const size = () => {
    const w = Math.round(figs[0].cv.clientWidth);
    const h = Math.round(w * (w < 560 ? 0.8 : 0.58));
    const pr = Math.min(devicePixelRatio || 1, w < 560 ? 2 : 1.5);
    if (w === W && h === H) return;
    W = w;
    H = h;
    for (const f of figs) {
      f.cv.width = Math.round(w * pr);
      f.cv.height = Math.round(h * pr);
      f.cv.style.height = `${h}px`;
    }
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  size();
  addEventListener('resize', size);
  const ray = new THREE.Raycaster();
  const box = new THREE.Box3();
  const sph = new THREE.Sphere();
  let last = performance.now();
  const frame = (now) => {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    size();
    for (const f of figs) {
      if (!f.vis) continue;
      f.t += dt;
      const st = f.def.step(f, dt);
      model.update(st);
      onState?.(st, f);
      const c0 = f.def.cam;
      // a selected part pulls the camera to itself: its box's centre, and close enough to fill a third of the card
      const want = {tx: c0.tx ?? 0, ty: c0.ty, tz: c0.tz, d: c0.d};
      if (st.focusRe) {
        model.root.updateMatrixWorld(true);
        box.makeEmpty();
        for (const m of model.meshes) if (st.focusRe.test(m.userData.part)) box.expandByObject(m);
        if (!box.isEmpty()) {
          box.getBoundingSphere(sph);
          Object.assign(want, {tx: sph.center.x, ty: sph.center.y, tz: sph.center.z, d: clamp(sph.radius * 7, 0.09, c0.d)});
        }
      }
      f.camNow ??= {...want};
      const kc = 1 - Math.exp(-dt / 0.35);
      for (const key in want) f.camNow[key] += (want[key] - f.camNow[key]) * kc;
      const c = f.camNow;
      const az = (c0.az + f.az + (st.autoTurn ? Math.sin(f.t * 0.25) * st.autoTurn : 0)) * D2R;
      const el = clamp(c0.el + f.elv, -30, 80) * D2R;
      const d = c.d * (W < 560 ? 1.25 : 1);
      camera.position.set(c.tx + d * Math.cos(el) * Math.sin(az), c.ty + d * Math.sin(el), c.tz + d * Math.cos(el) * Math.cos(az));
      camera.lookAt(c.tx, c.ty, c.tz);
      renderer.render(scene, camera);
      f.ctx.clearRect(0, 0, f.cv.width, f.cv.height);
      f.ctx.drawImage(gl, 0, 0, f.cv.width, f.cv.height);
      if (f.pick) {
        // the model is still in this figure's pose: find the part under the pointer
        ray.setFromCamera(new THREE.Vector2(f.pick[0], f.pick[1]), camera);
        const hit = ray.intersectObjects(model.meshes.filter((m) => m.visible), false)[0];
        f.pick = null;
        f.onPick(hit ? hit.object.userData.part : null);
      }
      f.out.innerHTML = f.def.readout(f, st);
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  window.PAGE = {figs, model};
  };
  return {add, header, lead, text, h2, caption, chain, table, footer, figure, range, speeds, beat, solid, partsPanel, partLook, start, scene, camera, renderer, figs};
}
