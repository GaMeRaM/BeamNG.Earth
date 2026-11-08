"""Russian data coverage, posted exit labels, Cyrillic rendering and material-safe mesh joins."""
import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dirsigns
import rusigns


class RussianSignsTest(TestCase):
    def test_place_snapshot_includes_ural_control_cities(self):
        pl=dirsigns.places()
        for city in ['Екатеринбург','Первоуральск','Ревда','Нижний Тагил','Тюмень','Челябинск']:
            self.assertTrue(any(n==city and cc=='RU' for n,cc in zip(pl.names,pl.cc)),city)

    def test_national_regional_and_european_refs(self):
        style=dirsigns.styles()['countries']['RU']
        for network,ref,plate in [('RU:national','М-12','national'),('ru:federal','Р242','national'),
                                  ('ru:regional','65К-001','regional'),('ru:sverdlovsk','65К-001','regional'),
                                  ('','P351','national'),('e-road','E22','e')]:
            self.assertEqual(dirsigns.plate_for(style,network,ref)[1],plate)
        self.assertIsNone(dirsigns.plate_for(style,'us:i','I-65'))
        self.assertEqual(rusigns.route_ref('P-242'),'Р-242')
        self.assertEqual(rusigns.route_ref('M12'),'М12')

    def test_inferred_distances_are_not_presented_as_road_kilometres(self):
        pl=dirsigns.Places({'places':[{'cc':'RU','name':'Екатеринбург','en':'Yekaterinburg','class':'city','lat':56.84,'lon':60.6}]})
        row=[0,0,-1,-1,-1,0,12000,-1,0,5,0]
        value=dirsigns._row_content(dirsigns.styles()['countries']['RU'],row,dirsigns.RouteTable(),pl,1.25,[[20,1],[100000,5]],True)
        self.assertEqual(value[2],[('Екатеринбург','','')])

    def test_exit_keeps_posted_names_and_turn_side_without_nearest_city_guess(self):
        sign={'label':{'ref':'12','names':['Первоуральск','Ревда'],'routes':['P242']},'side':-1,'kind':'advance'}
        turn,marks,names=rusigns.content(sign)
        self.assertEqual(turn,-1)
        self.assertEqual(names,[('Первоуральск','',''),('Ревда','','')])
        self.assertIn(('exit','СЪЕЗД 12'),marks)
        self.assertIn(('national','Р242'),marks)
        self.assertIsNone(rusigns.content(dict(sign,label={'ref':'12','names':[],'routes':[]})))

    def test_cyrillic_face_and_exit_mesh_are_generated_by_real_kernels(self):
        sign={'id':1,'kind':'decision','label':{'names':['Первоуральск','Ревда'],'routes':['Р242']},
              'side':1,'centre':[10.,20.,100.],'bottom':103.,'travel':[0.,1.],'width':6.,'distance':''}
        with tempfile.TemporaryDirectory() as folder:
            mesh,faces=rusigns.render([sign],(0.,0.,512.,512.),folder,folder)
            self.assertGreater(len(mesh[1]),0)
            self.assertTrue(np.isfinite(mesh[0]).all())
            self.assertEqual(len(faces),1)
            for path in faces.values():self.assertEqual(Path(path).read_bytes()[:4],b'DDS ')
            other,other_faces=rusigns.render([dict(sign,id=2,label={'names':['Тюмень'],'routes':['Р351']})],(0.,0.,512.,512.),folder,folder)
            self.assertNotEqual(set(faces),set(other_faces))
            joined=rusigns.join_meshes([mesh,other])
            self.assertEqual(len(joined[1]),len(mesh[1])+len(other[1]))
            self.assertLess(joined[1].max(),len(joined[0]))
            self.assertLess(joined[4].max(),len(joined[3]))

    def test_divided_trunk_uses_blue_while_actual_motorway_uses_green(self):
        style=dirsigns.styles()['countries']['RU']
        b=[0,0,1,0,10,0,0,2]
        line=np.array([[0.,0.],[100.,0.]])
        def rows(rank):return {'r':(line,line,(5,1,rank,0,0),[],[],[])}
        self.assertEqual(dirsigns.board_kind(style,'freeway',b,rows(6)),'road')
        self.assertEqual(dirsigns.board_kind(style,'freeway',b,rows(7)),'freeway')
        self.assertEqual(dirsigns.board_kind(style,'urban',b,rows(7)),'urban')

    def test_cyrillic_letters_are_distinct_pixels_not_missing_glyph_boxes(self):
        dirsigns._set_fonts()
        style=dirsigns.styles()['countries']['RU']['board']['road']
        face=dirsigns.styles()['face']
        flat=[*style['bg'],*style['ink'],*style['trim'],face['cap_m'],face['en_share'],face['min_w_m'],face['max_w_m'],face['inset_m'],face['trim_w_m'],0.,0.,0.]
        a=dirsigns.fast._ef.dirsign_face([(0,[],[('АААА','','')])],flat,[],256.)[0]
        b=dirsigns.fast._ef.dirsign_face([(0,[],[('ББББ','','')])],flat,[],256.)[0]
        self.assertNotEqual(bytes(a),bytes(b))

    def test_mapped_highway_exits_work_with_inferred_directions_off(self):
        from unittest.mock import patch
        mesh=(np.zeros((3,3)),np.array([[0,1,2]]),np.zeros((3,2)),['metal','face'],np.array([1]))
        with patch('dirsigns._inferred_tile') as inferred, patch('rusigns.build_tile',return_value=(mesh,{'face':'face.dds'})):
            result,pictures=dirsigns.build_tile(None,None,0,0,None,None,[],False,False,'out','vfs',country='RU',directions=False)
            inferred.assert_not_called()
            self.assertIs(result,mesh)
            self.assertEqual(pictures,{'face':'face.dds'})
