"""Mapped covered driveways retain their upper floors and have clear rendering and collision paths."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import buildings as bld
import buildingpassages
from ekb_fixtures import roads_of
from test_buildings import Feats, rect
from test_bridge_junction_surface import heights
from test_roads import FRAME, features, rules


def segment_hits(mesh, a, b, altitude, offset=0.0):
    p, uv, tri, mi, mats, *_ = mesh
    delta = np.asarray(b) - a
    length = np.linalg.norm(delta)
    u = delta / length
    v = np.array([-u[1], u[0]])
    xy = p[:, :2] - (a + b) / 2
    transformed = np.c_[xy @ v, p[:, 2], xy @ u]
    hits = heights((transformed, tri, uv, mats, mi), [[offset, altitude]])[0]
    return hits[np.abs(hits) <= length / 2 + 1e-5]


class BuildingPassageTest(unittest.TestCase):
    def items(self):
        spec = bld.plan(rect(-10, -6, 20, 12), {'class': 'apartments', 'num_floors': 9}, lat=56.83, lon=60.58)
        return [(spec, 0., 0.)]

    def test_one_storey_opening_keeps_the_facade_above_and_the_side_walls(self):
        old = self.items()
        line = np.array([[-12., 0.], [12., 0.]])
        new = buildingpassages.apply(old, [(line, 4., None)])
        self.assertGreater(len(new), 1)
        for builder in (bld.build, bld.collision_mesh):
            self.assertTrue(len(segment_hits(builder(old), *line, 1.5)))
            mesh = builder(new)
            for offset in (-.9, 0., .9):
                self.assertEqual(len(segment_hits(mesh, *line, 1.5, offset)), 0)
            self.assertTrue(len(segment_hits(mesh, *line, bld.FLOOR_M + 1.)))
            self.assertTrue(len(segment_hits(mesh, *line, 1.5, 4.)))
        self.assertAlmostEqual(max((s.min_h or 0) + s.height for s, _, _ in new), old[0][0].height)
        roof = next(s for s, _, _ in new if s.min_h == bld.FLOOR_M)
        self.assertEqual(roof.floors, 8)
        self.assertEqual(bld.collider_boxes(new, 0, 0), [], 'a car inside the arch must not hold back the whole collision mesh')

    def test_cut_facade_keeps_original_uvs_on_both_sides_and_above_the_arch(self):
        items = self.items()
        source = items[0][0]
        cuts = [(np.array([[0., -9.], [0., 9.]]), 4., 4.5)]
        fragments = buildingpassages.apply(items, cuts)

        def wall_mesh(items, lite):
            mesh = bld.Mesh()
            for spec, _, _ in items:
                z0 = -bld.SKIRT_M if not spec.min_h else spec.min_h
                bld._walls(mesh, spec, spec.ring, z0, (spec.min_h or 0) + spec.height,
                           bld._Looks(spec.seed), lite)
            return mesh.arrays()

        def sample(mesh, point):
            positions, uv, triangles, materials, colors = mesh
            for indices, material in zip(triangles, materials):
                p = positions[indices]
                ab = (p[1:] - p[0]).T
                weights, *_ = np.linalg.lstsq(ab, point - p[0], rcond=None)
                if (np.linalg.norm(ab @ weights - (point - p[0])) < 1e-7
                        and min(weights) >= -1e-7 and sum(weights) <= 1 + 1e-7):
                    return material, uv[indices[0]] + weights @ (uv[indices[1:]] - uv[indices[0]])
            self.fail(f'No facade at {point}')

        for lite in (False, True):
            original, cut = wall_mesh(items, lite), wall_mesh(fragments, lite)
            for x, z in ((-8., 1.5), (8., 1.5), (-8., 4.4), (0., 4.6), (0., 10.5), (8., 22.5)):
                point = np.array([x, -6., z])
                before, after = sample(original, point), sample(cut, point)
                self.assertEqual(before[0], after[0])
                np.testing.assert_allclose(before[1], after[1], atol=1e-8)

    def test_mapped_clearances_apply_to_each_opening_independently(self):
        a = np.array([[-12., -3.], [12., -3.]])
        b = np.array([[-12., 3.], [12., 3.]])
        new = buildingpassages.apply(self.items(), [(a, 2.5, None), (b, 2.5, 4.5)])
        mesh = bld.collision_mesh(new)
        self.assertTrue(len(segment_hits(mesh, *a, 3.5)))
        self.assertEqual(len(segment_hits(mesh, *b, 3.5)), 0)
        self.assertTrue(len(segment_hits(mesh, *b, 5.)))

    def test_untagged_or_underground_roads_do_not_cut_a_house(self):
        f = features([[(-20, 0), (20, 0)]], ['service'])
        self.assertEqual(buildingpassages.collect(FRAME, [f], -256, -256, 512), [])
        f.rules['flags'] = rules([(0, 'is_tunnel')])
        f.rules['level'] = rules([(0, -1.)], 'float')
        self.assertEqual(buildingpassages.collect(FRAME, [f], -256, -256, 512), [])

    def test_an_existing_elevated_building_keeps_its_mapped_clearance(self):
        items = self.items()
        items[0][0].min_h = 4.
        self.assertIs(buildingpassages.apply(items, [(np.array([[-12., 0.], [12., 0.]]), 4., None)])[0][0], items[0][0])

    def test_enclosed_garage_hole_is_not_misrendered_as_a_solid_polygon(self):
        items = self.items()
        result = buildingpassages.apply(items, [(np.array([[-2., 0.], [2., 0.]]), 2., None)])
        self.assertEqual(len(result), 1)
        self.assertIs(result[0][0], items[0][0])


class EkatMappedPassagesTest(unittest.TestCase):
    def test_real_covered_ranges_clear_the_reported_driveways(self):
        data = json.loads((Path(__file__).parent / 'fixtures/ekb_building_passages.json').read_text(encoding='utf-8'))
        roads = roads_of(data['roads'])
        passages = buildingpassages.collect(FRAME, [roads], -256, -256, 512)
        self.assertEqual(len(passages), 3)
        checked = 0
        for row in data['buildings']:
            xy = np.asarray(row['xy'])
            lat, lon, _ = FRAME.enu_to_geodetic(xy[:, 0], xy[:, 1], 0.)
            f = Feats([row['id']], [np.c_[lon, lat]], **{'class': ['apartments'], 'num_floors': [9.]})
            old = bld.tile_buildings(FRAME, -256, -256, 256, 256, [f], lambda la, lo: np.zeros(np.shape(la)))
            new = bld.tile_buildings(FRAME, -256, -256, 256, 256, [f], lambda la, lo: np.zeros(np.shape(la)), passages_xy=passages)
            self.assertGreater(len(new), len(old))
            for line, width, height in passages:
                if not bld._inside(old[0][0].ring, line.mean(axis=0)):
                    continue
                for a, b in zip(line[:-1], line[1:]):
                    if np.linalg.norm(b - a) < 1e-5:
                        continue
                    for builder in (bld.build, bld.collision_mesh):
                        for offset in (-.9, 0., .9):
                            self.assertEqual(len(segment_hits(builder(new), a, b, 1.5, offset)), 0, row['id'])
                    checked += 1
        self.assertGreaterEqual(checked, 3)


if __name__ == '__main__':
    unittest.main()
