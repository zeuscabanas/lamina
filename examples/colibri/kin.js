// Calypte HM-4, a 12 g robotic hummingbird: the math. Millimetres, body frame: +z is the beak, y up, +x the bird's
// left. One input drives everything: the flapping phase, integrated from the motor speed. Each wing is driven by its
// own coreless motor through a 1:12 gearbox to a Scotch-yoke crank (r = 2.5 mm); the yoke pushes a rack that turns a
// 15-tooth pinion (r = 2.25 mm) on the wing root, so the stroke is exactly sinusoidal with an amplitude of
// 2.5 / 2.25 rad = ±63.7°. The geometry and the joint laws live in model.py; these are the same numbers for the panels. The wing turns over at each reversal (supination) and its tip draws a figure of eight.
// No three.js in here.

export const D2R = Math.PI / 180;
export const B = {
  mass: 12, // g (Purdue's hummingbird robot: 12 g, the mass of an adult magnificent hummingbird)
  f0: 34, // Hz, hover flapping frequency
  gear: 12, // motor : crank
  crank: 2.5, // mm, Scotch-yoke crank radius
  pinion: 2.25, // mm, wing-root pinion pitch radius (15 teeth × module 0.3 / 2)
  wing: 76, // mm, root to tip
  span: 172, // mm, tip to tip
  bodyPitch: 38, // deg nose-up in hover: the stroke plane is level
  shoulder: [10, 10, 7], // left wing root, body frame
  cellV: 3.7, // 1S LiPo
  cellMah: 120,
  maxLift: 27, // g the wings can lift at full speed
};
export const AMP = (B.crank / B.pinion) / D2R; // ±63.7°
export const WEIGHT = (B.mass / 1000) * 9.81 * 1000; // mN, 117.7
export const STROKE_AXIS = [0, Math.cos(B.bodyPitch * D2R), Math.sin(B.bodyPitch * D2R)];

/** the wing's three angles at phase p (rad): stroke (forward +), rotation of the chord (deg, −40 on the downstroke,
 * −140 on the upstroke, the wing upside down), deviation (the figure of eight) */
export const wingAt = (p) => ({
  stroke: AMP * Math.sin(p),
  rot: -90 + 50 * Math.tanh(3 * Math.cos(p)),
  dev: 7 * Math.sin(2 * p),
});
/** the yoke's crank angle is the phase; the rack's travel and the pinion's turn follow */
export const rackAt = (p) => B.crank * Math.sin(p);
/** instantaneous lift as a fraction of the mean: both half strokes lift (∝ wing speed²) */
export const liftShape = (p) => 2 * Math.cos(p) ** 2;
/** mean lift (mN) at flapping frequency f: ∝ f², equal to the weight at 34 Hz */
export const liftAt = (f) => WEIGHT * (f / B.f0) ** 2;
/** electrical power (W): avionics plus aerodynamic power ∝ f³ */
export const powerAt = (f) => 0.35 + 2.05 * (f / B.f0) ** 3;
export const motorRpm = (f) => f * B.gear * 60;
