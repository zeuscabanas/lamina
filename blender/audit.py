"""lamina · the geometry audit. Call audit() at the end of a model script (after every part exists), or run
`python model.py --audit`. It poses the model through every declared input with the same joint laws the page uses
and proves, with the real meshes:

  interference   no two parts pass through each other, at rest, at every sampled pose, and exploded
                 (declared mates may overlap up to their depth: meshing teeth, a pin in its slot)
  support        every part touches another one, and all of them hang together as one assembly
  gears          every mate between two declared gears has centre distance (z1 + z2)·m / 2 and inverse ratio;
                 a rack's travel is the pinion's angle times its pitch radius
  closed         every part is a closed volume (a thin sheet has real thickness)

It prints one line per check and a list of the failures, writes audit.json, and returns the number of problems.
Nothing is done until it prints `audit passed`.
"""
import itertools
import json
import math

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

import tdb

TOUCH = 0.3  # mm: closer than this is contact, for the support graph
SKIN = 0.02  # mm: overlaps shallower than this are flush contact


def law_value(law, q):
    v = law.get('k', 0.0) * q + law.get('c', 0.0)
    if 'sin' in law:
        a, h, p = law['sin']
        v += a * math.sin(h * q + p)
    if 'tanh' in law:
        b, g = law['tanh']
        v += b * math.tanh(g * math.cos(q))
    return v


class Model:
    def __init__(self):
        self.objs = [o for o in bpy.context.scene.objects if 'td' in o.keys()]
        self.td = {o.name: json.loads(o['td']) for o in self.objs}
        self.rest = {o.name: (o.location.copy(), o.rotation_quaternion.copy()) for o in self.objs}
        self.meshes = [o for o in self.objs if o.type == 'MESH']
        self.local = {}
        for o in self.meshes:
            me = o.data
            me.calc_loop_triangles()
            self.local[o.name] = ([v.co.copy() for v in me.vertices], [tuple(t.vertices) for t in me.loop_triangles])
        self.jointed = [o for o in self.objs if 'joint' in self.td[o.name]]

    def pose(self, inputs, explode=0.0):
        for o in self.objs:
            loc, q = self.rest[o.name]
            td = self.td[o.name]
            loc = loc.copy()
            q = q.copy()
            j = td.get('joint')
            if j:
                v = law_value(j['law'], inputs.get(j['input'], 0.0))
                ax = Vector(j['axis'])
                if j['kind'] == 'rev':
                    q = q @ Quaternion(ax, v)
                else:
                    loc = loc + (q @ ax) * v
            if explode and 'explode' in td:
                loc = loc + Vector(td['explode']) * explode
            o.location = loc
            o.rotation_quaternion = q
        bpy.context.view_layer.update()

    def moving(self, name):
        """the inputs that move this part (its own joint or any ancestor's)"""
        o = bpy.data.objects[name]
        s = set()
        while o is not None:
            j = self.td.get(o.name, {}).get('joint')
            if j:
                s.add(j['input'])
            o = o.parent
        return s

    def world(self, o):
        vs, polys = self.local[o.name]
        m = o.matrix_world
        w = [m @ v for v in vs]
        return w, polys


def _bbox(w):
    xs, ys, zs = zip(*w)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _apart(a, b, pad=0.0):
    return a[0] > b[3] + pad or b[0] > a[3] + pad or a[1] > b[4] + pad or b[1] > a[4] + pad or a[2] > b[5] + pad or b[2] > a[5] + pad


_RAYS = [Vector(d).normalized() for d in ((0.577, 0.211, 0.789), (-0.331, 0.872, 0.361), (0.412, -0.593, -0.692))]


def _inside(tree, p):
    """p is inside the solid behind `tree`. Along a ray, surfaces left minus surfaces entered is the number of
    shells p is in, so a part welded from overlapping closed shells works too. Three skewed rays, by majority (one
    ray can graze an edge between two triangles and count it twice)."""
    votes = 0
    for d in _RAYS:
        n = 0
        o = p
        for _ in range(96):
            hit = tree.ray_cast(o, d)
            if hit[0] is None:
                break
            n += 1 if hit[1].dot(d) > 0 else -1
            o = hit[0] + d * 1e-4
        votes += 1 if n > 0 else 0
    return votes >= 2


