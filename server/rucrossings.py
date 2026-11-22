"""One Russian crossing/control layout for paint and sign faces.

Coordinates are world ENU, independent of the requesting tile. The node dataset
is evidence of a crossing, not a survey of its width or physical equipment.
"""

import os
import numpy as np
import dnp
import furniture
import markings
import secrossings


def _extend_approaches(roads, approaches):
    """Carry short junction approaches across unambiguous degree-two way splits."""
    ends = furniture._arms(roads)
    source = {fid: np.asarray(line, float) for fid, _, line, _ in roads}
    extended, continuations = [], {}
    for fid, spec, line, wide, control in approaches:
        used = [fid]
        while furniture._arclen(line)[-1] < markings.M14_LOOK_M:
            key = tuple(round(float(v) / furniture.JUNCTION_SNAP_M) for v in line[-1, :2])
            branches = ends.get(key, ())
            if len(branches) != 2:
                break
            following = [a for a in branches if a[0] not in used]
            if len(following) != 1:
                break
            other, next_spec, tangent, point, start, _ = following[0]
            last = line[-1, :2] - line[-2, :2]
            incoming = ((next_spec.dir or 1) < 0) == start
            if (next_spec.kind != spec.kind or next_spec.oneway != spec.oneway
                    or (spec.oneway and not incoming)
                    or dnp.norm(point[:2] - line[-1, :2]) > 1.0
                    or dnp.dot(last, tangent) < 0.9 * dnp.norm(last)):
                break
            branch = source[other] if start else source[other][::-1]
            line = np.vstack((line, branch[1:]))
            used.append(other)
        extended.append((fid, spec, line, wide, control))
        if len(used) > 1:
            continuations.setdefault(fid, set()).update(used[1:])
    return extended, continuations


def _on_approach(centre, travel, arm):
    """Identify junction crossings by their position and axis, across source way splits."""
    _, spec, line, wide, _ = arm
    stations = furniture._arclen(line)
    at = np.linspace(0.0, min(stations[-1], wide + 15.0), 12)
    points, _ = furniture._at(line, at)
    steps = np.diff(points[:, :2], axis=0)
    lengths = dnp.hypot(*steps.T)
    tangents = steps / np.maximum(lengths[:, None], 1e-9)
    offset = centre - points[:-1, :2]
    along = np.sum(offset * tangents, axis=1)
    lateral = dnp.hypot(*(offset - along[:, None] * tangents).T)
    return bool(np.any((abs(dnp.matmul(tangents, travel)) > 0.8) & (lateral < min(3.0, spec.width / 2))
                       & (along >= -1.0) & (along <= lengths + 5.0)))


def _junction_edges(roads):
    """Near edge of the intersecting carriageway, per incoming road end."""
    from collections import defaultdict

    edges = defaultdict(list)
    for arms in furniture._arms(roads).values():
        if len(arms) < 3:
            continue
        for arm in arms:
            fid, spec, outward, point = arm[:4]
            if spec.kind != "paved" or furniture._outbound(arm):
                continue
            normal = np.array([-outward[1], outward[0]])
            crossing = [other[1].width / (2 * abs(float(dnp.dot(other[2], normal))))
                        for other in arms if abs(float(dnp.dot(other[2], normal))) > .5]
            if not crossing:
                continue
            centre = point[:2] + outward * max(crossing)
            edges[fid].append(dict(a=centre - normal * spec.width, b=centre + normal * spec.width, w=.001))
    return edges


def _signal_minimum(roads, nodes, left_hand):
    """Use a mapped head when available and the rendered overhead boom otherwise."""
    heads = (nodes or {}).get("ru_signal_heads", ())
    road_lines = [(spec.width / 2, line) for _, spec, line, _ in roads]
    clearance = furniture.RoadClearance(road_lines)

    def minimum(line, spec, wide):
        start = line[0, :2]
        _, tangent = furniture._at(line, np.array([min(1., furniture._arclen(line)[-1] / 2)]))
        u = tangent[0]
        side, yaw = furniture.approach_pose(u, furniture.G_SIGNAL, left_hand)
        candidates = [(p, overhead) for p, overhead in heads
                      if -.5 <= dnp.dot(p - start, u) <= wide + 12.
                      and -.5 <= dnp.dot(p - start, side) <= spec.width / 2 + 3.
                      and dnp.norm(p - start) > .5]
        if candidates:
            points = np.asarray([p for p, _ in candidates])
            along = furniture._project(line, points)
            return max(float(at) + (10. if overhead else 3.)
                       for at, (_, overhead) in zip(along, candidates))
        if wide:
            spot = furniture.signal_spot(start, u, side, wide, spec.width / 2, road_lines,
                                         clearance=clearance, yaw=yaw)
            if spot is not None:
                return float(furniture._project(line, np.array([spot[:2]]))[0]) + 10.
        return 3.

    return minimum


