"""The Prizma's verified missing middle volume, without moving legitimate elevated parts."""
import sys,unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import buildingoverrides, buildings
from test_roads import FRAME
from test_buildings import Feats
import numpy as np

class MissingPartsTest(unittest.TestCase):
    BID = '9601607f-fce9-45e1-ab15-5e16148a29e9'
    def test_source_range_and_shape(self):
        rows = buildingoverrides.missing(FRAME, self.BID, ())
        self.assertEqual(len(rows), 1)
        ring, (height, bottom), own = rows[0]
        self.assertEqual((height, bottom), (72., 50.4))
        self.assertEqual(own['source'], 'r2673798')
        self.assertGreater(len(ring), 3)
    def test_new_overture_copy_wins_and_other_parents_are_untouched(self):
        self.assertEqual(buildingoverrides.missing(FRAME,self.BID,['r2673798@99']), [])
        self.assertEqual(buildingoverrides.missing(FRAME,'another-building',()), [])
    def test_shared_parts_lookup_includes_the_supplement(self):
        rows = buildings._PartsOf(FRAME, []).get(self.BID)
        self.assertEqual(rows[0][1], (72.,50.4))
