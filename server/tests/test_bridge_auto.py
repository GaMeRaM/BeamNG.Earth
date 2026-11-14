import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import grading, roads, roadmesh, revisit
from interchanges import load
from test_bridge_junction_surface import heights
class AutoBridgeTest(unittest.TestCase):
    def test_large_network_stays_opt_in(self):
        with mock.patch.object(grading._xs, 'ON', False), mock.patch.object(grading, 'CW_MODE', 'auto'):
            self.assertFalse(grading._cw_auto_allowed([([], [])] * 65))
            part = ('road', np.array([[0.,0.], [50000.,0.]]), False, 'motorway')
            self.assertFalse(grading._cw_auto_allowed([([part], [(0,False)])]))
        with mock.patch.object(grading, 'CW_MODE', 'on'):
            self.assertTrue(grading._cw_auto_allowed([([], [])] * 65))
    def test_auto_is_scoped_to_paired_short_highway_overpasses(self):
        def part(fid, xy, bridge, cls='trunk'):
            return ((fid,), np.array(xy, dtype=float), bridge, cls, fid, float(bridge), 5.)
        upper=[part('a',[[0,0],[140,0]],True),part('b',[[0,12],[140,12]],True)]
        lower=[part('c',[[60,-100],[60,100]],False),part('d',[[80,-100],[80,100]],False)]
        pack=lambda ps: [([p],[(0,False)]) for p in ps]
        with mock.patch.object(grading._xs,'ON',False), mock.patch.object(grading,'CW_MODE','auto'):
            self.assertTrue(grading._cw_auto_allowed(pack(upper+lower)))
            self.assertFalse(grading._cw_auto_allowed(pack(upper+lower[:1])))
            self.assertFalse(grading._cw_auto_allowed(pack(upper+[part('c',[[60,-100],[60,100]],False,'secondary'),lower[1]])))
            long=[part('a',[[0,0],[400,0]],True),part('b',[[0,12],[400,12]],True)]
            self.assertFalse(grading._cw_auto_allowed(pack(long+lower)))

    def test_reported_vostok_bridge_clears_traffic(self):
        self._reported_bridge("vostok_low")

    def test_reported_m12_bridge_clears_traffic(self):
        self._reported_bridge("m12_west_low")

    def _reported_bridge(self, name):
        site = load(name, prefix='bridge')
        md = SimpleNamespace(cell=lambda key, **kw: SimpleNamespace(layers={'roads':site.cells.get(str(key))}))
        with mock.patch.object(revisit, 'ON', False), mock.patch.object(grading, 'CW_ON', True), \
             mock.patch.object(grading, 'CW_MODE', 'auto'), mock.patch.object(grading._xs, 'ON', False):
            store = grading.PlanStore(md, site.sample)
            store.frame_of = lambda region: site.frame
            grader = grading.Grader(site.frame, md, site.sample, store=store)
            def elev(la, lo): return grader.apply(la,lo,site.sample(la,lo),grading.ROAD_LIFT)
            bridges = roads.BridgeProfiles(site.frame, lambda key: site.cells.get(str(key)), elev)
            cells = list(site.cells.values())
            minimum, checked = np.inf, 0
            for tx,ty in [(-1,-1),(0,-1),(-1,0),(0,0)]:
                ground=[]
                chunks=roads.build_tile(site.frame,tx,ty,cells,elev,bridges=bridges,walks=[],roads_out=ground,country='RU')
                mesh=roadmesh.deck(chunks,(0,0,0))
                for fid, spec, xy,z,_ in bridges.parts(cells,roads.tile_bbox(tx,ty)):
                    if str(fid) not in {'7ca294f9-317f-4fbb-a39d-71c7bb1b3620','f5b2bcfe-5b15-4235-b87b-c194e02436bf', 'fb1ac4a0-89b4-4580-97f6-1ec7d323b7c4'}: continue
                    arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
                    self.assertLessEqual(float(np.max(abs(np.diff(z)/np.diff(arc)))),.065)
                    for _,sp,line,_ in ground:
                        for _,at,pt in roads._crossings_by([xy],[line])[0]:
                            if min(at,arc[-1]-at)<10 or np.linalg.norm(pt)>150: continue
                            points=np.array([pt])
                            floor=roadmesh.drawn_ground(site.frame,elev,points)
                            hit=heights(mesh,points)[0] if mesh is not None else []
                            if len(hit): minimum=min(minimum,float(np.min(hit))-float(floor[0]));checked+=1
            self.assertGreater(checked,0)
            self.assertGreaterEqual(minimum,4.9)
if __name__=='__main__': unittest.main()
