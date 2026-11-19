// Calypte HM-4, the explained page: six figures of one audited model (model.py → colibri.glb). The text and every
// figure's state are here; the page, the cards, the renderer and the parts panel are kit/page.js.
import * as THREE from 'three';
import {C, createPage, es, sgn} from 'lamina-kit/page.js';
import {buildBird} from './bird.js';
import {AMP, B, D2R, liftAt, motorRpm, WEIGHT, wingAt} from './kin.js';

const ALT = 70; // mm above the floor: close enough for the shadow to sit in the card
const SHELL = /^(top_|bot_|crown|face)/;
// the named parts: a button each; selecting one leaves the rest as a faint ghost
const PARTS = [
  ['Carcasa', /^(top_|bot_)/, '12 paneles de 0,7 mm sobre el bastidor. Los del lomo y la panza se quitan para llegar al interior.'],
  ['Bastidor', /^airframe$/, 'Una sola pieza: quilla, cinco cuadernas, soporte del cuello, puente de los ejes, patas y eje de la cola.'],
  ['Motores', /^motor_/, 'Dos motores sin núcleo de Ø6 mm, uno por ala. Giran a 24.480 rpm en vuelo estacionario.'],
  ['Reductora', /^(mpinion_|compound_)/, 'Piñón de 8 dientes y rueda doble de 32 y 10: con la corona de la manivela reducen 12 veces.'],
  ['Manivela', /^crank_/, 'Corona de 30 dientes con un disco y un pasador a 2,5 mm del centro. Da una vuelta por batido.'],
  ['Yugo y cremallera', /^yoke_/, 'El pasador corre por la ranura y empuja el yugo ±2,5 mm. La cremallera va en su borde superior.'],
  ['Eje del ala', /^wingshaft_/, 'Piñón de 15 dientes, eje y horquilla. Convierte el vaivén de la cremallera en ±63,7° de giro.'],
  ['Alas', /^wing(frame|mem)_/, 'Varilla de carbono de 76 mm, siete nervios y una membrana. La raíz es una bola que deja girar el ala.'],
  ['Batería', /^battery$/, 'LiPo de una celda y 120 mAh. Es la pieza más pesada y va en la panza, bajo la quilla.'],
  ['Placa de control', /^pcb$/, 'Controlador de vuelo con el sensor de inercia. Ajusta cada motor 2.000 veces por segundo.'],
  ['Cabeza', /^(crown|face|head_base)$/, 'Dos medias carcasas sobre un soporte que gira en el barril del cuello y se mantiene horizontal.'],
  ['Ojos', /^eye_/, 'Dos cámaras de 4 mm en sus alojamientos, con aro dorado. Miran hacia los lados y al frente.'],
  ['Pico', /^beak$/, 'Sonda de 36 mm con la punta dorada. Encaja en el frente de la cabeza.'],
  ['Cola', /^feather_/, 'Siete plumas apiladas en un mismo pasador, como un abanico. Se abre para frenar y se cierra al avanzar.'],
];

