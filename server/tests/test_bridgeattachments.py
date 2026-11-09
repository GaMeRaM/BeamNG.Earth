"""Companions of a road bridge share its surface, not an independent DEM fit."""
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import bridgeattachments
import railways
from test_roads import FRAME, features


class SharedSurfaceTest(unittest.TestCase):
    def test_parallel_companions_interpolate_the_actual_deck(self):
        deck = {'n': [[0., 0., 20.], [100., 0., 22.]], 'w': 14., 'level': 1.}
        xy = np.array([[10., 3.], [50., 3.], [90., 3.]])
        z, covered = bridgeattachments.surface(xy, [deck], 1.)
        np.testing.assert_allclose(z, [20.2, 21., 21.8])
        self.assertTrue(covered)
        self.assertFalse(bridgeattachments.surface(xy + [0., 5.], [deck], 1.)[1])

    def test_crossings_and_different_levels_do_not_attach(self):
        deck = {'n': [[0., 0., 20.], [100., 0., 20.]], 'w': 14., 'level': 1.}
        self.assertIsNone(bridgeattachments.surface([[50., -3.], [50., 3.]], [deck], 1.))
        self.assertIsNone(bridgeattachments.surface([[10., 0.], [90., 0.]], [deck], 1., level=2.))

    def test_overlap_mask_does_not_cover_a_walkway_past_the_abutment(self):
        deck = {'n': [[0., 0., 20.], [100., 0., 20.]], 'w': 14., 'level': 1.}
        _, overlaps = bridgeattachments.surface([[90., 6.5], [100., 6.5], [104., 6.5]],
                                                [deck], 1., reach=10., overlap_mask=True)
        np.testing.assert_array_equal(overlaps, [True, True, False])

    def test_fixed_tram_height_propagates_to_its_connected_approach(self):
        rails = [('approach', 'tram', 'ground', np.array([[0., 0.], [50., 0.]])),
                 ('bridge', 'tram', 'bridge', np.array([[50., 0.], [100., 0.]]))]
        result = railways.profile(rails, lambda xy: np.full(len(xy), 10.),
                                  fixed_decks={1: np.array([12., 12.])})
        self.assertAlmostEqual(result[0][0][-1], 12.)
        np.testing.assert_array_equal(result[1][0], [12., 12.])

    def test_embedded_tram_mesh_and_returned_surface_are_at_road_height(self):
        f = features([[(30., 100.), (220., 100.)]], ['tram'],
                     subtypes=['rail'], flags=[(0, 'is_bridge')])
        decks = [{'n': [[0., 100., 20.], [256., 100., 20.]], 'w': 14., 'level': 1.}]
        mesh, result = railways.tile_mesh(FRAME, 0, 0, [f],
                                         lambda xy: np.full(len(xy), 10.),
                                         return_decks=True, road_decks=decks)
        self.assertIsNotNone(mesh)
        self.assertEqual(len(result), 1)
        np.testing.assert_allclose(result[0]['n'][:, 2], 20., atol=1e-6)
        p, t, _, mats, m = mesh
        steel = p[np.unique(t[m == mats.index(railways.STEEL)])]
        self.assertAlmostEqual(float(steel[:, 2].max()), 20.005, places=4)


if __name__ == '__main__':
    unittest.main()
