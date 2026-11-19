"""lamina · Blender side. Models a machine as named, closed, bevelled parts and exports them as one GLB with the
rig (joints, assemblies, explode vectors) in each node's extras, so the page and the audit pose the same model.

Runs inside Blender (`blender -b -P model.py -- --out x.glb`) or with the bpy module (`python model.py`).
Units are millimetres. The scene's axes are the model's: x left, y up, z forward; the GLB is written without the
Y-up conversion, so coordinates in three.js are the ones you type here.

    from tdb import *
    reset()
    P = part('motor_L', cyl(3, 7, axis='x'), mat='ink', asm='transmision', at=(3.2, 0, 0))
    joint(P, 'rev', axis=(1, 0, 0), law={'k': 12})
    export('machine.glb')
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

PARTS = {}  # name -> object
RIG = {'inputs': {}, 'mates': [], 'gears': {}}

MATS = {
    'shell': (0.90, 0.89, 0.86, 0.28, 0.0),
    'orange': (0.87, 0.10, 0.02, 0.35, 0.0),
    'ink': (0.02, 0.02, 0.025, 0.45, 0.3),
    'dark': (0.045, 0.05, 0.055, 0.5, 0.5),
    'steel': (0.33, 0.35, 0.37, 0.35, 0.85),
    'brass': (0.48, 0.30, 0.10, 0.35, 0.85),
    'carbon': (0.012, 0.012, 0.014, 0.35, 0.3),
    'lens': (0.004, 0.005, 0.006, 0.05, 0.0),
    'membrane': (0.78, 0.73, 0.66, 0.35, 0.0),
    'pcb': (0.02, 0.025, 0.027, 0.6, 0.2),
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    PARTS.clear()
    RIG.update({'inputs': {}, 'mates': [], 'gears': {}})
    for name, (r, g, b, rough, metal) in MATS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal


# ------------------------------------------------------------------ mesh builders: each returns a bmesh
def _bm():
    return bmesh.new()


def box(sx, sy, sz):
    bm = _bm()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    return bm


AX = {'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'y': Matrix.Rotation(-math.pi / 2, 4, 'X'), 'z': Matrix.Identity(4)}


def cyl(r, h, axis='z', seg=32, r2=None):
    """a closed cylinder (or cone, r at −h/2 and r2 at +h/2) centred on the origin along axis"""
    bm = _bm()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    bmesh.ops.transform(bm, matrix=AX[axis], verts=bm.verts)
    return bm


def ball(r, seg=32, rings=16):
    bm = _bm()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    return bm


def lathe(profile, axis='z', seg=48):
    """a closed solid of revolution: profile [(radius, height)...] from one end to the other; radius 0 closes on the
    axis, otherwise the ends are capped. A ring (a real bore) is a profile that goes out and back: outer then inner."""
    bm = _bm()
    rings = []
    for r, h in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, h))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), h)) for i in range(seg)])
    closed = profile[0] == profile[-1]
    n = len(rings) - (1 if closed else 0)
    for k in range(len(rings) - 1):
        a, b = rings[k], rings[(k + 1) % n] if closed else rings[k + 1]
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[i], b[0], a[j]))
            else:
                bm.faces.new((a[i], b[i], b[j], a[j]))
    if closed:
        bmesh.ops.delete(bm, geom=rings[-1], context='VERTS')
    else:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=AX[axis], verts=bm.verts)
    return bm


def ring(r_out, r_in, h, axis='z', seg=48):
    return lathe([(r_out, -h / 2), (r_out, h / 2), (r_in, h / 2), (r_in, -h / 2), (r_out, -h / 2)], axis, seg)


def prism(points, h, axis='z'):
    """a closed extrusion of a 2D outline [(a, b)...] by h, centred, along axis"""
    bm = _bm()
    lo = [bm.verts.new((a, b, -h / 2)) for a, b in points]
    hi = [bm.verts.new((a, b, h / 2)) for a, b in points]
    n = len(points)
    bm.faces.new(lo)
    bm.faces.new(hi)
    for i in range(n):
        bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=AX[axis], verts=bm.verts)
    return bm


def gear(teeth, module, thick, bore=0.0, axis='z', phase=0.0):
    """a spur gear with trapezoid teeth and a real bore. Pitch radius teeth·module/2, tip +0.9 m, root −1.1 m."""
    rp = teeth * module / 2
    ro, rr = rp + 0.9 * module, rp - 1.1 * module
    p = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = i * p + phase
        for rad, da in ((rr, -0.5), (rr, -0.30), (ro, -0.13), (ro, 0.13), (rr, 0.30)):
            pts.append((rad * math.cos(a + da * p), rad * math.sin(a + da * p)))
    bm = _bm()
    n = len(pts)
    lo = [bm.verts.new((x, y, -thick / 2)) for x, y in pts]
    hi = [bm.verts.new((x, y, thick / 2)) for x, y in pts]
    for i in range(n):
        bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
    if bore > 0:
        m = teeth
        bl = [bm.verts.new((bore * math.cos(i * p + phase - 0.5 * p), bore * math.sin(i * p + phase - 0.5 * p), -thick / 2)) for i in range(m)]
        bh = [bm.verts.new((v.co.x, v.co.y, thick / 2)) for v in bl]
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((bl[j], bl[i], bh[i], bh[j]))
            for outer, inner in ((lo, bl), (hi, bh)):
                o = [outer[(i * 5 + k) % n] for k in range(6)]
                bm.faces.new((inner[i], inner[j], o[5], o[4], o[3], o[2], o[1], o[0]))
    else:
        bm.faces.new(lo)
        bm.faces.new(hi)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=AX[axis], verts=bm.verts)
    return bm


def rack(teeth, module, thick, back, axis='z'):
    """a rack along `axis` (centred), teeth pointing +x of its own frame, pitch line at x = 0, body back to −back;
    thickness along the remaining axis"""
    p = math.pi * module
    pts = [(-back, -teeth * p / 2), ]
    for i in range(teeth):
        c = (i + 0.5 - teeth / 2) * p
        for x, d in ((-1.1 * module, -0.5), (-1.1 * module, -0.30), (0.9 * module, -0.13), (0.9 * module, 0.13), (-1.1 * module, 0.30)):
            pts.append((x, c + d * p))
    pts += [(-1.1 * module, teeth * p / 2), (-back, teeth * p / 2)]
    bm = prism(pts, thick, 'z')  # outline in (x, y), thickness z
    # own frame (x teeth, y travel, z thickness) → travel along the requested axis
    rot = {'z': Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1))), 'y': Matrix.Identity(4), 'x': Matrix.Rotation(-math.pi / 2, 4, 'Z')}[axis]
    bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    return bm


def tube(points, r, seg=10, smooth=4):
    """a closed tube along a polyline (Catmull-Rom smoothed `smooth` steps per span), radius r or a function of 0..1"""
    pts = [Vector(p) for p in points]
    if smooth > 1 and len(pts) > 2:
        out = []
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
            for s in range(smooth):
                t = s / smooth
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        out.append(pts[-1])
        pts = out
    bm = _bm()
    rings = []
    up = Vector((0, 1, 0))
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if abs(t.dot(up)) > 0.95:
            up = Vector((1, 0, 0))
        a = t.cross(up).normalized()
        b = t.cross(a).normalized()
        up = a.cross(t) * -1 if False else up
        rr = r(i / (len(pts) - 1)) if callable(r) else r
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * rr) for k in range(seg)])
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def spline(xs, ys):
    """a smooth function through (xs, ys): monotone-safe cubic Hermite (Catmull-Rom tangents)"""
    n = len(xs)

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(k for k in range(n - 1) if xs[k] <= x)
        h = xs[i + 1] - xs[i]
        t = (x - xs[i]) / h
        m0 = (ys[i + 1] - ys[i - 1]) / (xs[i + 1] - xs[i - 1]) if i > 0 else (ys[1] - ys[0]) / (xs[1] - xs[0])
        m1 = (ys[i + 2] - ys[i]) / (xs[i + 2] - xs[i]) if i < n - 2 else (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        return (2 * t ** 3 - 3 * t * t + 1) * ys[i] + (t ** 3 - 2 * t * t + t) * h * m0 + (-2 * t ** 3 + 3 * t * t) * ys[i + 1] + (t ** 3 - t * t) * h * m1
    return f


def patch(surf, u0, u1, v0, v1, nu=28, nv=28, thick=0.7):
    """a panel of an analytic surface surf(u, v) -> (x, y, z), cut along parameter lines and given real thickness
    (inward, along −normal). Closed, ready for a bevel. This is how a shell is split into panels: the gaps are the
    parameter ranges you leave out."""
    bm = _bm()
    grid = [[Vector(surf(u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
    e = 1e-3

    def normal(i, j):
        u, v = u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv
        du = Vector(surf(u + e, v)) - Vector(surf(u - e, v))
        dv = Vector(surf(u, v + e)) - Vector(surf(u, v - e))
        n = du.cross(dv)
        return n.normalized() if n.length > 1e-12 else Vector((0, 0, 0))
    nrm = [[normal(i, j) for j in range(nv + 1)] for i in range(nu + 1)]
    # orient: the normal must point away from the surface's axis (decided by the caller's parametrisation); flip by a probe
    out = [[bm.verts.new(grid[i][j]) for j in range(nv + 1)] for i in range(nu + 1)]
    inn = [[bm.verts.new(grid[i][j] - nrm[i][j] * thick) for j in range(nv + 1)] for i in range(nu + 1)]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((out[i][j], out[i + 1][j], out[i + 1][j + 1], out[i][j + 1]))
            bm.faces.new((inn[i][j], inn[i][j + 1], inn[i + 1][j + 1], inn[i + 1][j]))
    for i in range(nu):
        bm.faces.new((out[i][0], inn[i][0], inn[i + 1][0], out[i + 1][0]))
        bm.faces.new((out[i][nv], out[i + 1][nv], inn[i + 1][nv], inn[i][nv]))
    for j in range(nv):
        bm.faces.new((out[0][j], out[0][j + 1], inn[0][j + 1], inn[0][j]))
        bm.faces.new((out[nu][j], inn[nu][j], inn[nu][j + 1], out[nu][j + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def carve(bm, cutters):
    """bm minus the cutters (exact booleans), as a new bmesh: cut a piece before welding it into a part"""
    me = bpy.data.meshes.new('carve')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('carve', me)
    bpy.context.scene.collection.objects.link(ob)
    tmp = []
    for c in cutters:
        cme = bpy.data.meshes.new('carve_c')
        c.to_mesh(cme)
        c.free()
        cob = bpy.data.objects.new('carve_c', cme)
        bpy.context.scene.collection.objects.link(cob)
        m = ob.modifiers.new('cut', 'BOOLEAN')
        m.operation, m.solver, m.object = 'DIFFERENCE', 'EXACT', cob
        tmp.append(cob)
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    out = _bm()
    out.from_mesh(new)
    for o in tmp + [ob]:
        bpy.data.objects.remove(o)
    bpy.data.meshes.remove(new)
    return out


def join(*bms):
    """several bmeshes as one mesh (one part: fused details may overlap each other, the audit is between parts)"""
    out = _bm()
    for b in bms:
        me = bpy.data.meshes.new('tmp')
        b.to_mesh(me)
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        b.free()
    return out


def moved(bm, at=(0, 0, 0), rot=None, scale=None):
    if scale is not None:
        bmesh.ops.scale(bm, vec=scale if hasattr(scale, '__len__') else (scale,) * 3, verts=bm.verts)
    if rot is not None:
        bmesh.ops.transform(bm, matrix=rot if isinstance(rot, Matrix) else Matrix.Rotation(rot[1], 4, Vector(rot[0])), verts=bm.verts)
    bmesh.ops.translate(bm, vec=at, verts=bm.verts)
    return bm


def aim(direction, up=(0, 1, 0)):
    """a rotation taking +z to `direction`"""
    return Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()


# ------------------------------------------------------------------ parts
def _mat(name):
    return bpy.data.materials[name]


def part(name, bm, mat='shell', asm='general', at=(0, 0, 0), rot=None, parent=None, bevel=0.0, cut=None, explode=None, open=None, sharp=40, mats=None):
    """Register a part. `bm` is in the part's own frame (its origin is its pivot); `at`/`rot` place that frame in the
    parent's. bevel rounds every sharp edge by that many mm. cut: [bmesh...] subtracted (exact booleans, cutters in
    the part's frame). explode/open: vectors in the parent's frame the part travels in the exploded view / when its
    assembly opens. mats: {material: face-predicate(centre)} to paint regions of one part."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(_mat(mat))
    if mats:
        for k, (mname, pred) in enumerate(mats.items()):
            me.materials.append(_mat(mname))
            for f in me.polygons:
                if pred(f.center):
                    f.material_index = k + 1
    mods = False
    for k, c in enumerate(cut or []):
        cme = bpy.data.meshes.new(f'{name}_cut{k}')
        c.to_mesh(cme)
        c.free()
        cob = bpy.data.objects.new(f'{name}_cut{k}', cme)
        bpy.context.scene.collection.objects.link(cob)
        m = ob.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = cob
        mods = True
    if bevel > 0:
        m = ob.modifiers.new('bevel', 'BEVEL')
        m.width = bevel
        m.segments = 2
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(sharp)
        mods = True
    if mods:
        dg = bpy.context.evaluated_depsgraph_get()
        new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        old = ob.data
        ob.data = new
        new.name = name
        bpy.data.meshes.remove(old)
        for o in [o for o in bpy.data.objects if o.name.startswith(f'{name}_cut')]:
            bpy.data.objects.remove(o)
    # smooth shading with sharp edges past the angle
    me = ob.data
    b2 = bmesh.new()
    b2.from_mesh(me)
    for f in b2.faces:
        f.smooth = True
    for e in b2.edges:
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0) < math.radians(sharp)
    b2.to_mesh(me)
    b2.free()
    ob.rotation_mode = 'QUATERNION'
    ob.location = at
    if rot is not None:
        ob.rotation_quaternion = (rot if isinstance(rot, Matrix) else Matrix.Rotation(rot[1], 4, Vector(rot[0]))).to_quaternion()
    if parent is not None:
        ob.parent = parent
    td = {'asm': asm}
    if explode is not None:
        td['explode'] = list(explode)
    if open is not None:
        td['open'] = list(open)
    ob['td'] = json.dumps(td)
    PARTS[name] = ob
    return ob


