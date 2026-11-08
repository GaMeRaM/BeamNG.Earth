"""Representative Russian roadside scenery on existing road geometry.

Models: exencendre's PR #505 poles/reflector posts, Robitnik's PR #883 lamps.
These are visual presets, not surveyed asset locations or national statistics.
Wire anchors are the pole model's actual local insulator coordinates.
"""
import os
import logging
import time
import numpy as np
import citylamps

log = logging.getLogger('earthd.ruinfra')
_warned_markers = -float('inf')

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
                z = float(p[2])
                # Clearance uses a virtual upright box even though this prop
                # itself has no collision mesh.
                r = [MARKER, *map(float, q), z, (furniture._yaw(d[0], d[1]) + 90. * side) % 360., 1., 1.25, 0.]
                out.append(r)
    if not out:
        return []
    road_z = np.array([r[3] for r in out])
    if ground is None:
        heights = road_z
    else:
        # The production callback is vectorized drawn_ground: it returns an
        # (n,) array, including for a single query. Sample all posts together.
        xy = np.array([r[1:3] for r in out])
        heights = np.asarray(ground(xy[:, 0], xy[:, 1]), np.float64)
        if heights.ndim == 0:
            heights = np.full(len(out), heights.item())
        heights = heights.reshape(-1)
        if len(heights) != len(out):
            raise ValueError('marker terrain heights do not match the queried points')
    keep = []
    for r, z, road in zip(out, heights, road_z):
        if not np.isfinite(z) or abs(z - road) > 2.:
            continue
        r[3] = float(z)
        if clearance.clear(r, margin=.25):
            keep.append(r)
    return keep


def optional_markers(*args, **kwargs):
    """A failed decorative layer must never make a drivable road tile fail."""
    global _warned_markers
    try:
        return markers(*args, **kwargs)
    except Exception as error:
        now = time.monotonic()
        if now - _warned_markers >= 60.:
            _warned_markers = now
            log.warning('Reflector posts skipped; roads continue: %s: %s',
                        type(error).__name__, error, exc_info=True)
        return []
