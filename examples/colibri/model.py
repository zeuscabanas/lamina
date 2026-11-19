"""Calypte HM-4, the model. Run: python model.py [--audit] [--out colibri.glb]   (or blender -b -P model.py -- …)

Body frame, millimetres: x the bird's left, y up, z toward the beak. The torso is one analytic surface (a bird's
silhouette: deep breast, flat back, tapering rump) split into twelve panels with real thickness; under them one welded
airframe carries everything. The drive sits in a frame tilted 38° so its y is the stroke axis: per side a motor, a
1:12 train (8→32, 10→30, module 0.3), a crank with a pin in a Scotch yoke, a rack on the yoke and a 15-tooth pinion
on the wing shaft. The head pivots on a neck barrel and stays level while the body pitches.

PARTS (44 meshes)
  airframe 1   keel, 5 ring frames, 2 longerons, neck mount + barrel, motor plates, bridge, bearing plate, posts,
               shoulder bosses, battery tray, tail boom + fork + pin, legs
  shell 12     top_0..5 (asm transmision), bot_0..5 (asm bateria), bolts, hatch and vents fused
  drive 12     motor, mpinion, compound, crank, yoke, wingshaft  × L/R
  wings 4      wingframe (spar, sleeve, ball, veins), wingmem  × L/R
  power 2      battery, pcb
  head 6       head_base (lugs, gaiter, keel, mounts), crown, face, eye × 2, beak
  tail 7       feather_0..6, stacked on the pin like a hand fan
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'blender'))
import bpy  # noqa: E402,F401
from mathutils import Matrix, Vector  # noqa: E402

from tdb import *  # noqa: E402,F403
import audit as AUD  # noqa: E402

D = math.radians
PITCH = D(38)
MOD = 0.3
CRANK = 2.5
R_PIN = 15 * MOD / 2  # 2.25
AMP = CRANK / R_PIN  # 1.1111 rad = 63.7°

reset()

# ------------------------------------------------------------------ the torso surface
ZS = [-30, -24, -16, -6, 4, 12, 20, 26]
A = spline(ZS, [3.5, 6.6, 10.2, 13.2, 14.5, 14.2, 11.8, 9.0])
TOP = spline(ZS, [3.0, 5.0, 7.4, 9.6, 10.5, 10.5, 9.6, 8.2])
BOT = spline(ZS, [3.0, 5.6, 9.2, 12.6, 14.4, 14.4, 12.0, 8.6])
YC = spline(ZS, [2.0, 1.6, 1.0, 0.2, 0.0, 0.3, 1.2, 2.5])
EXP = 2 / 2.25


def sp(v):
    return math.copysign(abs(v) ** EXP, v)


def torso0(phi, z):
    c, s = math.cos(phi), math.sin(phi)
    return Vector((A(z) * sp(c), YC(z) + (TOP(z) if s >= 0 else BOT(z)) * sp(s), z))


def torso(phi, z, off=0.0):
    """the surface at angle phi (0 = left side, π/2 = back) and station z; off > 0 is inside by that many mm,
    measured along the true normal"""
    p = torso0(phi, z)
    if off == 0.0:
        return tuple(p)
    e = 1e-3
    n = (torso0(phi + e, z) - torso0(phi - e, z)).cross(torso0(phi, z + e) - torso0(phi, z - e)).normalized()
    return tuple(p - n * off)


def half_width(y, z, off=0.0):
    b = (TOP(z) if y >= YC(z) else BOT(z)) - off
    t = min(1.0, abs(y - YC(z)) / b)
    return (A(z) - off) * (1 - t ** 2.25) ** (1 / 2.25)


def loop(z, off, n=64):
    return [Vector(torso(2 * math.pi * i / n, z, off)) for i in range(n)]


def between(outer0, outer1, inner0, inner1):
    """a closed solid between two outer loops and two inner loops (same count): a ring frame or a bulkhead"""
    import bmesh
    bm = bmesh.new()
    n = len(outer0)
    L = [[bm.verts.new(p) for p in lp] for lp in (outer0, outer1, inner1, inner0)]
    for k in range(4):
        a, b = L[k], L[(k + 1) % 4]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def disc_between(outer0, outer1, c0, c1):
    """a solid bulkhead: two outer loops closed with fans to two centre points"""
    import bmesh
    bm = bmesh.new()
    n = len(outer0)
    a = [bm.verts.new(p) for p in outer0]
    b = [bm.verts.new(p) for p in outer1]
    ca, cb = bm.verts.new(c0), bm.verts.new(c1)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
        bm.faces.new((ca, a[j], a[i]))
        bm.faces.new((cb, b[i], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


SKIN = 0.7  # panel thickness
EDGES = [-30, -22.5, -14, -5, 4.5, 16, 26]
SEAM = 0.035  # half the side seam, radians

# ------------------------------------------------------------------ the drive frame and its layout (x, u, w)
DRV_AT = Vector((0, 1.5, 6))
DRV = Matrix.Translation(DRV_AT) @ Matrix.Rotation(PITCH, 4, 'X')


def to_body(bm):
    """a bmesh built in drive coordinates, moved into the body frame"""
    import bmesh
    bmesh.ops.transform(bm, matrix=DRV, verts=bm.verts)
    return bm


XS = 8.0  # wing shaft
X_RACK = XS - R_PIN  # the rack's pitch line, 5.75
CR = (-2.0, 0.0)  # crank axis (u, w)
CP = (-2.0, -6.0)  # compound axis: 6.0 = (10 + 30)·0.3/2 from the crank
k45 = math.sqrt(0.5)
MO = (CP[0] - 6 * k45, CP[1] - 6 * k45)  # motor axis: 6.0 = (8 + 32)·0.3/2 from the compound
U_PIN = (2.0, 4.0)  # the pinion's and the rack's band along the shaft
U_BR = (4.1, 4.7)  # bridge
U_LO = (1.3, 1.9)  # lower bearing plate


def shaft_exit(s):
    """u where the wing shaft leaves the shell"""
    lo, hi = 5.0, 20.0
    for _ in range(40):
        u = (lo + hi) / 2
        p = DRV @ Vector((s * XS, u, 0))
        inside = abs(p.y - YC(p.z)) < (TOP(p.z) if p.y >= YC(p.z) else BOT(p.z)) and abs(p.x) < half_width(p.y, p.z)
        lo, hi = (u, hi) if inside else (lo, u)
    return lo


U_EXIT = shaft_exit(1)
U_BOSS = U_EXIT + 2.6
U_HUB = U_BOSS + 0.1
U_BALL = U_HUB + 1.0 + 1.65

# ------------------------------------------------------------------ airframe: one welded part
import bmesh as _bmesh  # noqa: E402

fr = []
# keel: a plate on the centre plane following the silhouette, notched for the battery and the board
kz = [-27 + i * 1.0 for i in range(50)]  # −27 … 22


def keel_top(z):
    y = YC(z) + TOP(z) - 2.25
    return min(y, 3.15) if -22.01 <= z <= -11.99 else y


def keel_bot(z):
    y = YC(z) - BOT(z) + 2.25
    return max(y, -6.85) if -5.01 <= z <= 13.01 else y


outline = [(keel_top(z), z) for z in kz] + [(keel_bot(z), z) for z in reversed(kz)]
keel = prism([(z, y) for y, z in outline], 1.2, 'z')  # outline in (a, b) = (z, y), thickness along its own z
_bmesh.ops.transform(keel, matrix=Matrix(((0, 0, 1, 0), (0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 0, 1))), verts=keel.verts)  # (a, b, t) → (x = t, y = b, z = a)
_bmesh.ops.recalc_face_normals(keel, faces=keel.faces)
fr.append(keel)
# ring frames under the panel gaps, longerons under the side seams
def ring_arc(z, p0, p1, depth=1.0, half=0.8, n=40):
    """a ring frame under a panel gap, from angle p0 to p1 (a closed bar hugging the inside of the skin)"""
    secs = []
    for i in range(n + 1):
        ph = p0 + (p1 - p0) * i / n
        secs.append([Vector(torso(ph, z - half, SKIN + 0.05)), Vector(torso(ph, z + half, SKIN + 0.05)), Vector(torso(ph, z + half, SKIN + 0.05 + depth)), Vector(torso(ph, z - half, SKIN + 0.05 + depth))])
    bm = _bmesh.new()
    vs = [[bm.verts.new(p) for p in sec] for sec in secs]
    for i in range(n):
        for k in range(4):
            bm.faces.new((vs[i][k], vs[i][(k + 1) % 4], vs[i + 1][(k + 1) % 4], vs[i + 1][k]))
    bm.faces.new(vs[0])
    bm.faces.new(vs[-1])
    _bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


for z in EDGES[1:-1]:
    if z == 4.5:  # the drive fills the back here: the frame runs under the belly only
        fr.append(ring_arc(z, math.pi + 0.12, 2 * math.pi - 0.12))
    else:
        fr.append(ring_arc(z, 0.0, 2 * math.pi, n=72))
for phi in (0.0, math.pi):
    fr.append(tube([torso(phi, z, SKIN + 0.75) for z in range(-26, 25, 3)], 0.55, seg=8, smooth=2))
# neck mount: a bulkhead, a post, a barrel on the pitch axis
PIV = Vector((0, 2.8, 31))
fr.append(disc_between(loop(22.4, SKIN + 0.05), loop(23.6, SKIN + 0.05), Vector((0, YC(22.4), 22.4)), Vector((0, YC(23.6), 23.6))))
fr.append(moved(cyl(1.6, PIV.z - 23.0, 'z', 20), at=(0, PIV.y, (PIV.z + 23.0) / 2)))
fr.append(moved(cyl(2.0, 5.0, 'x', 28), at=PIV))
# rear bulkhead, tail boom, fork and pin
fr.append(disc_between(loop(-29.3, SKIN + 0.05), loop(-28.3, SKIN + 0.05), Vector((0, YC(-29.3), -29.3)), Vector((0, YC(-28.3), -28.3))))
TY = 2.0  # tail axis height
NF = 7
F_T, F_G = 0.6, 0.08
STACK = NF * F_T + (NF - 1) * F_G
PIN_Z = -36.0
fr.append(moved(cyl(1.5, 5.4, 'z', 20), at=(0, TY, -31.0)))
fr.append(moved(box(4.4, STACK + 1.5, 0.5), at=(0, TY, -33.55)))
for sgn in (1, -1):
    fr.append(moved(box(4.4, 0.65, 4.4), at=(0, TY + sgn * (STACK / 2 + 0.05 + 0.325), -35.5)))
fr.append(moved(cyl(0.7, STACK + 0.2, 'y', 16), at=(0, TY, PIN_Z)))
# battery tray: two rails under the keel's notch, a stop at each end
for x in (-5.15, 5.15):
    fr.append(moved(box(0.4, 1.0, 14.0), at=(x, -7.4, 4.4)))
fr.append(moved(box(10.7, 0.5, 16.0), at=(0, -6.6, 4.4)))
# board posts
for x in (-4, 4):
    for z in (-20, -13.5):
        fr.append(moved(cyl(0.6, 1.4, 'y', 10), at=(x, 2.45, z)))
fr.append(moved(box(9.2, 0.5, 1.0), at=(0, 1.55, -20)))
fr.append(moved(box(9.2, 0.5, 1.0), at=(0, 1.55, -13.5)))
# legs: a crossbar on the keel, struts through the belly, a knee, three toes
LEG_Z, LEG_X = 13.7, 4.0
fr.append(moved(box(2 * LEG_X + 1.4, 1.0, 1.4), at=(0, -9.6, LEG_Z)))
for s in (1, -1):
    fr.append(moved(cyl(0.7, 7.2, 'y', 12), at=(s * LEG_X, -12.7, LEG_Z)))
    fr.append(moved(ball(1.15, 16, 10), at=(s * LEG_X, -16.6, LEG_Z)))
    fr.append(tube([(s * LEG_X, -16.6, LEG_Z), (s * LEG_X, -18.2, LEG_Z + 2.4), (s * LEG_X, -19.4, LEG_Z + 2.9)], 0.5, seg=8, smooth=3))
    for a in (-0.5, 0, 0.5):
        fr.append(tube([(s * LEG_X, -19.4, LEG_Z + 2.9), (s * LEG_X + math.sin(a) * 2.2, -20.0, LEG_Z + 2.9 + math.cos(a) * 2.2), (s * LEG_X + math.sin(a) * 3.0, -20.6, LEG_Z + 2.9 + math.cos(a) * 3.0)], lambda t: 0.36 - 0.2 * t, seg=6, smooth=3))
# the drive's fixed parts, built in drive coordinates
dv = []
dv.append(carve(moved(box(2 * 10.0, U_BR[1] - U_BR[0], 6.8), at=(0, (U_BR[0] + U_BR[1]) / 2, 0)), [moved(cyl(0.75, 2.0, 'y', 20), at=(s * XS, (U_BR[0] + U_BR[1]) / 2, 0)) for s in (1, -1)]))  # bridge, bored for the shafts
for s in (1, -1):
    dv.append(moved(box(2.9, U_LO[1] - U_LO[0], 7.0), at=(s * 8.75, (U_LO[0] + U_LO[1]) / 2, 0)))  # lower bearing plate
    for w in (-2.95, 2.95):
        dv.append(moved(box(1.0, U_BR[0] - U_LO[1] + 0.1, 1.0), at=(s * 9.5, (U_BR[0] + U_LO[1]) / 2, w)))  # posts
    dv.append(moved(ring(1.9, 0.72, U_BOSS - U_BR[1] + 0.05, 'y', 28), at=(s * XS, (U_BOSS + U_BR[1]) / 2, 0)))  # shoulder boss
    # motor face plate and its web to the keel
    dv.append(moved(ring(3.2, 0.62, 0.3, 'x', 32), at=(s * 2.05, MO[0], MO[1])))
    wc = (MO[0] - 3.5 * k45, MO[1] - 3.5 * k45)
    web = box(1.7, 0.8, 5.0)
    moved(web, rot=((1, 0, 0), D(45)))
    dv.append(moved(web, at=(s * 1.37, wc[0], wc[1])))
fr += [to_body(b) for b in dv]
airframe = part('airframe', join(*fr), mat='ink', asm='bastidor', sharp=35)

# ------------------------------------------------------------------ shell panels
def bolt_on(z, phi, r=0.42):
    p = Vector(torso(phi, z))
    e = 1e-3
    n = (Vector(torso(phi + e, z)) - Vector(torso(phi - e, z))).cross(Vector(torso(phi, z + e)) - Vector(torso(phi, z - e))).normalized()
    return moved(cyl(r, 0.5, 'z', 10), rot=aim(n), at=p + n * 0.05)


def plate_on(z, phi, sx, sz, t=0.6):
    p = Vector(torso(phi, z))
    e = 1e-3
    n = (Vector(torso(phi + e, z)) - Vector(torso(phi - e, z))).cross(Vector(torso(phi, z + e)) - Vector(torso(phi, z - e))).normalized()
    zax = Vector((0, 0, 1))
    xax = zax.cross(n).normalized() * -1
    m = Matrix((xax, zax, n)).transposed().to_4x4()
    return moved(box(sx, sz, t), rot=m, at=p + n * (t / 2 - 0.25)), p, n, m


hole_L = to_body(moved(cyl(2.1, 9.0, 'y', 28), at=(XS, U_EXIT, 0)))
hole_R = to_body(moved(cyl(2.1, 9.0, 'y', 28), at=(-XS, U_EXIT, 0)))
leg_holes = [moved(cyl(1.0, 6.0, 'y', 16), at=(s * LEG_X, -14.0, LEG_Z)) for s in (1, -1)]
for k in range(6):
    z0, z1 = EDGES[k] + (0.5 if k else 0.0), EDGES[k + 1] - (0.5 if k < 5 else 0.0)
    zc = (z0 + z1) / 2
    nz = max(8, int((z1 - z0) * 2.2))
    for side, (p0, p1) in (('top', (SEAM, math.pi - SEAM)), ('bot', (math.pi + SEAM, 2 * math.pi - SEAM))):
        extra = []
        bm = patch(torso, p0, p1, z0, z1, nu=56, nv=nz, thick=SKIN)
        if A((z0 + z1) / 2) > 8:  # two bolts by each seam
            for ph in ((0.42, math.pi - 0.42) if side == 'top' else (math.pi + 0.42, 2 * math.pi - 0.42)):
                extra.append(bolt_on(z0 + 1.3, ph))
                extra.append(bolt_on(z1 - 1.3, ph))
        if side == 'top' and k == 2:  # the dorsal hatch: a raised plate, a latch, four screws
            h, hp, hn, hm = plate_on(-9.5, math.pi / 2, 6.6, 6.0)
            extra.append(h)
            extra.append(moved(box(2.6, 1.1, 0.5), rot=hm, at=hp + hn * 0.55 + hm.to_3x3() @ Vector((0, -1.7, 0))))
            for dx, dz in ((-2.5, 2.2), (2.5, 2.2), (-2.5, -2.2), (2.5, -2.2)):
                extra.append(moved(cyl(0.34, 0.4, 'z', 8), rot=hm, at=hp + hn * 0.45 + hm.to_3x3() @ Vector((dx, dz, 0))))
        if side == 'top' and k == 1:  # cooling slots on each flank: closed raised slats
            for ph in (0.95, math.pi - 0.95):
                for i in range(4):
                    sl, slp, sln, slm = plate_on(-20.4 + i * 1.3, ph, 4.2, 0.55, 0.5)
                    extra.append(sl)
        cuts = []
        if side == 'top' and k == 4:
            cuts = [hole_L.copy(), hole_R.copy()]
        if side == 'bot' and k == 4:
            cuts = [h.copy() for h in leg_holes]
        orange = None
        if k == 5:
            orange = {'orange': lambda c: 19.2 < c.z < 22.6}
        if k == 0 and side == 'top':
            orange = {'orange': lambda c: c.z < -27.2}
        dy = 1 if side == 'top' else -1
        part(f'{side}_{k}', join(bm, *extra), mat='shell', asm='transmision' if side == 'top' else 'bateria', bevel=0.16, cut=cuts,
             explode=(0, dy * (34 if side == 'top' else 20), zc * 0.5), open=(0, dy * 22, 0), mats=orange, sharp=38)

# ------------------------------------------------------------------ the drive
drive = frame('drive', at=DRV_AT, rot=((1, 0, 0), PITCH), asm='transmision')
rig_input('phase', 0.0, 2 * math.pi, 16, rest=0.9, cyclic=True)
for s, sd in ((1, 'L'), (-1, 'R')):
    ex = (s * 9, 0, 0)
    # motor: can, orange end cap, fixed
    m = join(moved(cyl(3.0, 5.0, 'x', 32), at=(s * 4.75, 0, 0)), moved(cyl(3.05, 1.0, 'x', 32), at=(s * 7.75, 0, 0)), moved(cyl(1.2, 0.5, 'x', 16), at=(s * 8.5, 0, 0)))
    part(f'motor_{sd}', m, mat='ink', asm='transmision', at=(0, MO[0], MO[1]), parent=drive, bevel=0.2, explode=(s * 30, -8, -10),
         mats={'orange': lambda c, s=s: abs(c.x) > 7.2})
    # motor pinion: shaft + 8 teeth
    mp = join(moved(cyl(0.4, 1.4, 'x', 12), at=(s * 1.5, 0, 0)), moved(gear(8, MOD, 1.0, 0, 'x'), at=(s * 1.3, 0, 0)))
    o = part(f'mpinion_{sd}', mp, mat='steel', asm='transmision', at=(0, MO[0], MO[1]), parent=drive, explode=(s * 22, -8, -10))
    joint(o, 'rev', (1, 0, 0), {'k': -12})
    gear_info(o.name, 8, MOD, (0, MO[0], MO[1]), (1, 0, 0))
    # compound: shaft, 32 teeth inboard, 10 teeth outboard
    cp = join(moved(cyl(0.5, 2.4, 'x', 12), at=(s * 1.85, 0, 0)), moved(gear(32, MOD, 1.0, 0, 'x'), at=(s * 1.3, 0, 0)), moved(gear(10, MOD, 1.0, 0, 'x', phase=math.pi / 10), at=(s * 2.5, 0, 0)))
    o = part(f'compound_{sd}', cp, mat='brass', asm='transmision', at=(0, CP[0], CP[1]), parent=drive, explode=(s * 34, -1, -20))
    joint(o, 'rev', (1, 0, 0), {'k': 3})
    gear_info(o.name, 32, MOD, (0, CP[0], CP[1]), (1, 0, 0))
    gear_info(o.name, 10, MOD, (0, CP[0], CP[1]), (1, 0, 0))
    mate(f'mpinion_{sd}', o.name, 0.7, 'teeth in mesh, 8:32')
    # crank: shaft, 30 teeth, disc, pin at r = 3
    ck = join(moved(cyl(0.6, 2.95, 'x', 14), at=(s * 2.125, 0, 0)), moved(gear(30, MOD, 1.0, 0, 'x'), at=(s * 2.5, 0, 0)),
              moved(cyl(3.8, 0.55, 'x', 40), at=(s * 3.325, 0, 0)), moved(cyl(0.5, 1.2, 'x', 14), at=(s * 4.15, CRANK, 0)))
    o = part(f'crank_{sd}', ck, mat='steel', asm='transmision', at=(0, CR[0], CR[1]), parent=drive, explode=(s * 42, -1, 4),
             mats={'orange': lambda c, s=s: abs(c.x) > 3.62 and (c.y - CRANK) ** 2 + c.z ** 2 < 0.4})
    joint(o, 'rev', (1, 0, 0), {'k': -1})
    gear_info(o.name, 30, MOD, (0, CR[0], CR[1]), (1, 0, 0))
    mate(f'compound_{sd}', o.name, 0.7, 'teeth in mesh, 10:30')
    # yoke + rack: a slotted plate the pin drives, the rack on its top edge
    yk = join(moved(box(0.6, 7.85, 3.4), at=(s * 4.35, CR[0] + 0.025, 0)), moved(box(1.6, 0.9, 3.4), at=(s * 4.85, 2.15, 0)),
              moved(rack(8, MOD, U_PIN[1] - U_PIN[0], X_RACK - 4.65, 'z'), scale=(s, 1, 1), at=(s * X_RACK, (U_PIN[0] + U_PIN[1]) / 2, 0)))
    _bmesh.ops.recalc_face_normals(yk, faces=yk.faces)
    slot = moved(box(2.0, 7.1, 1.12), at=(s * 4.35, CR[0], 0))
    o = part(f'yoke_{sd}', yk, mat='dark', asm='transmision', parent=drive, cut=[slot], explode=(s * 50, 3, 14))
    joint(o, 'slide', (0, 0, 1), {'sin': [-CRANK, 1, 0]})
    gear_info(o.name, 0, MOD, (s * X_RACK, 3, 0), (0, 0, 1), rack=True)
    # wing shaft: pinion, shaft, hub disc, two cheeks for the root ball
    ws = join(moved(cyl(0.6, U_HUB + 1.0 - (U_LO[1] + 0.05), 'y', 14), at=(0, (U_HUB + 1.0 + U_LO[1] + 0.05) / 2, 0)),
              moved(gear(15, MOD, U_PIN[1] - U_PIN[0] - 0.1, 0, 'y'), at=(0, (U_PIN[0] + U_PIN[1]) / 2, 0)),
              moved(cyl(2.7, 1.0, 'y', 32), at=(0, U_HUB + 0.5, 0)),
              moved(box(3.6, 3.9, 0.7), at=(0, U_HUB + 1.0 + 1.9, 1.95)), moved(box(3.6, 3.9, 0.7), at=(0, U_HUB + 1.0 + 1.9, -1.95)))
    o = part(f'wingshaft_{sd}', ws, mat='steel', asm='alas', at=(s * XS, 0, 0), parent=drive, bevel=0.12, explode=(s * 4, 20, 0),
             mats={'orange': lambda c: c.y > U_HUB - 0.1})
    joint(o, 'rev', (0, 1, 0), {'sin': [-s * AMP, 1, 0]})
    gear_info(o.name, 15, MOD, (s * XS, 0, 0), (0, 1, 0))
    mate(f'yoke_{sd}', o.name, 0.7, 'rack and pinion')
    shaft = o
    # wing: deviation, then rotation about the spar
    wdev = frame(f'wdev_{sd}', at=(0, U_BALL, 0), parent=shaft)
    joint(wdev, 'rev', (0, 0, 1), {'sin': [s * D(7), 2, 0]})
    wrot = frame(f'wrot_{sd}', parent=wdev)
    joint(wrot, 'rev', (1, 0, 0), {'c': -math.pi / 2, 'tanh': [D(50), 3]})
    L = 76.0

    def chord(x):
        u = x / L
        return max(5.0, 8 + 17 * math.sin(min(1, u * 1.3) * math.pi * 0.6) - 26 * max(0, u - 0.6) ** 1.5)
    wf = [ball(1.5, 20, 12), tube([(s * 1.2, 0, 0), (s * 40, 0, 0), (s * 75.5, 0, -1.5)], lambda t: 0.85 - 0.45 * t, seg=10, smooth=1),
          moved(cyl(1.3, 9.0, 'x', 18), at=(s * 6.5, 0, 0))]
    YM = -0.95  # the membrane hangs just under the spar
    chv = lambda x: chord(x) * min(1.0, 0.3 + 0.7 * (x - 14.0) / 20)  # noqa: E731
    for i in range(7):
        x1 = 18 + i * (L - 22) / 6
        x0 = 14.5 + i * 0.6
        wf.append(tube([(s * x0, YM + 0.31, -0.5), (s * (x0 + (x1 - x0) * 0.5), YM + 0.31, -chv(x1) * 0.42), (s * x1, YM + 0.31, -chv(x1) + 0.5)], 0.22, seg=6, smooth=5))
    wf.append(moved(box(1.0, 0.9, 1.0), at=(s * 14.6, YM + 0.52, -0.2)))  # the clamp that ties the membrane to the spar
    part(f'wingframe_{sd}', join(*wf), mat='carbon', asm='alas', parent=wrot, explode=(s * 22, 6, 0),
         mats={'orange': lambda c: 2.0 < abs(c.x) < 11.0 and c.y * c.y + c.z * c.z < 1.75})
    n = 26
    X0 = 14.0  # the membrane starts clear of the hub; its chord grows from 5 mm over the first 20
    ch = lambda x: chord(x) * min(1.0, 0.3 + 0.7 * (x - X0) / 20)  # noqa: E731
    pts = [(s * (X0 + (L - X0) * i / n), 0.3 - 1.5 * (i / n) ** 3) for i in range(n + 1)]
    pts += [(s * (L - 2.5), -ch(L - 2.5) * 0.92)]
    pts += [(s * (X0 + (L - 3 - X0) * i / n), -ch(X0 + (L - 3 - X0) * i / n)) for i in range(n, -1, -1)]
    mem = prism(pts if s > 0 else pts[::-1], 0.12, 'z')  # outline in (x, chord), thin along its own z
    _bmesh.ops.transform(mem, matrix=Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))), verts=mem.verts)  # (a, b, t) → (x = a, y = t, z = b)
    _bmesh.ops.recalc_face_normals(mem, faces=mem.faces)
    part(f'wingmem_{sd}', mem, mat='membrane', asm='alas', at=(0, YM, 0), parent=wrot, explode=(s * 22, 6, 0))
    anchor(f'wing{sd}', (s * L * 0.62, 0.5, 0), wrot)
    anchor(f'root{sd}', (0, 0, 0), wdev)
    anchor(f'motor{sd}', (s * 6, MO[0], MO[1]), drive)
    anchor(f'crank{sd}', (s * 3.6, CR[0], CR[1]), drive)
    anchor(f'rack{sd}', (s * X_RACK, 3, 4), drive)

# ------------------------------------------------------------------ power
bat = join(moved(box(9.6, 4.2, 15.6), at=(0, 0, 0)), moved(box(9.7, 4.1, 2.2), at=(0, 0, 4.6)))
part('battery', bat, mat='dark', asm='bateria', at=(0, -9.0, 4.4), bevel=0.35, explode=(0, -34, 0), mats={'orange': lambda c: 3.4 < c.z < 5.8})
pcb = join(box(10, 0.8, 8.6), moved(box(3.6, 0.9, 3.6), at=(1.8, 0.8, 0.6)), moved(box(2.4, 0.7, 2.0), at=(-2.6, 0.7, -2.0)), moved(box(1.6, 1.0, 1.2), at=(-3.0, 0.85, 2.6)),
           moved(box(5.0, 0.6, 0.9), at=(1.0, 0.65, -3.5)))
part('pcb', pcb, mat='pcb', asm='transmision', at=(0, 3.6, -16.75), bevel=0.08, explode=(0, 26, -22), mats={'orange': lambda c: c.y > 0.45 and c.x > 0 and c.z > -1.3})
anchor('fc', (1.8, 4.6, -16), None)
anchor('batt', (4.8, -9.0, 8.4), None)

# ------------------------------------------------------------------ head: pivots on the neck barrel
HEAD0 = PITCH  # at rest the head is pitched down by the body's 38°: level in hover
head = frame('head', at=PIV, asm='cabeza', explode=(0, 6, 22))
joint(head, 'rev', (1, 0, 0), {'k': 1}, input='head')
rig_input('head', 0.2, 0.76, 5, rest=HEAD0)
HC = Vector((0, 2.2, 9.5))
HR = (9.0, 8.6, 8.0, 10.2, 9.0)  # x, y top, y bottom, z front, z back


def skull(theta, phi, off=0.0):
    """theta from the beak (0) to the nape (π), phi round the beak axis (π/2 = crown)"""
    st, ct = math.sin(theta), math.cos(theta)
    c, s = math.cos(phi), math.sin(phi)
    ry = HR[1] if s >= 0 else HR[2]
    rz = HR[3] if ct >= 0 else HR[4]
    # a flatter forehead and a fuller nape: the brow drops toward the beak
    brow = 1 - 0.16 * max(0.0, ct) ** 2 * max(0.0, s)
    return (HC.x + HR[0] * st * c, HC.y + ry * st * s * brow, HC.z + rz * ct)


hb = []
for sg in (1, -1):
    hb.append(moved(cyl(2.4, 1.0, 'x', 28), at=(sg * 3.1, 0, 0)))  # lugs on the barrel
    hb.append(moved(box(3.3, 1.5, 1.5), at=(sg * 5.25, 0, 0)))  # struts out to the gaiter
hb.append(moved(box(7.2, 2.4, 1.0), at=(0, 0.4, 2.9)))  # yoke bridge
hk = prism([(3.3, -1.6), (3.3, 2.4), (6, 6.0), (13, 6.6), (16, 3.4), (16, -0.6), (12, -3.4), (6, -3.6)], 1.0, 'z')
_bmesh.ops.transform(hk, matrix=Matrix(((0, 0, 1, 0), (0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 0, 1))), verts=hk.verts)
_bmesh.ops.recalc_face_normals(hk, faces=hk.faces)
hb.append(hk)
# the gaiter: a zone of a sphere centred on the pivot, open round the post through the head's whole travel
gd = Vector((0, -math.sin(D(27.5)), -math.cos(D(27.5))))
T0, T1, RO, RI = D(32), D(100), 7.4, 6.8
prof = [(RO * math.sin(T0 + (T1 - T0) * i / 14), RO * math.cos(T0 + (T1 - T0) * i / 14)) for i in range(15)]
prof += [(RI * math.sin(T1 - (T1 - T0) * i / 14), RI * math.cos(T1 - (T1 - T0) * i / 14)) for i in range(15)]
prof.append(prof[0])
hb.append(moved(lathe(prof, 'z', 48), rot=aim(gd)))
# crown rib: a ring under the crown/face seam, and the beak socket
hb.append(moved(box(15.0, 1.0, 1.2), at=(0, HC.y - 2.6, HC.z)))
hb.append(moved(box(1.2, 1.0, 11.0), at=(0, HC.y - 2.6, HC.z)))
EYES = {}
for sg in (1, -1):
    d = Vector((sg * 0.84, 0.22, 0.50)).normalized()
    t = 1 / math.sqrt((d.x / HR[0]) ** 2 + (d.y / HR[1]) ** 2 + (d.z / HR[3]) ** 2)
    P = HC + d * t  # on the skull (the brow factor is 1 % here)
    n = Vector((d.x * t / HR[0] ** 2, d.y * t / HR[1] ** 2, d.z * t / HR[3] ** 2)).normalized()  # the surface normal
    EYES[sg] = (n, P)
    hb.append(moved(box(3.4, 3.4, 4.0), rot=aim(n), at=P - n * 6.15))
part('head_base', join(*hb), mat='ink', asm='cabeza', parent=head, sharp=35, explode=(0, 0, 0))
# crown and face: the skull split below the eyes, cut by the gaiter's sphere, the beak and the eyes
SPLIT = 0.33
neck_cut = lambda: ball(7.62, 48, 24)  # noqa: E731
beak_cut = lambda: moved(cyl(2.9, 12, 'z', 28), at=(0, 1.4, 18))  # noqa: E731
eye_cut = lambda sg: moved(cyl(3.35, 6, 'z', 28), rot=aim(EYES[sg][0]), at=EYES[sg][1])  # noqa: E731
crown = patch(skull, 0.22, math.pi - 0.5, -SPLIT + 0.03, math.pi + SPLIT - 0.03, nu=44, nv=64, thick=SKIN)
sensor = moved(lathe([(0, 1.3), (1.0, 1.1), (1.6, 0.4), (1.7, -0.4), (0, -0.4)], 'y', 24), at=Vector(skull(math.pi / 2 + 0.25, math.pi / 2)) + Vector((0, 0.1, 0)))
part('crown', join(crown, sensor), mat='shell', asm='cabeza', parent=head, bevel=0.16, cut=[neck_cut(), beak_cut(), eye_cut(1), eye_cut(-1)], explode=(0, 13, 0), open=(0, 10, 0),
     mats={'orange': lambda c: c.y > HC.y + 4.2 and abs(c.x) < 2.6 and c.z > HC.z - 2 and c.y < 30, 'ink': lambda c: (c.x ** 2 + (c.z - (HC.z - 2.25)) ** 2) < 3.2 and c.y > HC.y + 8.0})
face = patch(skull, 0.22, math.pi - 0.5, math.pi + SPLIT + 0.03, 2 * math.pi - SPLIT - 0.03, nu=44, nv=40, thick=SKIN)
part('face', face, mat='shell', asm='cabeza', parent=head, bevel=0.16, cut=[neck_cut(), beak_cut()], explode=(0, -11, 3), open=(0, -4, 0),
     mats={'orange': lambda c: c.z > HC.z + 3.5 and c.y < HC.y - 3.0})
for sg, sd in ((1, 'L'), (-1, 'R')):
    n, P = EYES[sg]
    e = join(moved(cyl(3.2, 4.5, 'z', 28), at=(0, 0, -1.85)), moved(ring(3.95, 2.5, 0.85, 'z', 32), at=(0, 0, 0.03)),
             moved(lathe([(0, 1.5), (1.2, 1.25), (2.1, 0.7), (2.55, 0.25), (2.55, -0.4), (0, -0.4)], 'z', 28), at=(0, 0, 0.3)))
    part(f'eye_{sd}', e, mat='ink', asm='cabeza', at=P, rot=aim(n), parent=head, bevel=0.1, explode=tuple(n * 9),
         mats={'orange': lambda c: 2.45 < math.hypot(c.x, c.y) and c.z > -0.6, 'lens': lambda c: math.hypot(c.x, c.y) < 2.56 and c.z > 0.26})
    anchor(f'eye{sd}', tuple(P + n * 1.5), head)
BK = 36.0
bk = join(tube([(0, 1.4, 16.05), (0, 1.4, 22), (0, 1.2, 34), (0, 0.2, 52)], lambda t: 2.3 - 1.75 * t ** 0.8, seg=14, smooth=6),
          moved(ring(3.5, 2.25, 1.1, 'z', 28), at=(0, 1.4, 20.6)), moved(box(1.5, 0.9, 3.0), at=(0, -0.95, 23.2)))
part('beak', bk, mat='ink', asm='cabeza', parent=head, explode=(0, 0, 16), mats={'orange': lambda c: c.z > 46.5 or (c.y < -0.4 and c.z < 25)})
anchor('beakTip', (0, 0.3, 51), head)
anchor('gorget', (0, -5, 14), head)

# ------------------------------------------------------------------ tail: seven feathers stacked on the pin
rig_input('spread', 0.0, 1.0, 3, rest=0.5)
ORDER = [3, 2, 4, 1, 5, 0, 6]  # the centre feather on top, then outward, alternating
for layer, i in enumerate(ORDER):
    outline = [(1.6 * math.sin(D(d)), 1.6 * math.cos(D(d))) for d in range(-90, 91, 15)]  # the round root, facing +z
    outline += [(1.6, -1.0), (3.5, -22), (3.3, -26.5), (2.0, -30), (0, -31.4), (-2.0, -30), (-3.3, -26.5), (-3.5, -22), (-1.6, -1.0)]
    f = prism(outline, F_T, 'z')
    _bmesh.ops.transform(f, matrix=Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))), verts=f.verts)  # (a, b, t) → (x = a, y = t, z = b)
    _bmesh.ops.recalc_face_normals(f, faces=f.faces)
    y = TY + STACK / 2 - F_T / 2 - layer * (F_T + F_G)
    o = part(f'feather_{i}', f, mat='shell', asm='cola', at=(0, y, PIN_Z), bevel=0.12, cut=[cyl(0.8, 2, 'y', 16)], explode=((i - 3) * 2.2, -layer * 1.2 + 3, -20),
             mats={('orange' if i % 2 else 'dark'): lambda c: c.z < -25.0})
    joint(o, 'rev', (0, 1, 0), {'k': (i - 3) * D(4), 'c': (i - 3) * D(7)}, input='spread')
anchor('tail', (0, TY, PIN_Z - 26), None)
anchor('body', (0, 0, 0), None)
anchor('hatch', tuple(Vector(torso(math.pi / 2, -9.5)) + Vector((0, 1, 0))), None)

out = argv('--out', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'colibri.glb'))
fails = AUD.audit(os.path.join(os.path.dirname(out), 'audit.json')) if argv('--audit') else 0
export(out)
sys.exit(1 if fails else 0)
