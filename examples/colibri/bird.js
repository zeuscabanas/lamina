// Calypte HM-4: the bird on the page. The geometry comes from model.py (Blender, via blender/tdb.py) as colibri.glb:
// 44 named parts with their joints, assemblies and explode vectors in the file, audited for interference, support and
// gear geometry (blender/audit.py). This module only gives them their materials and poses them (kit/rig.js).
import * as THREE from 'three';
import {loadRig} from 'lamina-kit/rig.js';
import glb from './colibri.glb';
import {B, D2R} from './kin.js';

export const ORANGE = '#d4a94e'; // the accent: brushed gold
export const ASSEMBLIES = ['general', 'cabeza', 'alas', 'transmision', 'cola', 'bateria'];
const FRAME = 'bastidor'; // the airframe: stays solid while the drive, the battery or the tail is inspected

export async function buildBird() {
  const M = {
    shell: new THREE.MeshPhysicalMaterial({color: '#f3f1ee', roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.12, envMapIntensity: 0.85}),
    orange: new THREE.MeshPhysicalMaterial({color: '#e0b04a', roughness: 0.3, metalness: 1, clearcoat: 0.4, clearcoatRoughness: 0.25, envMapIntensity: 1.25}),
    ink: new THREE.MeshStandardMaterial({color: '#34373d', roughness: 0.42, metalness: 0.55, envMapIntensity: 1.3}),
    dark: new THREE.MeshStandardMaterial({color: '#4a4e55', roughness: 0.45, metalness: 0.6, envMapIntensity: 1.2}),
    steel: new THREE.MeshStandardMaterial({color: '#9a9ea4', roughness: 0.35, metalness: 0.85, envMapIntensity: 0.9}),
    brass: new THREE.MeshStandardMaterial({color: '#c9a24a', roughness: 0.32, metalness: 1, envMapIntensity: 1.2}),
    carbon: new THREE.MeshStandardMaterial({color: '#2c2e33', roughness: 0.35, metalness: 0.5, envMapIntensity: 1.3}),
    lens: new THREE.MeshPhysicalMaterial({color: '#0d0f12', roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.2}),
    membrane: new THREE.MeshPhysicalMaterial({color: '#f0ebe1', roughness: 0.35, transparent: true, opacity: 0.72, side: THREE.DoubleSide, depthWrite: false, envMapIntensity: 0.6}),
    pcb: new THREE.MeshStandardMaterial({color: '#2f3a36', roughness: 0.55, metalness: 0.3, envMapIntensity: 1.2}),
  };
  const ghostMat = new THREE.MeshBasicMaterial({color: '#cfd2d8', transparent: true, opacity: 0.09, depthWrite: false});
  const blurMat = new THREE.MeshBasicMaterial({color: '#f0ebe1', transparent: true, opacity: 0.07, depthWrite: false, side: THREE.DoubleSide});
  const rig = await loadRig(glb, M);
  const root = new THREE.Group();
  root.scale.setScalar(0.001);
  const body = new THREE.Group();
  root.add(body);
  body.add(rig.root);
  // motion blur: three trailing copies of each wing (its frame and membrane only), posed a little earlier in the beat
  const GHOSTS = ['L', 'R'].flatMap((sd) => Array.from({length: 3}, () => rig.ghost(`wingshaft_${sd}`, blurMat, (m) => m.userData.asm === 'alas' && /^wing(frame|mem)/.test(m.userData.part))));

  /** st: {phase, f, pitch (deg), roll, alt (mm), focus, open 0..1, isolate 0..1, explode 0..1, blur, blurDt, spread 0..1} */
  const update = (st) => {
    const pitch = st.pitch ?? B.bodyPitch;
    body.rotation.set(-pitch * D2R, 0, (st.roll ?? 0) * D2R, 'YXZ');
    body.position.set(0, st.alt ?? 150, 0);
    const ex = st.explode ?? 0;
    const o = {explode: ex, focus: st.openAsm ?? st.focus, open: (st.open ?? 0) * (1 - ex)};
    // the head stays level: its joint takes the body's pitch
    const inputs = {phase: st.phase, head: pitch * D2R, spread: st.spread ?? 0.5};
    rig.pose(inputs, o);
    const ghosting = st.focus && st.focus !== 'general' && (st.isolate ?? 0) > 0.5;
    const showBlur = (st.blur ?? 1) > 0.02 && ex < 0.3 && !(ghosting && st.focus !== 'alas') && (!st.look || st.look('wingmem_L', 'alas') === 'solid');
    const step = (st.blurDt ?? 0.0016) * 2 * Math.PI * (st.f ?? B.f0);
    GHOSTS.forEach((g, i) => {
      g.node.visible = showBlur;
      if (showBlur) g.pose({...inputs, phase: st.phase - step * ((i % 3) + 1)}, o);
    });
    // st.look(part, asm) -> 'solid' | 'ghost' | 'hide' decides every mesh when given (the page's figures)
    if (st.look) {
      for (const m of rig.meshes) {
        const l = st.look(m.userData.part, m.userData.asm);
        m.visible = l !== 'hide';
        m.material = l === 'ghost' ? ghostMat : m.userData.mat;
        m.castShadow = l === 'solid';
      }
      return;
    }
    for (const m of rig.meshes) {
      m.visible = true;
      m.castShadow = true;
      const a = m.userData.asm;
      const keep = !ghosting || a === st.focus || (a === FRAME && st.focus !== 'alas' && st.focus !== 'cabeza');
      m.material = keep ? m.userData.mat : ghostMat;
    }
  };
  const A = rig.anchors;
  const anchors = {...A, eye: A.eyeL, motor: A.motorL, crank: A.crankL, rack: A.rackL};
  return {root, body, update, anchors, M, meshes: rig.meshes, rig};
}
