"""Replay reported bridge sites against the actual generated collision mesh.

Run with the downloaded Overture/DEM cache; this is a live-data audit, not a
network-dependent unit test. A report below the truck-clearance threshold exits
nonzero, so release checks can distinguish source/geometry failures from green
synthetic tests. Heights remain inferred from the DEM, not surveyed measurements.
"""
import argparse
import json
import logging
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import blockworker
import geodesy
import roads
import roadmesh

SITES = {
    'deryabina': (56.81400, 60.55128),
    'metallurgov': (56.82547, 60.56169),  # actual bridge, east of the car's screenshot coordinate
    'islamov': (56.82707, 60.51352),
    'makarov': (56.84869, 60.59025),
    'west-low': (56.83320, 60.32078),
    'west-missing': (56.83547, 60.29000),
    'west-rail': (56.84325, 60.24343),
}


def vertical_hits(mesh, points, offset):
    if mesh is None:
        return [np.empty(0) for _ in points]
    p, t = mesh[:2]
    p = np.asarray(p) + np.asarray(offset)
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    def cross(a, b):
        return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]
    det = cross(b[:, :2] - a[:, :2], c[:, :2] - a[:, :2])
    keep = np.abs(det) > 1e-9
    a, b, c, det = a[keep], b[keep], c[keep], det[keep]
    result = []
    for q in points:
        u = cross(b[:, :2] - q, c[:, :2] - q) / det
        v = cross(c[:, :2] - q, a[:, :2] - q) / det
        w = 1. - u - v
        hit = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8)
        result.append(u[hit] * a[hit, 2] + v[hit] * b[hit, 2] + w[hit] * c[hit, 2])
    return result


def audit(name, cache):
    lat, lon = SITES[name]
    frame = geodesy.EnuFrame(lat, lon)
    state = blockworker._s
    aid = list(SITES).index(name) + 1
    grader, _ = state.anchor(aid, lat, lon)
    found, seen, grades, clearances, lane_rails = [], set(), [], [], []
    for tx, ty in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
        part = blockworker._tile_parts(lambda stage: None, frame, (tx, ty), 16, grader,
                                      False, False, False, False, 0., None, 'RU', None,
                                      (aid, lat, lon), (lat, lon))
        cells = [state.md.cell(k, layers=('roads',), kind='demand').layers.get('roads')
                 for k in roads.cells_of_tile(frame, tx, ty)]
        decks = list(part.bridges.parts(cells, roads.tile_bbox(tx, ty)))
        decks = roads.shifted_parts(decks, roads.deck_shift_fn(
            frame, cells, state.surface.urban if state.surface is not None else None, state.widths, False))
        ground = {}
        for f in cells:
            if f is None:
                continue
            specs = roads.road_specs(f)
            for i, fid in enumerate(f.ids):
                sp = specs[i]
                if sp is None:
                    continue
                for j, line in enumerate(roads._raw_ground_parts(f, i)):
                    e, n, _ = frame.geodetic_to_enu(np.asarray(line)[:, 1], np.asarray(line)[:, 0], 0.)
                    ground[str(fid), j] = (sp, np.c_[e, n])
        for fid, spec, xy, z, _ in decks:
            xy, z = np.asarray(xy), np.asarray(z)
            if np.linalg.norm(np.maximum(np.maximum(xy.min(0), -xy.max(0)), 0)) > 200.:
                continue
            key = (str(fid), tuple(np.round(xy[0], 2)))
            if key not in seen:
                seen.add(key)
                arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
                grade = float(np.max(np.abs(np.diff(z) / np.maximum(np.diff(arc), 1e-9))))
                grades.append(grade)
                found.append({'fid': str(fid), 'length_m': round(float(arc[-1]), 2), 'max_grade': round(grade, 4)})
            for row in part.guardrail_rows:
                if not isinstance(row[0], int) or row[0] > 8:
                    continue
                p = np.asarray(row[1:3])
                delta = np.diff(xy, axis=0)
                length2 = np.maximum(np.sum(delta * delta, axis=1), 1e-9)
                raw_at = np.sum((p - xy[:-1]) * delta, axis=1) / length2
                at = np.clip(raw_at, 0., 1.)
                d = np.linalg.norm(p - (xy[:-1] + at[:, None] * delta), axis=1)
                j = int(np.argmin(d))
                level = z[j] + at[j] * (z[j + 1] - z[j])
                if (0. <= raw_at[j] <= 1. and 1.5 < d[j] < spec.width / 2 - 1.
                        and abs(row[3] - level) < .3):
                    lane_rails.append({'bridge': str(fid), 'xyz': row[1:4]})
            for (other, j), (sp, line) in ground.items():
                for _, arc, q in roads._crossings_by([xy], [line])[0]:
                    length = roads._length(xy)
                    if arc < 5. or arc > length - 5.:
                        continue
                    q = np.asarray(q)
                    if not (tx * 256. <= q[0] < (tx + 1) * 256. and ty * 256. <= q[1] < (ty + 1) * 256.):
                        continue
                    # The lower carriageway's tyre/body envelope, across its lanes.
                    d = np.diff(line, axis=0)
                    a = line[:-1]
                    t = np.clip(((q - a) * d).sum(1) / np.maximum((d * d).sum(1), 1e-9), 0., 1.)
                    k = int(np.argmin(np.linalg.norm(a + t[:, None] * d - q, axis=1)))
                    u = d[k] / np.linalg.norm(d[k])
                    normal = np.array([-u[1], u[0]])
                    pts = np.array([q + normal * side + u * along for side in (-sp.width / 2 + 1., 0., sp.width / 2 - 1.)
                                    for along in (-2., 0., 2.)])
                    levels = roadmesh.drawn_ground(frame, part.elev, pts)
                    hits = vertical_hits(part.dmesh, pts, (tx * 256., ty * 256., 0.))
                    headroom = [float(np.min(h)) - float(g) for h, g in zip(hits, levels) if len(h)]
                    if headroom:
                        clearances.append({'bridge': str(fid), 'under': other,
                                           'min_headroom_m': round(min(headroom), 3)})
        print(name, 'tile', tx, ty, flush=True)
    minimum = min((r['min_headroom_m'] for r in clearances), default=None)
    enough = len(found) >= (2 if name in ('west-missing', 'west-rail', 'west-low', 'islamov', 'makarov') else 1)
    return {'site': name, 'at': [lat, lon], 'overture': state.md.release, 'surveyed_heights': False,
            'decks': found, 'crossings': clearances, 'min_headroom_m': minimum,
            'suspected_lane_guardrails': lane_rails,
            'pass': enough and max(grades, default=1.) <= .08 and (minimum is None or minimum >= 4.9)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--site', action='append', choices=SITES)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    blockworker.init(args.cache, False, True, True, True, True, None, logging.WARNING, False, True)
    result = []
    for name in args.site or SITES:
        result.append(audit(name, args.cache))
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if all(r['pass'] for r in result) else 1


if __name__ == '__main__':
    raise SystemExit(main())
