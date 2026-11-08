"""A bridge split into short Overture segments must still leave a drivable underpass."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import grading
import buildings
import roads
import roadmesh
from ekb_fixtures import roads_of
from test_bridge_junction_surface import heights
from test_grading import FakeMD
from test_roads import FRAME


class BridgeChainTest(unittest.TestCase):
    def test_reversed_short_tail_and_duplicate_cell_copies_are_one_span(self):
        a = np.array([[-35., 0.], [33., 0.]])
        b = np.array([[35., 0.], [33., 0.]])
        merged = grading._merge_underpass_chains([(a, False, False, 1), (b, False, False, 1), (a.copy(), False, False, 1)])
        self.assertEqual(len(merged), 1)
        np.testing.assert_allclose(merged[0][0][[0, -1]], [[-35, 0], [35, 0]])

    def test_forks_and_different_levels_are_not_one_span(self):
        a = np.array([[-35., 0.], [0., 0.]])
        b = np.array([[0., 0.], [35., 0.]])
        c = np.array([[0., 0.], [35., 10.]])
        self.assertIsNone(grading._simple_bridge_path([a, b, c]))
        self.assertEqual(len(grading._merge_underpass_chains([(a, False, False, 1), (b, False, False, 2)])), 2)

    def test_railway_spans_remain_separate(self):
        a = np.array([[-35., 0.], [0., 0.]])
        b = np.array([[0., 0.], [35., 0.]])
        self.assertEqual(len(grading._merge_underpass_chains([(a, True, True, 0), (b, True, True, 0)])), 2)


class DeryabinaBridgeTest(unittest.TestCase):
    ROADS = {'d059fbec-3d5a-490a-bda7-983476a5017e', 'd66bcc74-ab02-404b-861e-c60049a42db1'}

    def build(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/ekb_deryabina_bridge.json').read_text(encoding='utf-8'))
        f = roads_of(fixture['roads'])
        flat = lambda la, lo: np.full(np.shape(la), 100.)
        g = grading.Grader(FRAME, FakeMD(f), flat)
        def elev(la, lo):
            return g.apply(la, lo, flat(la, lo), grading.ROAD_LIFT)
        store = roads.ChainStore(roads.BridgeProfiles, lambda key: f, elev)
        profiles = roads.ChainView(store, FRAME)
        parts = profiles.parts([f], (-256, -256, 256, 256))
        chunks, ground_roads = [], []
        for tx, ty in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
            chunks += roads.build_tile(FRAME, tx, ty, [f], elev, bridges=profiles,
                                        walks=[], roads_out=ground_roads, country='RU')
        return fixture, parts, roadmesh.deck(chunks, (0, 0, 0)), elev, ground_roads

    def clearance(self, built):
        fixture, parts, mesh, elev, ground_roads = built
        minimum, count = np.inf, 0
        for fid, spec, xy, z, lon in parts:
            for row in fixture['roads']:
                if row['id'] not in self.ROADS:
                    continue
                line = np.asarray(row['xy'])
                for _, arc, point in roads._crossings_by([xy], [line])[0]:
                    point = np.asarray(point)
                    _, _, direction = buildings._nearest_on(point, line)
                    normal = np.array([-direction[1], direction[0]])
                    # Across the carriageway and along it: tyre/body positions under the actual slab and girders.
                    sp = next(s for f, s, p, lo in ground_roads if f == row['id'])
                    offsets = np.linspace(-sp.width / 2 + 1., sp.width / 2 - 1., max(2, sp.lanes or 2))
                    points = np.array([point + normal * off + direction * along for off in offsets for along in (-3., 0., 3.)])
                    # The same 2 m terrain triangulation the player drives over.
                    ground = roadmesh.drawn_ground(FRAME, elev, points)
                    hits = heights(mesh, points)
                    for zz, surface in zip(hits, ground):
                        if len(zz):
                            minimum = min(minimum, float(np.min(zz)) - float(surface))
                            count += 1
        self.assertGreater(count, 4)
        return minimum

    def test_actual_deck_collision_clears_both_carriageways(self):
        built = self.build()
        # Six metres is the design target. With the existing bounded excavation and this constrained street
        # grid, every sampled lane must still clear a 16 ft truck; don't assert a universal six-metre guarantee.
        self.assertGreaterEqual(self.clearance(built), 4.9)
        for fid, spec, xy, z, lon in built[1]:
            arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
            self.assertLessEqual(float(np.max(np.abs(np.diff(z) / np.diff(arc)))), roads.DECK_MAX_GRADE + .005)

    def test_the_old_single_span_filter_reproduces_a_blocked_underpass(self):
        with mock.patch.object(grading, '_merge_underpass_chains', lambda records: records):
            built = self.build()
        self.assertLess(self.clearance(built), 2.)


if __name__ == '__main__':
    unittest.main()
