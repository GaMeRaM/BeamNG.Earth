"""Ground-level covered driveways cut through procedural buildings, with matching solid geometry."""
import copy

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

import mapgeom

CLASSES = {"service", "residential", "unclassified", "living_street"}
END_PAD_M = 1.0
SIDE_PAD_M = 0.25


def collect(frame, layers, x0, y0, size=256.0):
    """Mapped covered road ranges and short service tunnels, in the building tile's frame.

    Each entry is (polyline xy, carriageway width, mapped clearance or None). Ordinary roads crossing a bad
    footprint are not evidence of an arch. Underground tunnels must not open the houses above them.
    """
    import roads
    out, seen = [], set()
    for f in layers:
        if f is None or not len(f.kind):
            continue
        flags = f.rules.get("flags")
        classes = f.attrs.get("class")
        if flags is None or classes is None:
            continue
        candidates = np.unique(flags.feature[np.isin(flags.value, ["is_covered", "is_tunnel"])])
        specs = None
        for i in candidates.tolist():
            cls = str(classes[i])
            if cls not in CLASSES:
                continue
            level = roads._rule_value(f.rules.get("level"), i)
            if level is not None and float(level) < 0:
                continue
            for k in flags.rows(i):
                flag, a, b = str(flags.value[k]), float(flags.start[k]), float(flags.end[k])
                if flag != "is_covered" and not (flag == "is_tunnel" and cls == "service"):
                    continue
                key = (str(f.ids[i]), a, b)
                if key in seen:
                    continue
                seen.add(key)
                for part in f.parts(i):
                    if not part or len(part[0]) < 2:
                        continue
                    ll = roads.sub_polyline(np.asarray(part[0], np.float64), a, b)
                    e, n = mapgeom.enu_xy(f, frame, ll)
                    xy = np.c_[e - x0, n - y0]
                    if len(xy) < 2 or (xy.max(0) < -50).any() or (xy.min(0) > size + 50).any():
                        continue
                    length = float(np.hypot(*np.diff(xy, axis=0).T).sum())
                    if length < 1.0 or (flag == "is_tunnel" and length > 45.0):
                        continue
                    if specs is None:
                        specs = roads.road_specs(f)
                    sp = specs[i]
                    width = sp.width if sp is not None else roads.carriageway(cls, "paved", True)
                    clearance = None
                    values = f.attrs.get("osm_maxheight")
                    if values is not None:
                        try:
                            value = float(values[i])
                            if np.isfinite(value) and 2.0 <= value <= 8.0:
                                clearance = value
                        except (TypeError, ValueError):
                            pass
                    out.append((xy, float(width), clearance))
    return out


def apply(items, passages):
    """Split building solids into vertical layers around mapped passages; the roof and upper floors remain.

    Shapely/GEOS does the polygon difference. Through cuts produce ordinary exterior rings, so both existing
    building renderers and their collision builder consume exactly the same fragments. An enclosed cut with a
    hole is left alone: the building representation cannot express internal garages yet.
    """
    import buildings
    if not passages:
        return items
    cuts = []
    for xy, width, height in passages:
        xy = np.asarray(xy, np.float64).copy()
        for at, neighbour in ((0, 1), (-1, -2)):
            direction = xy[at] - xy[neighbour]
            xy[at] += direction * END_PAD_M / max(float(np.hypot(*direction)), 1e-9)
        cuts.append((LineString(xy).buffer(width / 2 + SIDE_PAD_M, cap_style="flat"), height))
    out = []
    for spec, gmin, gmax in items:
        if spec.cls in buildings.OPEN_CANOPY_CLASSES | buildings.BRIDGE_CLASSES or spec.deck or spec.ship:
            out.append((spec, gmin, gmax))
            continue
        poly = Polygon(spec.ring)
        if not poly.is_valid or poly.area < 1.0:
            out.append((spec, gmin, gmax))
            continue
        active = []
        bottom = float(spec.min_h or 0.0)
        for shape, mapped_height in cuts:
            height = buildings.FLOOR_M if mapped_height is None else mapped_height
            clear = min(float(height) - bottom, float(spec.height) - 0.2)
            if clear < 0.5 or not poly.intersects(shape) or poly.intersection(shape).area < 0.25:
                continue
            remaining = poly.difference(shape)
            polygons = list(remaining.geoms) if remaining.geom_type == 'MultiPolygon' else [remaining]
            if any(p.geom_type != 'Polygon' or p.interiors for p in polygons):
                continue
            active.append((shape, clear))
        if not active:
            out.append((spec, gmin, gmax))
            continue
        levels = sorted({0.0, float(spec.height), *(h for _, h in active)})
        for low, high in zip(levels, levels[1:]):
            cutters = [shape for shape, height in active if height >= high - 1e-8]
            solid = poly.difference(unary_union(cutters)) if cutters else poly
            pieces = list(solid.geoms) if solid.geom_type == 'MultiPolygon' else [solid]
            for piece in pieces:
                if piece.is_empty or piece.geom_type != 'Polygon' or piece.interiors or piece.area < 0.05:
                    continue
                fragment = copy.copy(spec)
                fragment.passage = True
                fragment.fr_house = None
                ring = np.asarray(piece.exterior.coords, np.float64)[:-1]
                fragment.ring = ring if buildings._area2(ring) > 0 else ring[::-1]
                fragment.min_h, fragment.height = bottom + low, high - low
                fragment.floors = max(1, int(round(fragment.height / (spec.floor_h or buildings.FLOOR_M))))
                fragment.floor_h = fragment.height / fragment.floors
                fragment.gring = None
                fragment.door = fragment.stoop = fragment.porch = fragment.sign = None
                fragment.shop = False
                if high < spec.height - 1e-8:
                    fragment.roof, fragment.plain = 'flat', True
                    fragment.windows, fragment.band = False, None
                    fragment.steeple = False
                out.append((fragment, gmin, gmax))
    return out
