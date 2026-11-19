---
name: lamina
description: Explain how a machine or mechanism works as a dark, explained web page of live 3D figures ("láminas"): a short text, then framed cards showing the same model whole, opened, its mechanism alone, its motion and its exploded view, each with one or two controls and named parts you can select while the rest fades. The model is built in Blender from code as real closed parts and audited so nothing passes through anything. Use when someone asks how something works, wants an explained page, a "lámina", an interactive 3D explainer, a cutaway or an exploded view of a machine, robot, tool, instrument or mechanism.
license: MIT
compatibility: Written for Claude Code. Needs Node.js 20+, Blender 4.2+ (or `pip install bpy`), and Chromium for the checks.
---

# lamina

One machine, one model, one page. The reader scrolls a short explanation and meets the machine several times: whole,
open, its mechanism alone, moving, apart. Every figure is the same audited 3D model, so nothing on the page can
disagree with anything else on it.

`SKILL_DIR` is the folder this file is in. `examples/colibri/` is a complete page (a 12 g robotic hummingbird, 44
parts, six figures): read it before you start and copy its structure.

```
cd "$SKILL_DIR" && npm install && npx playwright install chromium     # once
python examples/colibri/model.py --audit                              # model → colibri.glb, must print `audit passed`
node build.mjs examples/colibri                                       # → out/colibri.html, one offline file
node scripts/shots.mjs out/colibri.html                               # shots of every figure + control checks
```

With Blender instead of the `bpy` module: `blender -b -P examples/colibri/model.py -- --audit`.

## Workflow

Work in this order. Most of the quality is decided in steps 1 to 3, before any mesh.

1. **Truth first.** Collect the real numbers: sizes, masses, speeds, tooth counts, ratios, limits. Search for them.
   Put them in a small pure module (`kin.js`) and say in the page where they come from. Invented parts get invented
   names: a fictional product with a model code, never a real brand.
2. **One input.** Name the single variable that drives the machine (a crank angle, a stroke, a valve position).
   Every pose and every readout is a function of it.
3. **Parts list and layout, on paper.** 40+ parts grouped by assembly, each with what it sits on. Lay the mechanism
   out with numbers before modelling: gear centres at (z1 + z2)·m / 2, shaft positions, what has to clear what, where
   every shaft crosses a shell. Write the list at the top of `model.py`.
4. **Model in Blender** with `blender/tdb.py` (see "Modelling").
5. **Audit to zero.** `python model.py --audit` until it prints `audit passed`.
6. **Write the page** with `kit/page.js` (see "The page"): 4 to 7 figures, each answering one question.
7. **Look at it.** `node scripts/shots.mjs out/<name>.html` must print `checks passed`. Then read every PNG it wrote.
   Fix and repeat until a full pass finds nothing.

Show the user one figure early (the whole machine, built and shot) before writing the rest of the page.

## Modelling

Anything with a curved body, a shell over a mechanism, or parts that move past each other is modelled in Blender, not
typed as three.js primitives. Primitives placed by eye are how parts end up poking through each other.

- **A body is an analytic surface, never a sphere or a lathe standing in for it.** Define control sections, join them
  with `spline`, and cut the surface into panels with `patch(surf, u0, u1, v0, v1, thick=0.7)`: real thickness, real
  gaps where you leave parameter ranges out, a bevel on every edge.
- **`part(name, bmesh, mat, asm, bevel, cut, explode, open, mats)`** registers one closed part in its parent's frame.
  `cut=[…]` subtracts with exact booleans: a hole for every shaft, leg, eye or cable that crosses a shell.
  `carve()` cuts a piece before it is welded into a part.
- **One welded structure is one part** (`join`): keel, ring frames, plates, posts, bosses. Bolts, hatches and vents
  are fused onto the panel they belong to. The audit is between parts, so decide deliberately what a part is.
- **Motion:** `joint(part, 'rev' | 'slide', axis, law, input)` with `value = k·q + a·sin(h·q + p) + c + b·tanh(g·cos q)`.
  `rig_input(name, lo, hi, samples, rest)` declares what the audit sweeps. `mate(a, b, depth)` declares teeth in
  mesh; `gear_info(...)` declares gears and racks; `frame(...)` is an empty that carries a joint; `anchor(name, at)`
  is a named point.
- **Contacts are flush (0.05 mm gap), tangent, or rim-on-surface.** Nothing is sunk into anything. A part that floats
  is a bug: give it a bracket.
