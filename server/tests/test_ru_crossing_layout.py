"""Russian crossing boundaries and STOP-line plates share the paint layout."""

import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parent),
]
import rucrossings as ru
import markings, roads, signstream
from test_roads import FRAME, features, flat


def scene(oneway=False, direction=1):
    f = features([[(10.0, 100.0), (240.0, 100.0)]], ["tertiary"], widths=[(0, 10.0)])
    s = roads.road_specs(f)[0]._replace(
        oneway=oneway, dir=direction, lanes=1 if oneway else 2, urban=True
    )
    return [
        (
            str(f.ids[0]),
            s,
            np.array([[10.0, 100.0, 0.0], [240.0, 100.0, 0.0]]),
            FRAME.lon0,
        )
    ]


def nodes(paint=1):
    return dict(
        ru_crossings=[(100.0, 100.0, paint)],
        ru_signs=[(100.0, 100.0, 1)],
        stop_lines=np.empty((0, 2)),
    )


class CrossingLayout(unittest.TestCase):
    def test_two_way_pairs_bound_the_same_painted_strip(self):
        p = ru.layout(scene(), nodes())
        self.assertEqual(len(p["crosswalks"]), 1)
        self.assertEqual(len(p["pairs"]), 4)
        for sign in p["pairs"]:
            near = sign["role"] == "info.crossing_right"
            self.assertAlmostEqual(
                float(np.dot(sign["road"] - [100.0, 100.0], sign["travel"])),
                -2 if near else 2,
            )
            self.assertAlmostEqual(abs(sign["p"][1] - 100.0), 6.0)

    def test_one_way_has_reverse_faces_on_both_boundaries(self):
        for direction in [-1, 1]:
            p = ru.layout(scene(True, direction), nodes())
            self.assertEqual(len(p["pairs"]), 4)
            self.assertEqual(len({tuple(s["p"]) for s in p["pairs"]}), 2)
            self.assertEqual(sum(s["travel"][0] > 0 for s in p["pairs"]), 2)

    def test_unpainted_crossing_can_still_have_boundary_signs(self):
        p = ru.layout(scene(), nodes(0))
        self.assertFalse(p["crosswalks"])
        self.assertEqual(len(p["pairs"]), 4)

    def test_absent_nodes_do_not_invent_crossing_signs(self):
        self.assertFalse(ru.layout(scene(), None)["pairs"])

    def test_signal_plate_is_in_exact_stop_line_section(self):
        lines = [
            [(100.0, 100.0), (100.0 + dx * 80, 100.0 + dy * 80)]
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
        ]
        f = features(lines, ["tertiary"] * 4, widths=[(i, 10.0) for i in range(4)])
        rs = [
            (str(f.ids[i]), s, np.c_[np.array(lines[i]), np.zeros(2)], FRAME.lon0)
            for i, s in enumerate(roads.road_specs(f))
        ]
        p = ru.layout(rs, None, signals=np.array([[100.0, 100.0]]))
        self.assertEqual(len(p["stops"]), 4)
        self.assertEqual(len(p["plates"]), 4)
        for line, plate in zip(p["stops"], p["plates"]):
            self.assertAlmostEqual(
                float(np.dot(plate["p"] - line["a"][:2], plate["travel"])), 0.0
            )
        self.assertFalse(ru.layout(rs, None, signals=np.empty((0, 2)))["plates"])

    def test_midblock_signal_has_stop_lines_and_plates_for_both_directions(self):
        n = nodes()
        n["ru_signal_crossings"] = [(100.0, 100.0)]
        p = ru.layout(scene(), n, signals=np.empty((0, 2)))
        self.assertEqual(len(p["stops"]), 2)
        self.assertEqual(len(p["plates"]), 2)
        self.assertGreater(
            p["plates"][0]["travel"][0] * p["plates"][1]["travel"][0] * -1, 0.99
        )

    def test_signal_crossing_on_junction_arm_does_not_stop_departures(self):
        rs = scene()
        fid, spec, _, lon = rs[0]
        arms = [np.array([[100., 100., 0.], [100. + dx * 80, 100. + dy * 80, 0.]])
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]]
        rs = [(str(i), spec, arm, lon) for i, arm in enumerate(arms)]
        n = nodes()
        n.update(ru_crossings=[(112., 100., 1)], ru_signs=[(112., 100., 1)],
                 ru_signal_crossings=[(112., 100.)])
        planned = ru.layout(rs, n, signals=np.array([[100., 100.]]))
        self.assertEqual(len(planned["stops"]), 4)
        self.assertEqual(len(planned["plates"]), 4)

    def test_junction_crossing_on_different_way_id_does_not_add_stops(self):
        fid, spec, _, lon = scene()[0]
        arms = [np.array([[100., 100., 0.], [100. + dx * 80, 100. + dy * 80, 0.]])
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]]
        arms[0][1, 0] = 110.
        continuation = np.array([[110., 100., 0.], [190., 100., 0.]])
        rs = [(str(i), spec, arm, lon) for i, arm in enumerate([*arms, continuation])]
        n = nodes()
        n.update(ru_crossings=[(113., 100., 1)], ru_signs=[(113., 100., 1)],
                 ru_signal_crossings=[(113., 100.)])
        planned = ru.layout(rs, n, signals=np.array([[100., 100.]]))
        self.assertEqual(len(planned["stops"]), 4)
        east_side = [plate for plate in planned["plates"] if plate["road"][0] > 105.]
        self.assertEqual(len(east_side), 1)
        self.assertLess(east_side[0]["travel"][0], -.99)
        self.assertGreater(east_side[0]["road"][0], 115.)
        self.assertIn("4", planned["cuts"])

    def test_arrows_on_both_approaches_stay_before_control(self):
        lane = np.array([[0., 0., 0.], [100., 0., 0.]])
        tags = {"turn:lanes:forward": "left", "turn:lanes:backward": "right"}
        controls = [
            dict(a=np.array([x, y0, 0.]), b=np.array([x, y1, 0.]), w=w)
            for x, y0, y1, w in [(76., -4., 4., 4.), (24., -4., 4., 4.),
                                 (70., -4., 0., .4), (30., 0., 4., .4)]
        ]
        arrows = markings.arrows(tags, lane, True, 8., 2, country="RU", controls=controls)
        self.assertEqual(len(arrows), 4)
        for sense in (1, -1):
            stations = sorted(centre[0] for centre, direction, _ in arrows if direction[0] * sense > 0)
            self.assertAlmostEqual(stations[1] - stations[0], 25.)
        for centre, direction, kind in arrows:
            quad, _ = markings.arrow_quad(centre, direction, kind, country="RU", speed_kmh=80)
            if direction[0] > 0:
                self.assertLess(quad[:, 0].max(), 69.8)
            else:
                self.assertGreater(quad[:, 0].min(), 30.2)

    def test_last_arrow_uses_the_solid_start_or_junction_edge(self):
        lane = np.array([[0., 0., 0.], [120., 0., 0.]])
        edge = dict(a=np.array([110., -4.]), b=np.array([110., 4.]), w=.001)
        divider = np.array([[70., 0., 0.], [105., 0., 0.]])
        for speed, solids, expected in [(60., (), 90.), (80., (), 70.), (60., [divider], 70.)]:
            arrows = markings.arrows({"turn:lanes": "left|through"}, lane, False, 8., 2,
                                     country="RU", edges=[edge], solids=solids, speed_kmh=speed)
            self.assertEqual(len(arrows), 4)
            quad, _ = markings.arrow_quad(*arrows[0], country="RU", speed_kmh=speed)
            self.assertAlmostEqual(quad[:, 0].min(), expected, places=2)

    def test_mapped_signal_mounting_controls_stop_line_setback(self):
        fid, spec, _, lon = scene()[0]
        ways = [np.array([[100., 100., 0.], [100. + dx * 80, 100. + dy * 80, 0.]])
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]]
        rs = [(str(i), spec, way, lon) for i, way in enumerate(ways)]
        for overhead, distance in [(False, 3.), (True, 10.)]:
            head = np.array([108., 103.])
            planned = ru.layout(rs, {"ru_signal_heads": [(head, overhead)]},
                                signals=np.array([[100., 100.]]))
            east = next(plate for plate in planned["plates"] if plate["travel"][0] < -.99)
            self.assertAlmostEqual(east["road"][0] - head[0], distance)

    def test_wide_crossing_splits_paint_and_adds_opposed_arrows(self):
        n = dict(nodes(), ru_crossing_widths={(100., 100.): 8.})
        planned = ru.layout(scene(), n)
        self.assertEqual(planned["crosswalks"][0]["w"], 8.)
        self.assertTrue(all(abs(sign["road"][0] - 100.) == 4. for sign in planned["pairs"]))
        paint = ru.paint_stripes(planned["crosswalks"])
        triangles = [row["poly"] for row in paint if len(row["poly"]) == 3]
        self.assertEqual(len(triangles), 6)
        self.assertEqual(sum(tri[1, 1] > tri[0, 1] for tri in triangles), 3)
        self.assertTrue(all(np.all(abs(row["poly"][:, 0] - 100.) >= .1 - 1e-8) for row in paint))

    def test_explicit_stripes_have_half_metre_bars_and_gaps(self):
        p = ru.layout(scene(), nodes())
        stripes = ru.paint_stripes(p["crosswalks"])
        self.assertEqual(len(stripes), 10)
        for x in stripes:
            self.assertAlmostEqual(float(np.linalg.norm(x["b"] - x["a"])), 0.5)
        for a, b in zip(stripes, stripes[1:]):
            self.assertAlmostEqual(float(np.linalg.norm(b["a"] - a["b"])), 0.5)

    def test_wide_road_duplicates_and_overhead_clearance(self):
        rs = scene()
        fid, sp, xyz, lon = rs[0]
        four = ru.layout([(fid, sp._replace(lanes=4, width=14.0), xyz, lon)], nodes())
        self.assertEqual(len(four["pairs"]), 6)
        self.assertEqual(sum(bool(s.get("overhead")) for s in four["pairs"]), 2)
        six = ru.layout([(fid, sp._replace(lanes=6, width=21.0), xyz, lon)], nodes())
        self.assertEqual(sum(bool(s.get("overhead")) for s in six["pairs"]), 2)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(ru, "source_layout", return_value=six),
        ):
            pair, _, _ = ru.build_tile(None, FRAME, 0, 0, flat, None, tmp, "/vfs")
            p = pair[0]
            self.assertFalse(np.any((abs(p[:, 1] - 100.0) < 10.5) & (p[:, 2] < 15.4)))

    def test_crossing_duplicates_use_directional_counts_and_urban_exceptions(self):
        fid, sp, xyz, lon = scene()[0]
        def duplicates(spec, n, tags=None):
            planned = ru.layout([(fid, spec, xyz, lon)], n, lane_tags={fid: tags})
            return [sign for sign in planned["pairs"] if sign.get("overhead")]

        two_way = sp._replace(lanes=3)
        asymmetric = duplicates(two_way, nodes(), {"lanes:forward": "2", "lanes:backward": "1"})
        self.assertEqual(len(asymmetric), 1)
        self.assertGreater(asymmetric[0]["travel"][0], 0)
        self.assertFalse(duplicates(sp._replace(oneway=True, lanes=2), nodes()))
        self.assertEqual(len(duplicates(sp._replace(oneway=True, lanes=3), nodes())), 1)
        self.assertEqual(len(duplicates(sp._replace(urban=False), nodes())), 2)
        regulated = dict(nodes(), ru_signal_crossings=[(100., 100.)])
        self.assertFalse(duplicates(sp._replace(lanes=4), regulated))

    def test_stop_plate_real_mesh_texture_and_mount(self):
        n = nodes()
        n["ru_signal_crossings"] = [(100.0, 100.0)]
        planned = ru.layout(scene(), n, signals=np.empty((0, 2)))
        import fast

        native = fast._ef.dirsign_mesh
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(ru, "source_layout", return_value=planned),
            patch.object(fast._ef, "dirsign_mesh", wraps=native) as mesh,
        ):
            pairs, plate, faces = ru.build_tile(
                None, FRAME, 0, 0, flat, None, tmp, "/vfs"
            )
            self.assertTrue(len(plate[1]))
            self.assertEqual(len(faces), 1)
            rows = mesh.call_args.args[0]
            np.testing.assert_allclose(rows[:, 9], 1.5)
            np.testing.assert_allclose(rows[:, 6] / rows[:, 7], 3.0, rtol=0.01)
            self.assertTrue(
                all(p.read_bytes()[:4] == b"DDS " for p in Path(tmp).glob("*.dds"))
            )
            import rusigns, json

            merged = rusigns.join_meshes([pairs, plate])
            path, _ = signstream.write_tile(
                tmp,
                "/vfs",
                1,
                0,
                0,
                [None, None, None, None, None, merged, None],
                faces,
            )
            data = json.loads((Path(tmp) / Path(path).name).read_text())
            self.assertIn("rsigns", data)
            self.assertNotIn("dirs", data)
            self.assertEqual(data["dirs_faces"], faces)

    def test_mesh_and_owner_tile(self):
        planned = ru.layout(scene(), nodes())
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(ru, "source_layout", return_value=planned),
        ):
            pair, plate, faces = ru.build_tile(
                None, FRAME, 0, 0, flat, None, tmp, "/vfs"
            )
            self.assertTrue(len(pair[1]))
            self.assertIsNone(plate)
            other, _, _ = ru.build_tile(None, FRAME, 1, 0, flat, None, tmp, "/vfs")
            self.assertIsNone(other)

    def test_back_to_back_crossing_faces_share_one_metal_assembly(self):
        planned = ru.layout(scene(), nodes())
        signs = planned["pairs"]
        with tempfile.TemporaryDirectory() as tmp:
            def mesh(chosen):
                with patch.object(ru, "source_layout", return_value=dict(planned, pairs=chosen)):
                    return ru.build_tile(None, FRAME, 0, 0, flat, None, tmp, "/vfs")[0]
            p, t, _, materials, mi = mesh(signs)
            single = mesh(signs[:1])
        atlas = materials.index("bne_signs_vienna_ru")
        self.assertEqual(np.count_nonzero(mi != atlas), 2 * np.count_nonzero(single[4] != atlas))
        face_points = p[t[mi == atlas], 0]
        self.assertEqual(len(np.unique(np.round(face_points, 4))), 4)


if __name__ == "__main__":
    unittest.main()
