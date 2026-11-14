import sys, unittest, time
from pathlib import Path
from unittest import mock
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import carriageways as cw
class ComponentsTest(unittest.TestCase):
    def road(self, n):
        t=np.array([float(n),float(n)+1,float(n)])
        return dict(t=t,w=np.ones(3),grade=10.,K=10.,lam=1.,step=1.,length=1.)
    def test_matches_whole_separable_problem(self):
        roads=[self.road(i) for i in range(4)]
        cp=[(0,1,2,1,'eq',0.)]
        a,b={},{}
        whole=cw.solve(roads,cp,diagnostics=a)
        split=cw.solve_components(roads,cp,diagnostics=b)
        self.assertTrue(a['converged'] and b['converged'])
        for x,y in zip(whole,split): np.testing.assert_allclose(x,y,atol=1e-6)
    def test_remapping_and_shared_deadline(self):
        roads=[self.road(i) for i in range(4)]
        calls=[]
        def solve(chains,cp,deadline,diagnostics):
            calls.append((len(chains),cp,deadline));diagnostics.update(converged=True)
            return [c['t'] for c in chains]
        with mock.patch.object(cw,'solve',side_effect=solve):
            out=cw.solve_components(roads,[(0,1,2,1,'ge',6.)],deadline=123.)
        self.assertEqual([x[0] for x in calls],[2,1,1])
        self.assertEqual(calls[0][1],[(0,1,1,1,'ge',6.)])
        self.assertTrue(all(c[2]==123. for c in calls))
        for r,z in zip(roads,out):np.testing.assert_array_equal(r['t'],z)
if __name__=='__main__': unittest.main()
