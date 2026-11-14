import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import beaches
class PrefixTest(unittest.TestCase):
    def test_exact_prefix(self):
        rng = np.random.default_rng(56)
        for shape in [(2, 3), (127, 193), (1024, 1024)]:
            for r in [0, 1, 20, 80]:
                for edge in [False, True]:
                    m = rng.random(shape) < .4
                    a = np.pad(m.astype(np.int32), ((r+1,r),(r+1,r)), mode='edge' if edge else 'constant')
                    c = a.cumsum(0).cumsum(1)
                    ref = c[2*r+1:,2*r+1:] - c[:-2*r-1,2*r+1:] - c[2*r+1:,:-2*r-1] + c[:-2*r-1,:-2*r-1]
                    np.testing.assert_array_equal(beaches._box_sum(m,r,edge),ref)
if __name__ == '__main__': unittest.main()
