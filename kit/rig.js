// A model made in Blender with blender/tdb.py, loaded and posed. The GLB carries every part as a named node with its
// rig in the extras: the assembly it belongs to, its joint (the same law blender/audit.py sweeps), its explode and
// open vectors, and named anchors. pose(inputs, {explode, focus, open}) puts every part where the audit proved it fits.
//
//   import glb from './machine.glb';                       // the build inlines it as base64
//   const rig = await loadRig(glb, {shell: new THREE.MeshPhysicalMaterial(…), …});
//   scene.add(rig.root); rig.pose({phase: 1.2}, {explode: 0, focus: 'alas', open: 1});
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

/** value = k·q + a·sin(h·q + p) + c + b·tanh(g·cos q): the joint law, as in blender/audit.py */
export const lawValue = (law, q) => {
  let v = (law.k ?? 0) * q + (law.c ?? 0);
  if (law.sin) v += law.sin[0] * Math.sin(law.sin[1] * q + law.sin[2]);
  if (law.tanh) v += law.tanh[0] * Math.tanh(law.tanh[1] * Math.cos(q));
  return v;
};

const bytes = (b64) => {
  const s = atob(b64);
  const u = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
  return u.buffer;
};

export async function loadRig(glbBase64, materials = {}) {
  const gltf = await new Promise((res, rej) => new GLTFLoader().parse(bytes(glbBase64), '', res, rej));
  const root = gltf.scene;
  const nodes = {}; // name -> {node, td, rest: {p, q}}
  const anchors = {};
  const meshes = [];
  let rig = {inputs: {}};
  const q = new THREE.Quaternion();
  const ax = new THREE.Vector3();
  root.traverse((n) => {
    const raw = n.userData?.td;
    if (!raw) return;
    const td = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (td.rig) rig = td.rig;
    if (td.anchor) {
      anchors[td.anchor] = n;
      return;
    }
    nodes[n.name] = {node: n, td, rest: {p: n.position.clone(), q: n.quaternion.clone()}};
  });
  // every mesh knows its part and its assembly (its own or the nearest ancestor's)
  root.traverse((m) => {
    if (!m.isMesh) return;
    let p = m;
    let part = null;
    let asm = null;
    while (p) {
      const e = nodes[p.name];
      if (e && e.node === p) {
        part ??= p.name;
        asm ??= e.td.asm ?? null;
      }
      p = p.parent;
    }
    const mat = materials[m.material?.name] ?? m.material;
    m.material = mat;
    m.userData.mat = mat;
    m.userData.part = part;
    m.userData.asm = asm ?? 'general';
    m.castShadow = true;
    m.receiveShadow = true;
    meshes.push(m);
  });
  const rest = Object.fromEntries(Object.entries(rig.inputs).map(([k, v]) => [k, v.rest]));

  /** pose one entry from the inputs: its joint, then the exploded view and the opening of its assembly */
  const poseNode = (e, inputs, o) => {
    const {node, td} = e;
    node.position.copy(e.rest.p);
    node.quaternion.copy(e.rest.q);
    const j = td.joint;
    if (j) {
      const v = lawValue(j.law, inputs[j.input] ?? rest[j.input] ?? 0);
      ax.set(j.axis[0], j.axis[1], j.axis[2]);
      if (j.kind === 'rev') node.quaternion.multiply(q.setFromAxisAngle(ax, v));
      else node.position.addScaledVector(ax.applyQuaternion(e.rest.q), v);
    }
    if (o.explode && td.explode) node.position.addScaledVector(ax.set(td.explode[0], td.explode[1], td.explode[2]), o.explode);
    if (o.open && td.open && (Array.isArray(o.focus) ? o.focus.includes(td.asm) : td.asm === o.focus)) node.position.addScaledVector(ax.set(td.open[0], td.open[1], td.open[2]), o.open);
  };
  const pose = (inputs = {}, o = {}) => {
    for (const k in nodes) poseNode(nodes[k], inputs, o);
  };
  /** a copy of a jointed subtree (a wing for motion blur) that poses on its own inputs; keep(mesh) filters its meshes */
  const ghost = (name, material, keep = () => true) => {
    const src = nodes[name].node;
    const copy = src.clone(true);
    const own = [];
    const drop = [];
    copy.traverse((n) => {
      if (n.isMesh) {
        if (keep(n)) {
          n.material = material;
          n.castShadow = false;
          n.receiveShadow = false;
        } else drop.push(n);
      }
      const e = nodes[n.name];
      if (e) own.push({node: n, td: e.td, rest: e.rest});
    });
    for (const d of drop) d.parent.remove(d);
    src.parent.add(copy);
    return {node: copy, pose: (inputs, o = {}) => own.forEach((e) => poseNode(e, inputs, o))};
  };
  pose(rest);
  return {root, nodes, anchors, meshes, rig, rest, pose, ghost};
}
