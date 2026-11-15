"""Neighbor-cell copies of a bridge must not become continuations at BOTH abutments.

Fixture: reported road over the railway at 57.24311,61.17673, Overture 2026-10-21.0.
The two ENU copies differ by <= 10 micrometres. Exact identity suppressed both approach
lifts and left a 66% end segment in the real generated deck (.67).
"""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fast
import grading


class BridgeCopyTest(unittest.TestCase):
    def setUp(self):
        with np.load(Path(__file__).with_name('fixtures') / 'rezhev_rail_bridge_copy.npz') as f:
            self.bridge, self.copy, self.rail = (f[k].copy() for k in ('bridge', 'copy', 'rail'))

    def test_neighbor_cell_copy_leaves_both_abutments_free(self):
        line, copy = self.bridge, self.copy
        self.assertGreater(float(np.max(np.abs(line - copy))), 0)
        self.assertLess(float(np.max(np.abs(line - copy))), 0.0001)
        self.assertEqual(grading.bridge_chain(line, [line, copy]), [])
        for end in line[[0, -1]]:
            self.assertTrue(grading.bridge_chain_ends_free(line, [line, copy], end))

    def test_railway_clearance_raises_approaches_despite_duplicate_copy(self):
        line, copy = self.bridge, self.copy
        ground = lambda xy: np.full(len(xy), 240.)
        expected = grading.bridge_lifts(line, [line], [], ground, rail_lines=[self.rail])
        actual = grading.bridge_lifts(line, [line, copy], [], ground, rail_lines=[self.rail])
        self.assertEqual(len(actual), 2)
        self.assertEqual(len(expected), 2)
        for (end, lift), (base_end, base_lift) in zip(actual, expected):
            np.testing.assert_array_equal(end, base_end)
            self.assertAlmostEqual(lift, base_lift, places=8)
            self.assertGreater(lift, 7.)

    def test_real_continuation_is_still_joined(self):
        line = self.bridge
        next_line = np.stack([line[-1], line[-1] + (line[-1] - line[-2]) * 10])
        all_lines = [line, self.copy, next_line]
        chain = grading.bridge_chain(line, all_lines)
        self.assertEqual(len(chain), 1)
        np.testing.assert_array_equal(chain[0], next_line)
        self.assertTrue(grading.bridge_chain_ends_free(line, all_lines, line[0]))
        self.assertFalse(grading.bridge_chain_ends_free(line, all_lines, line[-1]))

    def test_a_nearby_distinct_line_is_not_a_coordinate_copy(self):
        line = self.bridge
        nearby = line + np.array([0.001, 0.])
        # Even 1 mm is outside the identity allowance. Preserve the existing spatial join rule.
        got = fast._ef.plan_bridges_joined([line, nearby], line, np.ascontiguousarray(line[[0, -1]]), .75, True)
        self.assertEqual(list(got), [True, True])


if __name__ == '__main__':
    unittest.main()