def frame(name, at=(0, 0, 0), rot=None, parent=None, asm=None, explode=None, open=None):
    """an empty: a frame other parts hang from (a joint's moving frame, an assembly that explodes as one)"""
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    ob.location = at
    if rot is not None:
        ob.rotation_quaternion = (rot if isinstance(rot, Matrix) else Matrix.Rotation(rot[1], 4, Vector(rot[0]))).to_quaternion()
    if parent is not None:
        ob.parent = parent
    td = {}
    if asm:
        td['asm'] = asm
    if explode is not None:
        td['explode'] = list(explode)
    if open is not None:
        td['open'] = list(open)
    ob['td'] = json.dumps(td)
    PARTS[name] = ob
    return ob


def _td(ob, **kw):
    td = json.loads(ob['td'])
    td.update(kw)
    ob['td'] = json.dumps(td)


def joint(ob, kind, axis, law, input='phase'):
    """ob moves in its parent's frame: kind 'rev' (radians about axis) or 'slide' (mm along axis), by
    value = k·q + a·sin(h·q + p) + c + b·tanh(g·cos q), q the named input.
    law keys: k | sin: [a, h, p] | c | tanh: [b, g]. The page (kit/rig.js) and the audit read this same law."""
    _td(ob, joint={'kind': kind, 'axis': list(axis), 'law': law, 'input': input})


