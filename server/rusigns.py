"""Russian highway exit panels: posted OSM destinations, Cyrillic faces, existing safe placement.

These do not invent destinations, exit numbers or mile markers. They reuse the metric
exit planner, but never the American lettering/shields. Inferred junction guides are
separate (dirsigns), so turning them off does not remove mapped highway exit panels.
"""
import re
import numpy as np
import exitsigns
import highwaysigns
import roads


def route_ref(ref):
    ref = str(ref).strip()
    if re.match(r'^[MPA]\s*-?\s*\d', ref, re.I):
        ref = ref[0].upper().translate(str.maketrans('MPA', 'МРА')) + ref[1:]
    return ref


def content(sign):
    label = sign['label']
    names = [str(n).strip() for n in label.get('names', []) if str(n).strip()][:3]
    if not names:
        return None
    marks = []
    if label.get('ref'):
        marks.append(('exit', 'СЪЕЗД ' + str(label['ref'])))
    for raw in label.get('routes', [])[:3]:
        ref = route_ref(raw)
        if ref:
            marks.append(('e' if re.match(r'^E\s*\d', ref) else 'national', ref))
    turn = 0 if sign['kind'] == 'ramp' else int(sign.get('side', 1))
    return turn, marks, [(n, '', '') for n in names]


def join_meshes(meshes):
    if not meshes:
        return None
    if len(meshes) == 1:
        return meshes[0]
    points, tris, uvs, indices, materials = [], [], [], [], []
    offset = 0
    for p, t, uv, names, mi in meshes:
        remap = []
        for name in names:
            if name not in materials:
                materials.append(name)
            remap.append(materials.index(name))
        points.append(p)
        tris.append(np.asarray(t) + offset)
        uvs.append(uv)
        indices.append(np.asarray(remap, np.int64)[np.asarray(mi, np.int64)])
        offset += len(p)
    return np.vstack(points), np.vstack(tris), np.vstack(uvs), materials, np.concatenate(indices)


def build_tile(md, frame, tx, ty, elev, context, decks, left_hand, out_dir, vfs_dir):
    source = getattr(md, 'highway_signs', None)
    if source is None:
        return None, {}
    box = roads.tile_bbox(tx, ty)
    objects = highwaysigns.tile_objects(source, frame, tx, ty)
    placed = []
    for obj in sorted(objects, key=lambda o: str(o['id'])):
        if not obj.get('exit'):
            continue
        pavements, mains = exitsigns.source_pavements(frame, obj, context, left_hand)
        for sign in exitsigns.place(frame, [obj], (), box, elev, decks, left_hand, False,
                                    pavements=pavements, ramp_mains=mains):
            near = exitsigns._nearest(np.asarray(sign['road_point']), pavements)
            sign['board_kind'] = 'freeway' if near is not None and near[2].cls == 'motorway' else 'road'
            placed.append(sign)
    return render(placed, box, out_dir, vfs_dir)


def render(placed, box, out_dir, vfs_dir):
    import dirsigns
    if not placed:
        return None, {}
    dirsigns.fast.require(dirsigns.KERNEL, 'Russian highway signs')
    dirsigns._set_fonts()
    doc = dirsigns.styles()
    style = doc['countries']['RU']
    materials, faces, rows, seen = [dirsigns.METAL], {}, [], set()
    for sign in placed:
        if len(faces) >= dirsigns.MAX_FACES:
            break
        key = sign['id'], sign['kind'], sign.get('distance', '')
        if key in seen:
            continue
        seen.add(key)
        line = content(sign)
        if line is None:
            continue
        plate_keys = sorted({k for k, _ in line[1]})
        face = dict(doc['face'], max_w_m=min(6., sign['width']), min_w_m=min(2., sign['width']))
        name, tex, w, h = dirsigns._face(out_dir, vfs_dir, style, plate_keys, sign.get('board_kind', 'road'), [line], face)
        if name not in materials:
            materials.append(name)
            faces[name] = tex
        x, y, ground = sign['centre']
        rows.append([x, y, ground, sign['bottom'], *sign['travel'], w, h, materials.index(name), 0.])
    if not rows:
        return None, {}
    p, t, uv, mi = dirsigns.fast._ef.dirsign_mesh(np.ascontiguousarray(rows, np.float64), [box[0], box[1], 0.])
    return (p, t, uv, materials, mi), faces