def layout(roads, nodes, signals=None, priority=None, left_hand=False, fallback=(), lane_tags=None):
    crosswalks, ramps = list(fallback), {}
    pairs = []
    approaches = furniture.give_way_arms(roads, signals, "RU", priority, stops=True)
    approaches, continuations = _extend_approaches(roads, approaches) if approaches else ([], {})
    junction_arms = [arm for arm in approaches if arm[4] == furniture.G_SIGNAL]
    signal_crossings = np.asarray((nodes or {}).get("ru_signal_crossings", []), float).reshape(-1, 2)
    junction_crossings = []
    signed, owners = [], []
    if nodes is not None:
        crosswalks, _, ramps = secrossings.place(
            roads, dict(nodes, crossings=nodes.get("ru_crossings", [])),
            min_width=4.0, widths=nodes.get("ru_crossing_widths")
        )
        owners = []
        signed, _, _ = secrossings.place(
            roads,
            dict(nodes, crossings=nodes.get("ru_signs", nodes.get("ru_crossings", []))),
            on=owners,
            min_width=4.0, widths=nodes.get("ru_crossing_widths"),
        )
        for cw, (fid, spec) in zip(signed, owners):
            a, b = np.asarray(cw["a"]), np.asarray(cw["b"])
            span = float(dnp.norm(a[:2] - b[:2]))
            centre = (a[:2] + b[:2]) / 2
            n = (a[:2] - b[:2]) / span
            along = np.array([n[1], -n[0]])
            directions = (
                [along * (-1 if (spec.dir or 1) < 0 else 1)]
                if spec.oneway
                else [along, -along]
            )
            at_junction = any(_on_approach(centre, along, arm) for arm in junction_arms)
            junction_crossings.append(at_junction)
            regulated = at_junction or (
                len(signal_crossings) > 0 and np.any(dnp.hypot(*(signal_crossings - centre).T) <= 2.0)
            )
            lanes = int(spec.lanes or max(1, round(span / 3.5)))
            tags = (lane_tags or {}).get(fid) or {}
            forward = markings._count(tags.get("lanes:forward"))
            backward = markings._count(tags.get("lanes:backward"))
            for go in directions:
                right = np.array([go[1], -go[0]])
                for near, role in [
                    (True, "info.crossing_right"),
                    (False, "info.crossing_left"),
                ]:
                    edge = centre + go * cw["w"] / 2 * (-1 if near else 1)
                    p = edge + right * (span / 2 + 1.0) * (1 if near else -1)
                    pairs.append(
                        dict(
                            role=role,
                            p=p,
                            travel=go,
                            road=edge,
                            width=0.9 if (spec.lanes or 0) >= 4 else 0.7,
                        )
                    )
                    if spec.oneway:
                        pairs.append(
                            dict(
                                pairs[-1],
                                role="info.crossing_left"
                                if near
                                else "info.crossing_right",
                                travel=-go,
                            )
                        )
                along_way = dnp.dot(go, along) > 0
                mapped = forward if along_way else backward
                opposite = backward if along_way else forward
                incoming = lanes if spec.oneway else mapped or max(1, lanes - opposite if opposite else lanes // 2)
                threshold = 3 if spec.oneway else 2
                if not spec.urban or (not regulated and incoming >= threshold):
                    edge = centre - go * cw["w"] / 2
                    lane_width = span / max(lanes, (forward or 0) + (backward or 0), incoming)
                    support = edge + right * (span / 2 + 1.0)
                    pairs.append(dict(
                        role="info.crossing_right", travel=go, road=edge, width=0.9,
                        p=edge + right * (span / 2 - lane_width / 2),
                        overhead=True, support=support,
                    ))
    if len(signal_crossings):
        import motesfri

        for cw, (fid, spec), at_junction in zip(signed, owners, junction_crossings):
            if at_junction:
                continue
            centre = (cw["a"][:2] + cw["b"][:2]) / 2
            if not np.any(dnp.hypot(*(signal_crossings - centre).T) <= 2.0):
                continue
            line = next(line for key, _, line, _ in roads if key == fid)
            stations = furniture._arclen(line)
            arc = float(motesfri._project(np.array([centre]), line[:, :2])[0][0])
            directions = [-1 if (spec.dir or 1) < 0 else 1] if spec.oneway else [1, -1]
            for sense in directions:
                reach = min(25.0, arc if sense > 0 else float(stations[-1]) - arc)
                if reach >= 8.0:
                    at = arc - sense * np.arange(0.0, reach + 0.01, 1.0)
                    branch, _ = furniture._at(line, at)
                    approaches.append((fid, spec, branch, 0.0, furniture.G_SIGNAL))

    boundaries = [*crosswalks, *signed]
    stops, cuts = markings.stop_lines(
        approaches, boundaries, mapped=(nodes or {}).get("stop_lines"),
        left_hand=left_hand, w=0.4, own_crossings=True,
        signal_minimum=_signal_minimum(roads, nodes, left_hand) if junction_arms or len(signal_crossings) else None,
    )
    for fid, following in continuations.items():
        for other in following:
            cuts.setdefault(other, []).extend(cuts.get(fid, ()))
    plates = []
    for line in stops:
        if line["control"] != furniture.G_SIGNAL:
            continue
        a, b = line["a"], line["b"]
        side = b[:2] - a[:2]
        length = float(dnp.norm(side))
        if length < 1.0:
            continue
        side /= length
        go = np.array([-side[1], side[0]]) * (-1 if left_hand else 1)
        plates.append(dict(p=b[:2] + side * 1.1, travel=go, road=(a[:2] + b[:2]) / 2))
    return dict(
        crosswalks=crosswalks,
        ramps=ramps,
        stops=stops,
        cuts=cuts,
        controls=[*boundaries, *stops],
        edges=_junction_edges(roads),
        pairs=pairs,
        plates=plates,
    )


def source_layout(md, frame, box, context, left_hand=False):
    import mapcells, roads as roadmod, mapgeom, signroads

    x0, y0, x1, y1 = box
    la, lo, _ = frame.enu_to_geodetic(
        np.array([x0 - 100.0, x1 + 100.0]), np.array([y0 - 100.0, y1 + 100.0]), 0.0
    )
    keys = list(
        mapcells.cells_for_bbox(
            float(min(la)), float(min(lo)), float(max(la)), float(max(lo))
        )
    )
    source, seen, infra, tags = [], set(), [], {}
    for key in keys:
        f = context.cell(key)
        infra.append(
            md.cell(key, layers=("infrastructure",), kind="prefetch").layers.get(
                "infrastructure"
            )
        )
        if f is None:
            continue
        placement = roadmod.placement_context(
            [f], context.urban, context.widths, left_hand
        )
        for i, sp in enumerate(
            signroads.cell_specs(f, context.urban, context.widths, left_hand)
        ):
            if sp is None or str(f.ids[i]) in seen:
                continue
            seen.add(str(f.ids[i]))
            tags[str(f.ids[i])] = roadmod.lane_tags(f, i)
            for ring in roadmod.ground_parts(f, i):
                if len(ring) < 2:
                    continue
                ring = placement.ring(frame, f, i, ring, sp)
                e, n = mapgeom.enu_xy(f, frame, ring)
                if len(e) > 1:
                    source.append(
                        (str(f.ids[i]), sp, np.c_[e, n, np.zeros(len(e))], frame.lon0)
                    )
    nodes = secrossings.nodes(frame, infra)
    return layout(
        source,
        nodes,
        furniture.mapped_signals(frame, infra),
        (nodes or {}).get("priority"),
        left_hand, lane_tags=tags,
    )


def build_tile(
    md, frame, tx, ty, elev, context, out_dir, vfs_dir, left_hand=False, decks=()
):
    import roads, roadsigns, exitsigns, fast, dirsigns, imagery, busstationsign

    box = roads.tile_bbox(tx, ty)
    planned = source_layout(md, frame, box, context, left_hand)

    def keep(s):
        x, y = s["p"]
        return roads.box_owns(box, float(x), float(y)) and not exitsigns._on_deck(
            s["p"], decks, 1.5
        )

    def heights(items):
        xy = np.array([s["p"] for s in items] + [s["road"] for s in items])
        la, lo, _ = frame.enu_to_geodetic(xy[:, 0], xy[:, 1], 0.0)
        return np.asarray(frame.geodetic_to_enu(la, lo, elev(la, lo))[2]).ravel()

    pairmesh = None
    pairs = [s for s in planned["pairs"] if keep(s)]
    if pairs:
        import rusigns

        z = heights(pairs)
        roles, _, by_id = roadsigns.tables()
        meshes = []
        # Opposite faces on the same boundary share one pole and backing.
        # The native mesh otherwise puts each opaque back in front of the
        # other sign's face, hiding both pictograms.
        locations = {}
        for i, sign in enumerate(pairs):
            key = (*np.round(sign["p"], 3), bool(sign.get("overhead")))
            locations.setdefault(key, []).append(i)
        shared, faces_only = set(), set()
        for group in locations.values():
            if len(group) != 2:
                continue
            front, back = group
            if dnp.dot(pairs[front]["travel"], pairs[back]["travel"]) < -0.99:
                shared.update(group)
                faces_only.add(back)
        for overhead, reverse in ((False, False), (False, True), (True, False), (True, True)):
            chosen = [
                (i, s)
                for i, s in enumerate(pairs)
                if bool(s.get("overhead")) == overhead
                and (i in faces_only) == reverse
            ]
            if not chosen:
                continue
            rows = [
                [
                    *(s["p"] - s["travel"] * (0.04 if overhead else 0.006)
                      if i in shared else s["p"]),
                    z[i],
                    z[i + len(pairs)],
                    *s["travel"],
                    by_id[s["role"]][0],
                    5,
                    s["width"],
                    5.5 if overhead else 2.2,
                ]
                for i, s in chosen
            ]
            p, t, uv, mi = fast._ef.road_sign_mesh(
                np.ascontiguousarray(rows, float),
                roles["cols"],
                roles["rows"],
                [box[0], box[1], 0.0],
            )
            if overhead or reverse:
                t = t[mi == 0]
                used, inverse = np.unique(t, return_inverse=True)
                p, uv, t = p[used], uv[used], inverse.reshape(-1, 3)
                mi = np.zeros(len(t), np.int64)  # no stock centre pole through the lane
                # A metal back to each face, followed by supports wholly outside the carriageway.
                meshes.append((p, t, uv, ["bne_signs_vienna_ru", roadsigns.METAL], mi))
                if overhead and not reverse:
                    for i, s in chosen:
                        mount = dict(s, p=s["p"] - s["travel"] * 0.04) if i in shared else s
                        verts, tri, tex, materials = _support(
                            mount, frame, elev, box, z[i + len(pairs)]
                        )
                        meshes.append((verts, tri, tex, [roadsigns.METAL], materials))
            else:
                meshes.append((p, t, uv, ["bne_signs_vienna_ru", roadsigns.METAL], mi))
        pairmesh = rusigns.join_meshes(meshes)
    plates = [s for s in planned["plates"] if keep(s)]
    faces = {}
    platemesh = None
    if plates:
        dirsigns._set_fonts()
        flat = [
            255,
            255,
            255,
            0,
            0,
            0,
            0,
            0,
            0,
            255,
            255,
            255,
            (0.35 - 0.036) / 2.4,
            0.55,
            1.05,
            1.05,
            0.012,
            0.006,
            0.0,
            0.0,
            0.0,
        ]
        data, w, h = fast._ef.dirsign_town_face("СТОП", "", False, flat, 512.0)
        import hashlib

        name = "bne_ru_stopline_" + hashlib.sha256(bytes(data)).hexdigest()[:16]
        path = os.path.join(out_dir, name + ".color.dds")
        if not os.path.exists(path):
            imagery.write_picture_dds(path, data)
        faces[name] = vfs_dir + "/" + name + ".color.dds"
        z = heights(plates)
        rows = []
        for i, s in enumerate(plates):
            rows.append([*s["p"], z[i], z[i + len(plates)], *s["travel"], w, h, 1, 1.5])
        p, t, uv, mi = fast._ef.dirsign_mesh(
            np.ascontiguousarray(rows, float), [box[0], box[1], 0.0]
        )
        platemesh = (p, t, uv, [dirsigns.METAL, name], mi)
    return pairmesh, platemesh, faces


def paint_stripes(crosswalks):
    """Explicit 0.5 m white bars / 0.5 m gaps; independent of stock zebra UVs.

    Keep the full crossing envelope for signs, curb ramps and longitudinal cuts;
    split only the painted geometry. Centre the pattern across each carriageway.
    """
    import junctions

    out = []
    for cw in crosswalks:
        if cw.get("stop") or not cw.get("paint", True):
            out.append(cw)
            continue
        a, b = np.asarray(cw["a"]), np.asarray(cw["b"])
        length = float(dnp.norm(b[:2] - a[:2]))
        if cw["w"] > 6.0:
            out.extend(_wide_crossing(a, b, cw["w"]))
            continue
        count = int(length // 1.0)
        if count < 1:
            continue
        u = (b - a) / length
        margin = (length - (count - 0.5)) / 2
        for i in range(count):
            start = a + u * (margin + i)
            out.append(dict(cw, a=start, b=start + u * 0.5, look=junctions.STOP_LINE))
    return out


def _wide_crossing(a, b, width):
    """1.14.2, ГОСТ Р 51256-2018 figures Б.2 and Б.3."""
    across = np.asarray(b - a, float)
    length = float(dnp.norm(across[:2]))
    if length < 1.0:
        return []
    across /= length
    side = np.array([-across[1], across[0], 0.])
    side /= dnp.norm(side)
    half = width / 2
    out = []

    def polygon(points):
        out.append({"poly": np.array([a + x * across + y * side for x, y in points])})

    def rect(x0, x1, y0, y1):
        if x1 > x0 and y1 > y0:
            polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    count = int(length)
    margin = (length - (count - .5)) / 2
    # Each entrance keeps its first bar. The next bar in its right-hand
    # half gives way to the three pedestrian arrows from figure Б.2.
    for sense in (1, -1):
        omitted = 1 if sense > 0 else count - 2
        y0, y1 = (-half, -.1) if sense > 0 else (.1, half)
        for i in range(count):
            if count < 4 or i != omitted:
                x = margin + i
                rect(x, x + .5, y0, y1)
        if count < 4:
            continue
        y = (y0 + y1) / 2
        entrance = margin + .5 if sense > 0 else length - margin - .5
        for lateral in (-.6, 0., .6):
            mid = y + lateral
            start = entrance + sense * (.2 if lateral == 0. else .1)
            base = start + sense * .68
            tip = start + sense * 1.2
            rect(min(start, base), max(start, base), mid - .1, mid + .1)
            polygon([(base, mid - .3), (tip, mid), (base, mid + .3)])
    return out


def _support(sign, frame, elev, box, road_z):
    """A roadside square post and high cantilever; no support foot on a traffic lane."""
    points = []
    triangles = []

    def beam(c, u, hx, hy, z0, z1):
        u = np.asarray(u, float)
        v = np.array([-u[1], u[0]])
        corners = [
            c - u * hx - v * hy,
            c + u * hx - v * hy,
            c + u * hx + v * hy,
            c - u * hx + v * hy,
        ]
        offset = len(points)
        points.extend(
            [[q[0] - box[0], q[1] - box[1], z] for z in (z0, z1) for q in corners]
        )
        for face in [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]:
            a, b, c_, d = (offset + x for x in face)
            triangles.extend([(a, b, c_), (a, c_, d)])

    support = np.asarray(sign["support"])
    p = np.asarray(sign["p"])
    go = np.asarray(sign["travel"])
    la, lo, _ = frame.enu_to_geodetic(support[0], support[1], 0.0)
    ground = float(np.asarray(frame.geodetic_to_enu(la, lo, elev(la, lo))[2]).ravel()[0])
    top = road_z + 6.6
    beam(support, go, 0.075, 0.075, ground - 0.2, top)
    delta = p - support
    length = float(dnp.norm(delta))
    beam(
        (p + support) / 2, delta / max(length, 1e-9), length / 2, 0.075, top - 0.15, top
    )
    # Short hanger and opaque backing plate above the 5.5 m clear opening.
    beam(p, go, 0.04, 0.04, road_z + 6.35, top)
    beam(
        p + go * 0.025,
        go,
        0.01,
        sign["width"] / 2,
        road_z + 5.5,
        road_z + 5.5 + sign["width"],
    )
    points = np.array(points, float)
    return (
        points,
        np.array(triangles, np.int64),
        np.zeros((len(points), 2)),
        np.zeros(len(triangles), np.int64),
    )