- **Materials are names** (`shell`, `orange` = the accent, `ink`, `dark`, `steel`, `brass`, `carbon`, `lens`,
  `membrane`, `pcb`); the page gives them their look. `mats={'orange': predicate}` paints a region of a part.

### The audit

`blender/audit.py` poses the model through every input with the same joint laws the page uses and proves on the real
meshes:

| Check | Meaning |
|---|---|
| interference | No two parts pass through each other at rest, at every sampled pose, or exploded. A declared mate may overlap up to its depth. |
| support | Every part touches another and all of them hang together as one assembly. |
| gears | Centre distance (z1 + z2)·m / 2, inverse speed ratio, rack travel = pinion angle × pitch radius. |
| closed | Every part is a closed volume; a sheet has thickness. |

Each failure names the pair, the pose, the depth and the point. **Fix the geometry**: move it, shrink it, cut a hole,
change the layout, reduce a stroke. Never widen a mate, delete a part, or skip a pose to silence it. If the audit
shows that the real numbers do not fit, the numbers on the page change too. If you cannot run it (no Blender, no
`bpy`), say so and do not call the model finished.

## The page

`kit/rig.js` loads the GLB and poses it: `rig.pose(inputs, {explode, focus, open})`. `kit/page.js` is the page:

```js
import {createPage} from 'lamina-kit/page.js';
const P = await createPage({title, model});          // model: {root, meshes, update(state)}
P.header({code, kicker, name, sub}); P.lead('…'); P.h2('01 — El conjunto', '…'); P.text('…');
P.figure({n: 1, title, cam: {az, el, d, ty, tz}, controls, step: (fig, dt) => state, readout: (fig, state) => html});
P.caption('<b>Fig 1.</b> …'); P.chain([...]); P.table([...]); P.footer(left, right); P.start();
```

- **One renderer for every figure.** Each visible card is posed, rendered and copied to its own canvas. Never one
  WebGL context per figure.
- A figure's `step` returns the state for `model.update`. `state.look(part, asm)` returns `'solid'`, `'ghost'` or
  `'hide'` for every mesh: that is how one model becomes the whole machine, the open machine and the mechanism alone.
- **Controls are few and real:** at most a pause, three speeds and one slider per figure (`P.range`, `P.speeds`,
  `data-pp`). Native inputs only. No consoles, dashboards, timelines or status panels.
- **Named parts:** `...P.partsPanel(PARTS)` adds a button per part with one line about it; selecting one (or
  clicking it in the figure) ghosts the rest and brings the camera to it. `PARTS` is `[name, /regex/, line]`.
- **The figures to consider**, in this order: the whole machine working · the inside (a slider lifts the shell) · the
  mechanism alone, slow, with a phase you can scrub · the motion that matters, traced · a compensation or a limit · the
  exploded view with the named parts. Then a table of the numbers.

### Writing

Spanish by default (match the user's language). Short. A lead of two sentences, then per figure: a heading, two or
three sentences that say what to look at and why it is so, the figure, and a caption with one fact. Every number in
the text comes from the model. Say what is fictional and where the real figures come from.

## Look

Dark, always. Page `#0e0f11`, text `#ece8df`, one accent: gold `#d4a94e`. Each card has a soft pool of light behind
the model so dark parts keep an outline. The model is **white and gold**: glossy white shells, gold for what the
`orange` material marks, graphite and steel underneath. Inter for text, JetBrains Mono in small caps for labels,
numbers and buttons.

Dark parts on a dark page lose their edges. Keep black for a few parts; make internal mechanics steel, aluminium or
brass, and check each selected part against the background in `fig*-part.png`.

## Review

You cannot watch the page; you can read frames. `scripts/shots.mjs` writes `top.png`, `figN.png`, `figN-part.png` and
`phone.png`, presses every pause, moves every slider, selects a part and reports console errors. Then look:

- **The model.** `audit passed` on the current file. It reads as the real thing at a glance; no bare face at 4×.
- **Each figure.** One subject, filling half the card, not clipped; its shadow inside the card; the readout true.
- **Each control.** It changes what the caption says it changes.
- **The text.** Every number matches the readouts and the table.
- **Phone.** One column at 390 px, nothing scrolling sideways.

Say what you could not check (a real GPU's frame rate, for one).

## Credits

lamina unifies ideas from [teardown](https://github.com/elvarofficial/teardown) (elvarofficial),
[anatomy](https://github.com/wheresryan22/anatomy) (Ryan) and
[claude-motion](https://github.com/whaleyxbt/claude-motion) (whaleyxbt), all MIT. See `CREDITS.md`.
