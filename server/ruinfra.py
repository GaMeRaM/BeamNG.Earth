"""Representative Russian roadside scenery on existing road geometry.

Models: exencendre's PR #505 poles/reflector posts, Robitnik's PR #883 lamps.
These are visual presets, not surveyed asset locations or national statistics.
Wire anchors are the pole model's actual local insulator coordinates.
"""
import os
import numpy as np
import citylamps

ON = os.environ.get('BNE_RU_INFRA', 'on') == 'on'
POLE = 'ru_pole_concrete'
MARKER = 'ru_delineator'
BRACKET = 'ru_pole_lamp'
POLE_H = 8.5
WIRE_ANCHORS = ((-.55, 0., 8.08), (.55, 0., 7.45), (-.55, 0., 6.82))
COLLISION_BOXES = {
    POLE: (POLE_H, ((-.22, -.22, -.2, .22, .22, 6.45),
                   (-.80, -.25, 6.45, .80, .25, 8.50))),
    BRACKET: (9., ((-.15, -.15, 8.10, 2.70, .20, 8.95),)),
    **citylamps.COLLISION_BOXES,
}


def enabled(country):
    return ON and str(country or '').upper() == 'RU'


def localize(rows):
    out = []
    for row in rows:
        r = list(row)
        if r[0] == 'pole':
            r[0], r[6] = POLE, POLE_H
        elif r[0] == 'streetlight':
            r[0] = citylamps.group_for('RU', r[1], r[2])
        elif r[0] == 'polelamp':
            # The stock attachment is relative to the head; this model uses
            # the same ground origin as the pole and faces towards the road.
            import furniture
            r[0], r[3], r[4], r[6] = BRACKET, r[3] - furniture.POLE_LAMP_Z, (r[4] + 180.) % 360., 9.
        out.append(r)
    return out


def markers(roads, box, clearance, ground=None):
    """Inferred reflector posts on paved rural main roads, outside carriageways.

    No posts on links or near segment ends/junctions; ownership and a stable
    phase preserve them across tiles. Render-only, with no vehicle collider.
    """
    import furniture
    out = []
    for fid, spec, line, _ in roads:
        if spec.urban or spec.link or spec.kind != 'paved' or spec.cls not in {'motorway', 'trunk', 'primary', 'secondary'}:
            continue
        line = np.asarray(line)
        if len(line) < 2:
            continue
        length = furniture._arclen(line)[-1]
        phase = furniture._h01(fid, 'ru-marker') * 50.
        distances = phase + np.arange(0., length, 50.)
        distances = distances[(distances > 35.) & (distances < length - 35.)]
        pts, dirs = furniture._at(line, distances)
        for side in (-1, 1):
            for p, d in zip(pts, dirs):
                n = np.array([-d[1], d[0]]) * side
                q = p[:2] + n * (spec.width / 2 + 1.0)
                if not furniture._owns(box, *q):
                    continue
                z = float(ground(q[0], q[1])) if ground is not None else float(p[2])
                if not np.isfinite(z) or abs(z - p[2]) > 2.:
                    continue
                # Clearance uses a virtual upright box even though this prop
                # itself has no collision mesh.
                r = [MARKER, *map(float, q), z, (furniture._yaw(d[0], d[1]) + 90. * side) % 360., 1., 1.25, 0.]
                if clearance.clear(r, margin=.25):
                    out.append(r)
    return out