export async function runPage() {
  const bird = await buildBird();
  // every figure flies at the same height and tail spread unless its state says otherwise
  const model = {root: bird.root, meshes: bird.meshes, update: (st) => bird.update({alt: ALT, spread: 0.5, ...st})};
  // the wing tips' path over one beat, in the body's frame: the figure of eight
  const traces = ['L', 'R'].map((sd, k) => {
    const pts = [];
    const tip = new THREE.Vector3();
    for (let i = 0; i <= 120; i++) {
      bird.update({phase: (i / 120) * 2 * Math.PI, blur: 0, alt: ALT});
      bird.root.updateMatrixWorld(true);
      bird.rig.nodes[`wrot_${sd}`].node.localToWorld(tip.set((k ? -1 : 1) * 75, 0, -1.5));
      pts.push(bird.body.worldToLocal(tip.clone()));
    }
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({color: C.or}));
    line.visible = false;
    bird.body.add(line);
    return line;
  });

  const P = await createPage({title: 'Calypte HM-4 · Cómo vuela un colibrí robótico', model, onState: (st) => traces.forEach((t) => (t.visible = !!st.trace))});
  const {range, speeds, beat, solid, partsPanel, partLook} = P;
  P.header({
    code: 'HM-4', kicker: 'Colibrí robótico · Microvehículo aéreo de 12 g', name: 'Calypte HM-4', sub: 'Cómo vuela · Seis figuras',
    icon: '<svg width="34" height="30" viewBox="0 0 34 30"><g fill="none" stroke="#14110a" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M3 22 L13 15 Q18 9 24 11 L33 9 L25 14 Q22 21 15 22 Z"/><path d="M14 15 L8 3 L19 11"/></g></svg>',
  });
  P.lead('Un colibrí no planea: se sostiene en el aire batiendo las alas adelante y atrás decenas de veces por segundo. Este robot de 12 gramos hace lo mismo con dos motores del tamaño de una lenteja.');
  P.text('Todas las figuras son el mismo modelo: 44 piezas que encajan sin atravesarse, movidas por una sola variable, el ángulo de la manivela. Arrastra cualquiera para girarla.');

  // ---------------------------------------------------------------- 1 · the whole bird
  P.h2('01 — El conjunto', 'Un pájaro de 12 gramos');
  P.text(`Cuerpo inclinado 38°, cabeza horizontal, cola abierta hacia abajo: es la postura de un colibrí parado en el aire. Las alas baten a 34 veces por segundo; aquí las ves 40 veces más despacio.`);
  P.figure({
    n: 1, title: 'Vuelo estacionario', cam: {az: 52, el: 10, d: 0.4, ty: 0.066, tz: 0.012}, 
    controls: `<span class="btn pp" data-pp>❚❚ Pausa</span>${speeds}`,
    step: (f, dt) => (beat(f, dt, B.f0), {phase: f.phase, look: solid, blur: f.speed < 0.05 ? 1 : 0.0, autoTurn: 5}),
    readout: () => `34 Hz &nbsp;·&nbsp; ±${Math.round(AMP)}° &nbsp;·&nbsp; 12,0 g`,
  });
  P.caption(`<b>Fig 1.</b> Envergadura 172 mm. La carcasa son 12 paneles blancos sobre un bastidor; la banda dorada del cuello marca la junta de la cabeza.`);

  // ---------------------------------------------------------------- 2 · inside
  P.h2('02 — El interior', 'Qué hay bajo la carcasa');
  P.text(`Mueve el control para levantar los paneles. Debajo aparece el bastidor, una quilla con cuadernas como la de un barco, y colgado de él todo lo demás: dos motores, la transmisión, la batería en la panza y la placa de control en el lomo.`);
  P.figure({
    n: 2, title: 'Carcasa abierta', cam: {az: 64, el: 16, d: 0.36, ty: 0.068, tz: 0.004}, 
    controls: `<span class="btn pp" data-pp>❚❚ Pausa</span>${range('open', 'Carcasa', 0, 1, 0.75)}`,
    step: (f, dt) => {
      beat(f, dt, B.f0);
      const k = Number(f.q('[data-open]').value);
      f.q('[data-open-v]').textContent = `${Math.round(k * 100)} %`;
      return {phase: f.phase, look: solid, openAsm: ['transmision', 'bateria'], open: k * 1.5, blur: 0, k};
    },
    readout: (f, st) => (st.k < 0.05 ? '12 paneles cerrados' : `44 piezas &nbsp;·&nbsp; 1 bastidor &nbsp;·&nbsp; 2 motores`),
  });
  P.caption(`<b>Fig 2.</b> Arriba salen los paneles del lomo y abajo los de la panza. La batería (120 mAh) es la pieza más pesada y va lo más baja posible para que el robot no vuelque.`);

  // ---------------------------------------------------------------- 3 · the drive
  P.h2('03 — El mecanismo', 'Del giro del motor al vaivén del ala');
  P.text(`Un motor solo sabe girar; un ala tiene que ir y volver. Entre los dos hay cuatro pasos, repetidos en cada lado:`);
  P.chain(['Motor · 24.480 rpm', 'Engranajes 1:12', 'Manivela r 2,5 mm', 'Yugo + cremallera ±2,5 mm', 'Piñón r 2,25 mm', 'Ala ±63,7°']);
  P.text(`Los engranajes reducen la velocidad doce veces. La manivela lleva un pasador dorado metido en la ranura del yugo: al girar, el pasador empuja el yugo adelante y atrás. El yugo lleva una cremallera que hace girar el piñón del eje del ala. Párala y mueve la fase a mano para seguirlo paso a paso.`);
  P.figure({
    n: 3, title: 'Transmisión izquierda', cam: {az: 114, el: 20, d: 0.125, ty: 0.073, tz: 0.001, tx: 0.005}, 
    controls: `<span class="btn pp" data-pp>❚❚ Pausa</span>${speeds}${range('ph', 'Fase', 0, 360, 0, 1)}`,
    setup: (f) => {
      f.speed = 1 / 200;
      for (const o of f.el.querySelectorAll('[data-speed]')) o.classList.toggle('on', Number(o.dataset.speed) === f.speed);
      f.q('[data-ph]').addEventListener('input', (e) => {
        f.setPlay(false);
        f.phase = Number(e.target.value) * D2R;
      });
    },
    step: (f, dt) => {
      beat(f, dt, B.f0);
      const deg = (((f.phase / D2R) % 360) + 360) % 360;
      if (f.playing) f.q('[data-ph]').value = deg;
      f.q('[data-ph-v]').textContent = `${Math.round(deg)}°`;
      return {phase: f.phase, blur: 0, deg, look: (part, asm) => (SHELL.test(part) || /^wing(frame|mem)/.test(part) || /_R$/.test(part) || asm === 'cabeza' || asm === 'cola' || asm === 'bateria' || part === 'pcb' ? 'hide' : part === 'airframe' ? 'ghost' : 'solid')};
    },
    readout: (f, st) => `Manivela ${Math.round(st.deg)}° &nbsp;·&nbsp; Cremallera ${sgn(-B.crank * Math.sin(f.phase))} mm &nbsp;·&nbsp; Ala ${sgn(wingAt(f.phase).stroke, 0)}°`,
  });
  P.caption(`<b>Fig 3.</b> Solo el lado izquierdo, sin el ala, y con el bastidor transparente. 2,5 mm de manivela entre 2,25 mm de radio del piñón son 1,11 radianes: el ala barre 63,7° a cada lado, ni un grado más, porque lo fija la geometría y no el motor.`);

  // ---------------------------------------------------------------- 4 · the wing
  P.h2('04 — El ala', 'Un ocho en el aire');
  P.text(`Un pájaro normal solo empuja al bajar el ala. El colibrí la da la vuelta al final de cada recorrido, como quien rema con la mano en el agua, y así sustenta tanto al ir como al volver. La punta dibuja un ocho tumbado: la línea dorada.`);
  P.text(`La sustentación crece con el cuadrado de la frecuencia. Sube el control: a 34 Hz iguala el peso y el robot se queda quieto; por encima, asciende.`);
  P.figure({
    n: 4, title: 'Trayectoria de la punta', cam: {az: 28, el: 34, d: 0.5, ty: 0.07, tz: 0.01}, 
    controls: `<span class="btn pp" data-pp>❚❚ Pausa</span>${range('hz', 'Frecuencia', 24, 44, 34, 0.5)}`,
    step: (f, dt) => {
      const hz = Number(f.q('[data-hz]').value);
      f.q('[data-hz-v]').textContent = `${es(hz)} Hz`;
      beat(f, dt, hz);
      return {phase: f.phase, f: hz, look: solid, blur: 1, trace: true, hz};
    },
    readout: (f, st) => {
      const L = liftAt(st.hz);
      const d = L - WEIGHT;
      return `Giro del ala ${Math.round(wingAt(f.phase).rot + 90)}° &nbsp;·&nbsp; Sustentación ${Math.round(L)} mN &nbsp;·&nbsp; ${Math.abs(d) < 3 ? 'Se sostiene' : d > 0 ? 'Asciende' : 'Desciende'}`;
    },
  });
  P.caption(`<b>Fig 4.</b> El peso son 117,7 mN (12 g). A 44 Hz las alas dan casi 200 mN: el margen que usa para acelerar y maniobrar.`);

  // ---------------------------------------------------------------- 5 · level head
  P.h2('05 — La cabeza', 'El cuerpo se inclina, la mirada no');
  P.text(`Para avanzar, el robot baja el morro y con él todo el plano en el que baten las alas. Las cámaras de los ojos necesitan un horizonte estable, así que el cuello gira justo lo contrario que el cuerpo.`);
  P.figure({
    n: 5, title: 'Cuello compensado', cam: {az: 86, el: 6, d: 0.4, ty: 0.066, tz: 0.012}, 
    controls: range('pt', 'Cabeceo del cuerpo', 12, 43, 38, 0.5),
    step: (f, dt) => {
      beat(f, dt, B.f0);
      const pitch = Number(f.q('[data-pt]').value);
      f.q('[data-pt-v]').textContent = `${es(pitch)}°`;
      return {phase: f.phase, pitch, look: solid, blur: 1, spread: (pitch - 12) / 31};
    },
    readout: (f, st) => `Cuerpo ${es(st.pitch)}° &nbsp;·&nbsp; Cuello ${sgn(-st.pitch)}° &nbsp;·&nbsp; Cabeza 0,0° &nbsp;·&nbsp; ${st.pitch < 24 ? 'Avance' : 'Estacionario'}`,
  });
  P.caption(`<b>Fig 5.</b> El cuello es un barril sobre un eje; un fuelle esférico tapa la junta en todo el recorrido. La cola se abre al frenar y se cierra al avanzar.`);

  // ---------------------------------------------------------------- 6 · exploded
  P.h2('06 — El despiece', 'Las 44 piezas');
  P.text(`Sepáralo y elige una pieza para verla sola.  Nada está pegado encima de otra cosa: los ejes pasan por agujeros, los ojos entran en su alojamiento y las siete plumas de la cola van apiladas en un mismo pasador, como las varillas de un abanico.`);
  P.figure({
    n: 6, title: 'Despiece', hint: 'Arrastra para girar · toca una pieza', cam: {az: 48, el: 16, d: 0.58, ty: 0.07, tz: 0.004}, 
    controls: range('ex', 'Separación', 0, 1, 0.55),
    ...partsPanel(PARTS),
    step: (f) => {
      const k = Number(f.q('[data-ex]').value);
      f.q('[data-ex-v]').textContent = `${Math.round(k * 100)} %`;
      return {phase: 0.9, explode: k * k * (3 - 2 * k), look: partLook(f), blur: 0, k, autoTurn: f.sel < 0 ? 4 : 0, focusRe: f.focusRe};
    },
    readout: (f, st) => (f.sel >= 0 ? PARTS[f.sel][0] : st.k < 0.03 ? 'Montado' : `${Math.round(st.k * 100)} % separado &nbsp;·&nbsp; 44 piezas`),
  });
  P.caption(`<b>Fig 6.</b> Carcasa 12 · bastidor 1 · transmisión 12 · alas 4 · cabeza 6 · cola 7 · batería y placa 2.`);

  P.h2('Ficha', 'Los números');
  P.table([
    ['Masa', `12,0 g (117,7 mN de peso)`],
    ['Envergadura', `172 mm · ala de 76 mm, varilla de carbono y membrana de poliéster`],
    ['Batido', `34 Hz en estacionario · ±63,7° · giro del ala de 100° en cada inversión`],
    ['Motores', `2 sin núcleo, Ø6 mm · ${Math.round(motorRpm(B.f0)).toLocaleString('es-ES')} rpm a 34 Hz`],
    ['Reductora', `8→32 y 10→30 dientes, módulo 0,3 · 1:12 · ejes a 6,0 mm`],
    ['Conversión', `Manivela 2,5 mm · yugo escocés · cremallera · piñón de 15 dientes (r 2,25 mm)`],
    ['Energía', `LiPo 1S de 120 mAh · 2,4 W en estacionario`],
    ['Sustentación máx.', `27 g, algo más del doble de su peso`],
  ]);
  P.caption(`Masa y carga máxima tomadas del colibrí robótico de la Universidad de Purdue (12 g, levanta hasta 27 g). El resto del diseño es propio de este modelo.`);
  P.footer('Calypte HM-4 · Modelo de 44 piezas hecho en Blender · Sin interferencias en 26 poses', 'Calypte Robotics');

  P.start();
}
