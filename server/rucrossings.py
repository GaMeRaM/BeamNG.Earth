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


def layout(roads, nodes, signals=None, priority=None, left_hand=False, fallback=()):
    crosswalks, ramps = list(fallback), {}
    pairs = []
    signed, owners = [], []
    if nodes is not None:
        crosswalks, _, ramps = secrossings.place(
            roads, dict(nodes, crossings=nodes.get("ru_crossings", [])), min_width=4.0
        )
        owners = []
        signed, _, _ = secrossings.place(
            roads,
            dict(nodes, crossings=nodes.get("ru_signs", nodes.get("ru_crossings", []))),
            on=owners,
            min_width=4.0,
        )
        for cw, (fid, spec) in zip(signed, owners):
            a, b = np.asarray(cw["a"]), np.asarray(cw["b"])
            span = float(dnp.norm(a[:2] - b[:2]))
            if span < 1.0:
                continue
            centre = (a[:2] + b[:2]) / 2
            n = (a[:2] - b[:2]) / span
            along = np.array([n[1], -n[0]])
            directions = (
                [along * (-1 if (spec.dir or 1) < 0 else 1)]
                if spec.oneway
                else [along, -along]
            )
            lanes = int(spec.lanes or max(1, round(span / 3.5)))
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
                incoming = lanes if spec.oneway else max(1, lanes // 2)
                opposing = 0 if spec.oneway else lanes - incoming
                if incoming >= 2:
                    edge = centre - go * cw["w"] / 2
                    duplicate = dict(
                        role="info.crossing_right", travel=go, road=edge, width=0.9
                    )
                    if opposing <= 2:
                        duplicate["p"] = edge - right * (span / 2 + 1.0)
                    else:
                        duplicate.update(
                            p=edge + right * span / 4,
                            overhead=True,
                            support=edge + right * (span / 2 + 1.0),
                        )
                    pairs.append(duplicate)
                    if spec.oneway:
                        pairs.append(
                            dict(duplicate, role="info.crossing_left", travel=-go)
                        )
    stops, cuts, plates = [], {}, []
    arms = furniture.give_way_arms(roads, signals, "RU", priority, stops=True)
    for arm in arms:
        lines, cut = markings.stop_lines(
            [arm],
            crosswalks,
            mapped=nodes.get("stop_lines") if nodes is not None else None,
            left_hand=left_hand,
            w=0.4,
        )
        stops.extend(lines)
        for fid, value in cut.items():
            cuts.setdefault(fid, []).extend(value)
        if arm[4] != furniture.G_SIGNAL:
            continue  # a STOP octagon alone is not a basis for 6.16
        for line in lines:
            a, b = np.asarray(line["a"]), np.asarray(line["b"])
            side = b[:2] - a[:2]
            length = float(dnp.norm(side))
            if length < 1.0:
                continue
            side /= length
            go = np.array([-side[1], side[0]]) * (-1 if left_hand else 1)
            # b is the incoming carriageway's kerb end (_way_in's hi).
            plates.append(
                dict(p=b[:2] + side * 1.1, travel=go, road=(a[:2] + b[:2]) / 2)
            )
    if nodes is not None and nodes.get("ru_signal_crossings"):
        import motesfri

        source = {fid: (sp, np.asarray(line, float)) for fid, sp, line, _ in roads}
        for cw, (fid, sp) in zip(signed, owners):
            centre = (cw["a"][:2] + cw["b"][:2]) / 2
            if (
                min(
                    (
                        float(dnp.norm(centre - np.asarray(q)))
                        for q in nodes["ru_signal_crossings"]
                    ),
                    default=100.0,
                )
                > 2.0
            ):
                continue
            if fid not in source:
                continue
            line = source[fid][1]
            stations = furniture._arclen(line)
            arc = float(motesfri._project(np.array([centre]), line[:, :2])[0][0])
            directions = [-1 if (sp.dir or 1) < 0 else 1] if sp.oneway else [1, -1]
            for sense in directions:
                reach = min(25.0, arc if sense > 0 else float(stations[-1]) - arc)
                if reach < 8.0:
                    continue
                at = arc - sense * np.arange(0.0, reach + 0.01, 1.0)
                branch, _ = furniture._at(line, at)
                go = -(branch[1, :2] - branch[0, :2])
                go /= max(float(dnp.norm(go)), 1e-9)
                if any(
                    float(dnp.norm((x["a"][:2] + x["b"][:2]) / 2 - centre)) < 20.0
                    and float(np.dot((x["b"] - x["a"])[:2], np.array([go[1], -go[0]])))
                    > 0.0
                    for x in stops
                ):
                    continue
                lines, cut = markings.stop_lines(
                    [(fid, sp, branch, 0.0, furniture.G_SIGNAL)],
                    crosswalks,
                    mapped=nodes.get("stop_lines"),
                    left_hand=left_hand,
                    w=0.4,
                )
                stops.extend(lines)
                for key, value in cut.items():
                    cuts.setdefault(key, []).extend(value)
                for x in lines:
                    side = (x["b"] - x["a"])[:2]
                    side /= max(float(dnp.norm(side)), 1e-9)
                    plates.append(
                        dict(
                            p=x["b"][:2] + side * 1.1,
                            travel=go,
                            road=(x["a"][:2] + x["b"][:2]) / 2,
                        )
                    )
    return dict(
        crosswalks=crosswalks,
        ramps=ramps,
        stops=stops,
        cuts=cuts,
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
    source, seen, infra = [], set(), []
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
        left_hand,
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
        for overhead in (False, True):
            chosen = [
                (i, s)
                for i, s in enumerate(pairs)
                if bool(s.get("overhead")) == overhead
            ]
            if not chosen:
                continue
            rows = [
                [
                    *s["p"],
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
            if overhead:
                t = t[mi == 0]
                used, inverse = np.unique(t, return_inverse=True)
                p, uv, t = p[used], uv[used], inverse.reshape(-1, 3)
                mi = np.zeros(len(t), np.int64)  # no stock centre pole through the lane
                # A metal back to each face, followed by supports wholly outside the carriageway.
                meshes.append((p, t, uv, ["bne_signs_vienna_ru", roadsigns.METAL], mi))
                for i, s in chosen:
                    verts, tri, tex, materials = _support(
                        s, frame, elev, box, z[i + len(pairs)]
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
        count = int(length // 1.0)
        if count < 1:
            continue
        u = (b - a) / length
        margin = (length - (count - 0.5)) / 2
        for i in range(count):
            start = a + u * (margin + i)
            out.append(dict(cw, a=start, b=start + u * 0.5, look=junctions.STOP_LINE))
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
