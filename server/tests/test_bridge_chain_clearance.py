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



class LongDividedOverpassTest(unittest.TestCase):
    def setUp(self):
        # The coupled bridge network is opt-in, matching upstream.
        patcher = mock.patch.object(grading, "CW_ON", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_long_trunk_uses_one_continuous_road_and_deck_profile(self):
        from test_roads import features
        # The junction 10 m before the abutment must be free to move with its
        # branch. Solving/fixing the ground-only chains first makes this
        # clearance impossible within the bridge's grade limit.
        f = features([[(-600., 0.), (-80., 0.)], [(-80., 0.), (-70., 0.)],
                      [(-70., 0.), (70., 0.)], [(70., 0.), (600., 0.)],
                      [(0., -600.), (0., 600.)], [(-80., 0.), (-80., 400.)]],
                     ['trunk'] * 5 + ['unclassified'], flags=[(2, 'is_bridge')])
        flat = lambda la, lo: np.full(np.shape(la), 100.)
        g = grading.Grader(FRAME, FakeMD(f), flat)
        def elev(la, lo):
            return g.apply(la, lo, flat(la, lo), grading.ROAD_LIFT)
        store = roads.ChainStore(roads.BridgeProfiles, lambda key: f, elev)
        with mock.patch.object(grading, '_ACTIVE_STORE', g.store):
            view = roads.ChainView(store, FRAME)
            parts = view.parts([f], (-256., -256., 256., 256.))
            self.assertEqual(len(parts), 1)
            fid, spec, xy, z, _ = parts[0]
            arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
            self.assertLessEqual(float(np.max(np.abs(np.diff(z) / np.diff(arc)))), .062)  # sampled mesh: 0.2 percentage-point allowance
            la, lo, _ = FRAME.enu_to_geodetic(xy[[0, -1], 0], xy[[0, -1], 1], 0.)
            _, _, approach = FRAME.geodetic_to_enu(la, lo, elev(la, lo))
            np.testing.assert_allclose(z[[0, -1]], approach, atol=.08)
            la, lo, _ = FRAME.enu_to_geodetic(np.array([0.]), np.array([0.]), 0.)
            _, _, below = FRAME.geodetic_to_enu(la, lo, elev(la, lo))
            clearance = np.interp(arc[-1] / 2, arc, z) - below[0] - view.depth_of(fid)
            self.assertGreaterEqual(clearance, 5.9)



class M12ServiceJoinTest(unittest.TestCase):
    """Captured service access, with the experimental coupled network enabled."""
    def setUp(self):
        patcher = mock.patch.object(grading, "CW_ON", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_access_profile_keeps_headroom_and_does_not_punch_the_carriageway(self):
        fixture = Path(__file__).parent / 'fixtures'
        rows = json.loads((fixture / 'ekb_m12_service_join.json').read_text())['roads']
        f = roads_of(rows)
        with np.load(fixture / 'ekb_m12_dem.npz') as dem:
            xs, ys, zgrid = dem['x'], dem['y'], dem['z']
        def raw(la, lo):
            e, n, _ = FRAME.geodetic_to_enu(la, lo, np.zeros(np.shape(la)))
            x = np.clip((e - xs[0]) / 40., 0., len(xs) - 1.00001)
            y = np.clip((n - ys[0]) / 40., 0., len(ys) - 1.00001)
            i, j = x.astype(int), y.astype(int)
            a, b = x - i, y - j
            return ((1 - b) * ((1 - a) * zgrid[j, i] + a * zgrid[j, i + 1])
                    + b * ((1 - a) * zgrid[j + 1, i] + a * zgrid[j + 1, i + 1]))
        g = grading.Grader(FRAME, FakeMD(f), raw)
        def elev(la, lo):
            return g.apply(la, lo, raw(la, lo), grading.ROAD_LIFT)
        store = roads.ChainStore(roads.BridgeProfiles, lambda key: f, elev)
        profiles = roads.ChainView(store, FRAME)
        chunks = []
        for tx, ty in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
            chunks += roads.build_tile(FRAME, tx, ty, [f], elev, bridges=profiles, walks=[])
        mesh = roadmesh.deck(chunks, (0, 0, 0))
        checked = 0
        for fid, sp, xy, z, _ in profiles.parts([f], (-150, -150, 150, 150)):
            for _, _, point in roads._crossings_by([xy], [np.asarray(rows[2]['xy'])])[0]:
                pts = np.asarray([point])
                ground = roadmesh.drawn_ground(FRAME, elev, pts)
                hit = heights(mesh, pts)[0]
                self.assertTrue(len(hit))
                self.assertGreaterEqual(float(min(hit) - ground[0]), 5.)
                checked += 1
        self.assertEqual(checked, 2, 'both carriageways span the underpass')
        x = np.arange(-35., 21., 2.)
        for side in (-4., -2., 0., 2., 4.):
            y = 1.418 - .229 * x + side
            la, lo, _ = FRAME.enu_to_geodetic(x, y, 0.)
            z = roadmesh.drawn_ground(FRAME, elev, np.c_[x, y])
            self.assertLess(float(np.max(np.abs(np.diff(z)))), .35, 'no metre-scale hole at the access junction')


if __name__ == "__main__":
    unittest.main()


class BridgeTerrainFloorTest(unittest.TestCase):
    def test_long_bridge_cannot_bury_either_lane_in_a_hillside(self):
        from test_roads import features
        xy = np.c_[np.linspace(-600., 600., 301), np.zeros(301)]
        f = features([xy], ['trunk'], flags=[(0, 'is_bridge')])

        def terrain(la, lo):
            x, y, _ = FRAME.geodetic_to_enu(la, lo, 0.)
            # A long mapped bridge's middle crosses rising terrain and a bank
            # beside its axis, while both abutments are lower (Revda, M-12).
            return 100. + 5. * np.exp(-(np.asarray(x) / 180.) ** 2) + .25 * np.asarray(y)

        p = grading._Planner(FRAME, FakeMD(f), terrain)
        key = ('b', -600., 0., 600., 0.)
        part = (key, xy, True, 'trunk', str(f.ids[0]), 1., 5.)
        profiles = p._cw_cluster_solve([([part], [(0, False)])])
        q, z = profiles[key]
        for side in (-5., 0., 5.):
            la, lo, _ = FRAME.enu_to_geodetic(q[:, 0], q[:, 1] + side, 0.)
            self.assertGreaterEqual(float(np.min(z - terrain(la, lo))), grading.ROAD_LIFT)
