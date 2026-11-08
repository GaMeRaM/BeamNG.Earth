"""Raised sidewalks must leave slip lanes clear in both the visible and collision meshes."""
import sys
import json
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import roads
import sidewalks
import junctions
from test_roads import FRAME, features, flat, rules


def meshes(walks):
    for wk in walks:
        b = sidewalks.Builder((0, 0, 0), collision=True)
        if 'corner' in wk:
            c = wk['corner']
            b.add_corner(c['arc'], c['inward'], c['outer'], ramps=c.get('ramps', ()))
        else:
            curb, out = sidewalks.run_geometry(wk['pts'], wk['side'], wk['w'])
            b.add_run(curb, out, wk['w'], caps=wk['caps'], ramps=wk.get('ramps', ()))
        yield wk.get('fid'), b.arrays(), b.col.arrays()


def intrusions(walks, carriageways):
    hits = []
    for owner, *variants in meshes(walks):
        for p, t, *_ in variants:
            # Include triangle interiors: checking only the centreline or the slab's corners missed the defect.
            sample = np.r_[p, p[t].mean(1)]
            for fid, spec, pts, _ in carriageways:
                if fid == owner:
                    continue
                distance = roads._seg_dist(sample[:, :2], pts[:-1, :2], pts[1:, :2]).min(1)
                bad = (distance < spec.width / 2 - 0.1) & (sample[:, 2] > 10.08)
                if bad.any():
                    hits.append((owner, fid, float((spec.width / 2 - distance[bad]).max())))
    return hits


class SlipLaneClearanceTest(unittest.TestCase):
    def scene(self, angle, tx=0, node=40):
        radians = np.radians(angle)
        f = features([[(-100, 100), (600, 100)],
                      [(node, 100), (node + 220 * np.cos(radians), 100 + 220 * np.sin(radians))]],
                     ['primary', 'primary'])
        f.rules['subclass'] = rules([(1, 'link')])
        f.rules['oneway'] = rules([(1, 1.0)], 'float')
        walks, carriageways = [], []
        roads.build_tile(FRAME, tx, 0, [f], flat, lambda la, lo: np.ones(np.shape(la), bool),
                         walks=walks, roads_out=carriageways, country='RU')
        return walks, carriageways

    def test_slab_tips_clear_shallow_slip_lanes_in_both_meshes(self):
        for angle in (10, 20, 30, 45, 90):
            with self.subTest(angle=angle):
                walks, carriageways = self.scene(angle)
                self.assertTrue(walks, 'keep sidewalks outside the junction')
                self.assertEqual(intrusions(walks, carriageways), [])

    def test_slip_lane_at_a_tile_seam(self):
        for tx in (0, 1):
            with self.subTest(tx=tx):
                walks, carriageways = self.scene(20, tx=tx, node=256)
                self.assertTrue(walks)
                self.assertEqual(intrusions(walks, carriageways), [])

    def test_centreline_only_clipping_reproduces_the_reported_failure(self):
        # Prove the integration scene detects the former algorithm, even with the safer join check retained.
        with mock.patch.object(roads, 'cut_walk_outside', lambda pts, *args: [pts]):
            walks, carriageways = self.scene(20)
        self.assertTrue(intrusions(walks, carriageways))

    def test_full_profile_includes_the_sloping_back_of_a_wide_slab(self):
        pts = np.array([[0., 0., 10.], [100., 0., 10.]])
        width = 4.0
        # The slab top stops at y=2; its back extends farther and used to catch tyres on the parallel lane.
        blockers = [(np.array([[0., 5.2], [100., 5.2]]), 2.7)]
        self.assertTrue(roads._walk_blocked(pts, 1, width, blockers).all())
        self.assertEqual(roads.cut_walk_outside(pts, 1, width, blockers), [])

    def test_join_cannot_put_a_slab_back_into_a_slip_lane(self):
        def run(x0, x1, fid):
            return dict(pts=np.array([[x0, 0., 10.], [x1, 0., 10.]]), side=1, w=2.5,
                        fid=fid, j=(False, False), open=(True, True))
        lane = [(np.array([[10.8, 2.], [11.2, 2.]]), 0.8)]
        self.assertEqual(len(roads.join_walk_ends([run(0, 10, 'a'), run(12, 22, 'b')], [])), 1)
        self.assertEqual(len(roads.join_walk_ends([run(0, 10, 'a'), run(12, 22, 'b')], lane)), 2)


class EkatCornerClearanceTest(unittest.TestCase):
    def test_generated_makarovsky_corners_cross_a_carriageway(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/ekb_walk_corners.json').read_text())
        for row in fixture['rows']:
            corner = {key: np.asarray(value) for key, value in row['corner'].items()}
            road = row['road']
            spec = roads.Spec(road['half'] * 2, 'paved', True, 'secondary', False)
            carriageways = [(road['fid'], spec, np.asarray(road['points']), 60.59)]
            centre = corner['arc'][:, :2].mean(axis=0)
            with self.subTest(road=road['fid']):
                self.assertEqual(junctions.corner_on_carriageway(corner, carriageways, (centre, 100)), road['fid'])
                # An otherwise identical slab clear of the road must remain eligible.
                away = {key: value + [200, 200, 0] for key, value in corner.items() if key != 'inward'}
                away['inward'] = corner['inward']
                self.assertIsNone(junctions.corner_on_carriageway(away, carriageways, (centre + 200, 100)))


if __name__ == '__main__':
    unittest.main()