def anchor(name, at, parent=None):
    """a named point for callouts and cameras"""
    ob = bpy.data.objects.new('@' + name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = at
    if parent is not None:
        ob.parent = parent
    ob['td'] = json.dumps({'anchor': name})
    return ob


def rig_input(name, lo, hi, samples, rest=0.0, cyclic=False):
    """declare an input the audit sweeps: `samples` poses from lo to hi"""
    RIG['inputs'][name] = {'lo': lo, 'hi': hi, 'samples': samples, 'rest': rest, 'cyclic': cyclic}


def mate(a, b, depth=0.0, why=''):
    """a and b touch by design (meshing teeth, a pin in a slot): the audit allows them to overlap up to `depth` mm"""
    RIG['mates'].append({'a': a, 'b': b, 'depth': depth, 'why': why})


def gear_info(name, teeth, module, axis_point, axis_dir, rack=False):
    """declare a gear (or a rack) so the audit checks centre distances and ratios of every mate between two of them"""
    RIG['gears'].setdefault(name, []).append({'teeth': teeth, 'module': module, 'point': list(axis_point), 'dir': list(axis_dir), 'rack': rack})


def export(path):
    scene = bpy.context.scene
    scene['td_rig'] = json.dumps(RIG)
    # the rig rides on a root empty so it reaches the GLB's extras
    root = bpy.data.objects.new('td_root', None)
    scene.collection.objects.link(root)
    root['td'] = json.dumps({'rig': RIG})
    for ob in list(scene.collection.objects):
        if ob is not root and ob.parent is None:
            ob.parent = root
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_yup=False, export_extras=True, export_apply=False,
                              export_materials='EXPORT', export_normals=True, export_texcoords=False, export_animations=False)
    tris = sum(len(o.data.loop_triangles) if (o.data.calc_loop_triangles() or True) else 0 for o in scene.objects if o.type == 'MESH')
    print(f'exported {path} · {sum(1 for o in scene.objects if o.type == "MESH")} parts · {tris} tris')


def argv(flag, default=None):
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    if flag in a:
        i = a.index(flag)
        return a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else True
    return default
