# Credits

lamina is a unification and a set of experiments. The ideas that make it work belong to the projects below; the
merit is theirs.

## Built on

| Project | Author | Licence | What comes from it |
|---|---|---|---|
| [teardown](https://github.com/elvarofficial/teardown) | elvarofficial | MIT | The starting point: one machine as an interactive 3D page that can be taken apart, real numbers from one source, one input driving everything, the single-file build (`build.mjs` derives from its build script), isolating an assembly and ghosting the rest, the exploded view. |
| [anatomy](https://github.com/wheresryan22/anatomy) | Ryan (wheresryan22) | MIT | The page format and the method: an explained page of framed figures ("Fig n", title, hint, live readout, caption), the parts list before any geometry, every part sitting on another, contacts flush or tangent, named parts you select while the rest fades, and above all an audit that must reach zero at rest, apart and in motion. No anatomy code is included: its kit draws isometric SVG and this one renders 3D meshes. |
| [claude-motion](https://github.com/whaleyxbt/claude-motion) | whaleyxbt | MIT | teardown's own base (runtime, capture, review rules), and so the root of the review loop used here: you cannot watch the page, you can read frames. |

## Tools and libraries

| | Licence | Use |
|---|---|---|
| [Blender](https://www.blender.org/) and its `bpy` module | GPL (a tool, not distributed here) | Modelling: meshes, exact booleans, bevels, the glTF exporter, the BVH trees the audit uses. |
| [three.js](https://threejs.org/) | MIT | Rendering the figures. Inlined into the built page. |
| [esbuild](https://esbuild.github.io/) | MIT | Bundling the page. |
| [Playwright](https://playwright.dev/) | Apache-2.0 | The headless browser behind `scripts/shots.mjs`. |
| [Inter](https://rsms.me/inter/) | SIL OFL 1.1 | Text. Inlined into the built page. |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | SIL OFL 1.1 | Labels and readouts. Inlined into the built page. |

## The example

The hummingbird's mass (12 g) and maximum lift (27 g) are those published for Purdue University's hummingbird robot
(Bio-Robotics Lab, Xinyan Deng). Everything else about the Calypte HM-4 is this example's own design; it is a
fictional product.

## How it was made

Written in conversation with Claude (Anthropic), by César Cabanas.