def _depth(wa, ta, wb, tb, limit=900):
    """how deep two overlapping closed meshes go into each other: the deepest vertex of one inside the other"""
    deep = 0.0
    where = None
    for w, tree_self, tree_other in ((wa, ta, tb), (wb, tb, ta)):
        step = max(1, len(w) // limit)
        cand = []
        for v in w[::step]:
            near = tree_other.find_nearest(v, 3.0)
            if near[0] is not None:
                cand.append((near[3], v))
        cand.sort(key=lambda c: c[0])
        for dist, v in cand[::-1]:
            if dist <= deep:
                break
            if _inside(tree_other, v):
                deep = dist
                where = v
                break
    return deep, where


def audit(out='audit.json', quiet=False):
    M = Model()
    rig = tdb.RIG
    names = [o.name for o in M.meshes]
    mates = {}
    for m in rig['mates']:
        mates[frozenset((m['a'], m['b']))] = m['depth']
    problems = []
    report = {'parts': len(names), 'checks': {}}

    # ---------------------------------------------------------------- closed
    open_parts = []
    for o in M.meshes:
        edges = {}
        for p in o.data.polygons:
            vs = p.vertices
            for i in range(len(vs)):
                k = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
                edges[k] = edges.get(k, 0) + 1
        bad = sum(1 for c in edges.values() if c != 2)
        if bad:
            open_parts.append(f'{o.name}: {bad} open or non-manifold edges')
    report['checks']['closed'] = open_parts
    problems += [('closed', p) for p in open_parts]

    # ---------------------------------------------------------------- poses
    rest_in = {k: v['rest'] for k, v in rig['inputs'].items()}
    poses = [('rest', dict(rest_in), 0.0)]
    for k, v in rig['inputs'].items():
        n = v['samples']
        for i in range(n):
            q = v['lo'] + (v['hi'] - v['lo']) * (i / n if v['cyclic'] else i / max(1, n - 1))
            d = dict(rest_in)
            d[k] = q
            poses.append((f'{k}={q:.3f}', d, 0.0))
    poses.append(('apart', dict(rest_in), 1.0))

    moving = {n: M.moving(n) for n in names}
    worst = {}  # pair -> (depth, pose)
    tested = 0
    cache_static = {}
    for label, inputs, ex in poses:
        M.pose(inputs, ex)
        active = None if label in ('rest', 'apart') else label.split('=')[0]
        W, T, B = {}, {}, {}
        for o in M.meshes:
            if active and active not in moving[o.name] and o.name in cache_static:
                W[o.name], T[o.name], B[o.name] = cache_static[o.name]
                continue
            w, polys = M.world(o)
            W[o.name], T[o.name], B[o.name] = w, BVHTree.FromPolygons(w, polys, epsilon=0.0), _bbox(w)
            if label == 'rest':
                cache_static[o.name] = (W[o.name], T[o.name], B[o.name])
        for a, b in itertools.combinations(names, 2):
            if active and active not in moving[a] and active not in moving[b]:
                continue  # neither moved in this pose: the rest pose covered the pair
            if _apart(B[a], B[b]):
                continue
            tested += 1
            if not T[a].overlap(T[b]):
                continue
            d, at = _depth(W[a], T[a], W[b], T[b])
            if at is None:
                i0 = T[a].overlap(T[b])[0][0]
                at = sum((W[a][k] for k in M.local[a][1][i0]), Vector()) / 3
            allow = mates.get(frozenset((a, b)), 0.0)
            if d > allow + SKIN or (d == 0.0 and allow == 0.0):
                key = (a, b)
                if key not in worst or d > worst[key][0]:
                    worst[key] = (d, label, at)
        if label == 'rest':
            RW, RT, RB = dict(W), dict(T), dict(B)
    inter = [f'{a} × {b}: {"crosses" if d == 0 else f"{d:.2f} mm deep"} at {lab}, near ({at.x:.1f}, {at.y:.1f}, {at.z:.1f})' for (a, b), (d, lab, at) in sorted(worst.items(), key=lambda kv: -kv[1][0])]
    report['checks']['interference'] = inter
    problems += [('interference', p) for p in inter]

    # ---------------------------------------------------------------- support: a contact graph at rest
    M.pose(rest_in, 0.0)
    adj = {n: set() for n in names}
    for a, b in itertools.combinations(names, 2):
        if _apart(RB[a], RB[b], TOUCH):
            continue
        touch = bool(RT[a].overlap(RT[b]))
        if not touch:
            for w, t in ((RW[a], RT[b]), (RW[b], RT[a])):
                step = max(1, len(w) // 1500)
                if any(t.find_nearest(v, TOUCH)[0] is not None for v in w[::step]):
                    touch = True
                    break
        if touch:
            adj[a].add(b)
            adj[b].add(a)
    floating = [n for n in names if not adj[n]]
    seen = set()
    islands = []
    for n in names:
        if n in seen:
            continue
        comp, stack = [], [n]
        seen.add(n)
        while stack:
            c = stack.pop()
            comp.append(c)
            for d in adj[c]:
                if d not in seen:
                    seen.add(d)
                    stack.append(d)
        islands.append(comp)
    islands.sort(key=len, reverse=True)
    sup = [f'{n}: touches nothing (within {TOUCH} mm)' for n in floating]
    sup += [f'island of {len(c)} not joined to the rest: {", ".join(sorted(c)[:6])}{"…" if len(c) > 6 else ""}' for c in islands[1:] if len(c) > 1]
    report['checks']['support'] = sup
    problems += [('support', p) for p in sup]

    # ---------------------------------------------------------------- gears
    gp = []
    G = rig['gears']

    def world_axis(name, g):
        o = bpy.data.objects[name]
        base = o.parent.matrix_world if o.parent else Matrix.Identity(4)
        return base @ Vector(g['point']), (base.to_3x3() @ Vector(g['dir'])).normalized()
    for m in rig['mates']:
        a, b = m['a'], m['b']
        if a not in G or b not in G:
            continue
        # a part may carry several gears (a compound): the pair that is in mesh is the one whose geometry fits
        def fit(ga, gb):
            if ga['rack'] or gb['rack']:
                return 0
            pa_, da_ = world_axis(a, ga)
            pb_, _ = world_axis(b, gb)
            d_ = pb_ - pa_
            return abs((d_ - da_ * d_.dot(da_)).length - (ga['teeth'] + gb['teeth']) * ga['module'] / 2)
        ga, gb = min(((x, y) for x in G[a] for y in G[b]), key=lambda xy: fit(*xy))
        if abs(ga['module'] - gb['module']) > 1e-6:
            gp.append(f'{a} × {b}: modules differ ({ga["module"]} vs {gb["module"]})')
        ja, jb = M.td[a].get('joint'), M.td[b].get('joint')
        if ga['rack'] or gb['rack']:
            rk, pn = (a, b) if ga['rack'] else (b, a)
            jr, jp = M.td[rk].get('joint'), M.td[pn].get('joint')
            gpn = gb if ga['rack'] else ga
            r = gpn['teeth'] * gpn['module'] / 2
            pa, da = world_axis(pn, gb if ga['rack'] else ga)
            pr, dr = world_axis(rk, ga if ga['rack'] else gb)  # a point on the pitch line, the travel direction
            dist = ((pr - pa) - dr * (pr - pa).dot(dr))
            dist = (dist - da * dist.dot(da)).length
            if abs(dist - r) > 0.03:
                gp.append(f'{rk} × {pn}: pitch line {dist:.2f} mm from the pinion axis, should be {r:.2f}')
            if jr and jp:
                ar, ap = jr['law'].get('sin', [0])[0], jp['law'].get('sin', [0])[0]
                if abs(abs(ar) - abs(ap) * r) > 0.02:
                    gp.append(f'{rk} × {pn}: rack travel ±{abs(ar):.2f} mm but pinion ±{abs(ap):.3f} rad × r {r:.2f} = ±{abs(ap) * r:.2f}')
            continue
        pa, da = world_axis(a, ga)
        pb, db = world_axis(b, gb)
        if abs(abs(da.dot(db)) - 1) > 1e-3:
            gp.append(f'{a} × {b}: axes not parallel')
            continue
        d = pb - pa
        dist = (d - da * d.dot(da)).length
        want = (ga['teeth'] + gb['teeth']) * ga['module'] / 2
        if abs(dist - want) > 0.03:
            gp.append(f'{a} × {b}: centre distance {dist:.2f} mm, should be {want:.2f} ((z1+z2)·m/2)')
        if ja and jb:
            ka, kb = ja['law'].get('k', 0) * (1 if Vector(ja['axis']).dot(Vector(ga['dir'])) > 0 else -1), jb['law'].get('k', 0) * (1 if Vector(jb['axis']).dot(Vector(gb['dir'])) > 0 else -1)
            sign = 1 if da.dot(db) > 0 else -1
            if abs(ka * ga['teeth'] + sign * kb * gb['teeth']) > 1e-6:
                gp.append(f'{a} × {b}: speeds {ka:g} and {kb:g} do not match teeth {ga["teeth"]}:{gb["teeth"]}')
    report['checks']['gears'] = gp
    problems += [('gears', p) for p in gp]

    for o in M.objs:  # leave the scene as it was built: the export must not carry a pose
        o.location, o.rotation_quaternion = M.rest[o.name]
    bpy.context.view_layer.update()
    report['poses'] = len(poses)
    report['pairs_tested'] = tested
    report['problems'] = len(problems)
    with open(out, 'w') as f:
        json.dump(report, f, indent=1)
    if not quiet:
        for k in ('closed', 'interference', 'support', 'gears'):
            print(f'{k}: {len(report["checks"][k])} problems')
            for p in report['checks'][k][:40]:
                print('   ', p)
        print(f'audit · {len(names)} parts · {len(poses)} poses · {tested} pair tests')
        print('audit passed' if not problems else f'audit failed: {len(problems)} problems')
    return len(problems)
