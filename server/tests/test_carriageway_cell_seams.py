"""A road's per-cell clips must read the same network profile (Ekat's westbound highway)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import grading
import mapcells
from test_roads import FRAME


class CarriagewayCellSeamTest(unittest.TestCase):
    def test_different_cell_clips_share_the_original_parts_network(self):
        planner = grading._Planner(FRAME, None, None)
        full = np.array([[-4000., 0.], [0., 0.], [4000., 0.]])
        part = ('source', full, False, 'primary', 'road', 0., 5.)
        la, lo, _ = FRAME.enu_to_geodetic(0., 0., 0.)
        home = mapcells.cell_of(float(la), float(lo))
        calls = []

        def region(key):
            calls.append(key)
            # Different surrounding networks can produce different heights.
            z = 10. if key == home else 12.
            return {'parts': [part], 'prof': {'source': (full, np.full(3, z))}}

        with mock.patch.object(planner, '_cw_cell_parts', return_value=[part]), \
                mock.patch.object(planner, '_cw_region', side_effect=region):
            for clip in (full[:2], full[1:], full[::-1], full):
                got = planner._cw_z_at(clip, np.array([[0., 0.]]), 'road')
                np.testing.assert_allclose(got, [10.], atol=1e-9)
        self.assertEqual(set(calls), {home})

    def test_parallel_unrelated_parts_do_not_choose_the_network(self):
        planner = grading._Planner(FRAME, None, None)
        full = np.array([[-4000., 0.], [0., 0.], [4000., 0.]])
        part = ('source', full, False, 'primary', 'road', 0., 5.)
        other = ('other', full + [1000., 10.], False, 'primary', 'other-road', 0., 5.)
        reg = {'parts': [part], 'prof': {'source': (full, np.full(3, 10.))}}
        with mock.patch.object(planner, '_cw_cell_parts', return_value=[other, part]), \
                mock.patch.object(planner, '_cw_region', return_value=reg):
            np.testing.assert_allclose(planner._cw_z_at(full[:2], full[:2], 'road'), 10.)


if __name__ == '__main__':
    unittest.main()
