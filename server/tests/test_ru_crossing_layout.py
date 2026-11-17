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
import roads, signstream
from test_roads import FRAME, features, flat


def scene(oneway=False, direction=1):
    f = features([[(10.0, 100.0), (240.0, 100.0)]], ["tertiary"], widths=[(0, 10.0)])
    s = roads.road_specs(f)[0]._replace(
        oneway=oneway, dir=direction, lanes=1 if oneway else 2
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
        six = ru.layout([(fid, sp._replace(lanes=6, width=21.0), xyz, lon)], nodes())
        self.assertEqual(sum(bool(s.get("overhead")) for s in six["pairs"]), 2)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(ru, "source_layout", return_value=six),
        ):
            pair, _, _ = ru.build_tile(None, FRAME, 0, 0, flat, None, tmp, "/vfs")
            p = pair[0]
            self.assertFalse(np.any((abs(p[:, 1] - 100.0) < 10.5) & (p[:, 2] < 15.4)))

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


if __name__ == "__main__":
    unittest.main()
