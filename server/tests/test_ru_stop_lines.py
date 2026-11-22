"""Stop markings at Russian signals must not depend on sidewalk generation."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import roads
from test_roads import FRAME, features, flat


class RussianSignalStops(unittest.TestCase):
    def chunks(self, walks=None, country='RU', signal=True):
        centre = (100.,100.)
        ls = [[centre,(100.+dx*80,100.+dy*80)] for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]]
        f = features(ls, ['tertiary']*4, widths=[(i,10.) for i in range(4)])
        return roads.build_tile(FRAME,0,0,[f],flat,walks=walks,country=country,
                                signals=np.array([[100.,100.]]) if signal else np.empty((0,2)))

    def stops(self, **kw):
        return [c for c in self.chunks(**kw) if c['m']=='line_white' and c['w']==.4]

    def test_signal_stop_lines_exist_without_sidewalk_output(self):
        self.assertEqual(len(self.stops()),4)

    def test_sidewalk_output_does_not_duplicate_signal_lines(self):
        self.assertEqual(len(self.stops(walks=[])),4)

    def test_no_automatic_signal_lines_without_signal(self):
        self.assertFalse(self.stops(signal=False))

    def test_other_country_keeps_existing_behavior(self):
        self.assertFalse(self.stops(country='US'))


class RussianMappedZebras(unittest.TestCase):
    def test_midblock_node_paints_without_sidewalks(self):
        f=features([[(10.,100.),(200.,100.)]],['tertiary'])
        nodes={'ru_crossings':[(100.,100.,1)], 'stop_lines':np.empty((0,2)), 'priority':np.empty((0,3))}
        chunks=roads.build_tile(FRAME,0,0,[f],flat,country='RU',nodes=nodes,signals=np.empty((0,2)))
        zebras=[c for c in chunks if c['m']=='line_white' and c['w']==4.]
        self.assertGreater(len(zebras),1)
        for stripe in zebras:
            self.assertAlmostEqual(float(np.linalg.norm(np.diff(np.array(stripe['n'])[:,:2],axis=0)[0])),.5,places=2)
        self.assertEqual(zebras[0]['w'],4.0)
        self.assertAlmostEqual(np.mean(np.array(zebras[0]['n'])[:,0]),100.,places=2)

    def test_wide_mapped_zebra_emits_pedestrian_arrows(self):
        import secrossings
        from test_secrossings import Frame, Infra
        infra = Infra([("crossing", (10., 10.),
                        {"highway": "crossing", "crossing": "marked", "width": "8 m"})])
        nodes = secrossings.nodes(Frame(), [infra])
        f = features([[(10., 100.), (200., 100.)]], ["tertiary"], widths=[(0, 10.)])
        chunks = roads.build_tile(FRAME, 0, 0, [f], flat, country="RU", nodes=nodes,
                                  signals=np.empty((0, 2)))
        arrows = [c for c in chunks if c["m"] == "line_white" and len(c.get("poly", ())) == 3]
        self.assertEqual(len(arrows), 6)

    def test_ru_nodes_use_same_eligibility_as_signs(self):
        import secrossings
        from test_secrossings import Frame,Infra
        tags=[{'crossing':'marked'}, {'crossing':'traffic_signals'},
              {'crossing':'unmarked'}, {'crossing:markings':'no'},
              {'crossing:markings':'zebra'}, {'crossing':'marked','foot':'no'},
              {'crossing:markings':'surface'}, {'crossing:markings':'lines'}]
        n=secrossings.nodes(Frame(),[Infra([('crossing',(i,1),{'highway':'crossing',**t}) for i,t in enumerate(tags)])])
        self.assertEqual([v[2] for v in n['ru_crossings']],[1,1,0,0,1,0,0,0])
        self.assertTrue(secrossings.wanted('RU'))


if __name__=='__main__':
    unittest.main()
