"""Russian pack integration: model geometry, wire attachments and streamed sign assets."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'server'))
import furniture
import ruinfra
import roads
import markings
import roadsigns
import townentry as townsigns


class RussianInfrastructure(unittest.TestCase):
    def test_country_gate_and_explicit_disable(self):
        self.assertTrue(ruinfra.enabled('RU'))
        self.assertFalse(ruinfra.enabled('UA'))
        self.assertFalse(ruinfra.enabled(None))
        with patch.object(ruinfra, 'ON', False):
            self.assertFalse(ruinfra.enabled('RU'))

    def test_wire_endpoints_follow_rotated_model_insulators(self):
        poles = [(0., 0., 100., 90.), (0., 40., 105., 90.)]
        wires = furniture.wire_lines(poles, ruinfra.WIRE_ANCHORS)
        self.assertEqual(len(wires), 3)
        for wire, (x, y, z) in zip(wires, ruinfra.WIRE_ANCHORS):
            np.testing.assert_allclose(wire[0], [-y, x, 100 + z], atol=1e-9)
            np.testing.assert_allclose(wire[-1], [-y, 40 + x, 105 + z], atol=1e-9)
            self.assertLess(wire[len(wire)//2, 2], (wire[0,2] + wire[-1,2]) / 2)

    def test_pole_lamp_uses_ground_origin_and_faces_carriageway(self):
        rows = ruinfra.localize([['polelamp', 10, 20, 100 + furniture.POLE_LAMP_Z, 30, 1, 1.1, 0]])
        self.assertEqual(rows[0][0], ruinfra.BRACKET)
        self.assertAlmostEqual(rows[0][3], 100)
        self.assertEqual(rows[0][4], 210)
        self.assertEqual(rows[0][6], 9)

    def test_lenses_use_the_new_luminaire_not_stock_offset(self):
        row = [ruinfra.citylamps.G_STEEL, 0., 0., 10., 0., 1., 9., 0.]
        lenses = furniture.lamp_lenses([row])
        lens = next(r for r in lenses if r[0] == furniture.G_LENS)
        np.testing.assert_allclose(lens[1:4], [2.1, 0., 18.77 - furniture.LENS_DROP_M], atol=1e-6)

    def test_scaled_highway_lamp_glow_follows_the_model_head(self):
        for group in ruinfra.citylamps.GROUPS:
            for height in (11., 13.5):
                with self.subTest(group=group, height=height):
                    row = [group, 20., 30., 100., 90., 1., height, 0.]
                    lens = next(r for r in furniture.lamp_lenses([row]) if r[0] == furniture.G_LENS)
                    scale = height / ruinfra.citylamps.HEIGHT
                    np.testing.assert_allclose(lens[1:4],
                        [20., 30. + 2.1 * scale, 100. + 8.77 * scale - furniture.LENS_DROP_M], atol=.006)

    def test_actual_furniture_pipeline_has_local_models_and_clear_roads(self):
        spec = roads.Spec(8., 'paved', False, 'secondary', False)
        line = np.array([[-200., 50., 0.], [600., 50., 0.]])
        wires = []
        rows = furniture.place([('r', spec, line, 60.)], [], (0.,0.,256.,256.), country='RU', wires=wires)
        self.assertTrue(any(r[0] == ruinfra.POLE for r in rows))
        self.assertTrue(any(r[0] == ruinfra.MARKER for r in rows))
        self.assertFalse(any(r[0] == 'pole' for r in rows))
        self.assertTrue(wires)
        for r in rows:
            if r[0] in (ruinfra.POLE, ruinfra.MARKER):
                self.assertGreater(abs(r[2] - 50.), spec.width / 2)
        again = furniture.place([('r', spec, line, 60.)], [], (0.,0.,256.,256.), country='RU')
        self.assertEqual(rows, again)

    def test_marker_rejected_inside_another_road(self):
        spec = roads.Spec(8., 'paved', False, 'secondary', False)
        line = np.array([[-200.,50.,0.],[600.,50.,0.]])
        crossing = np.array([[100.,-200.,0.],[100.,300.,0.]])
        clear = furniture.RoadClearance([(4.,line),(4.,crossing)])
        rows = ruinfra.markers([('r',spec,line,60.)], (0.,0.,256.,256.), clear)
        self.assertTrue(rows)
        self.assertTrue(all(abs(r[1]-100.) > 4. for r in rows))

    def test_russian_marking_patterns_and_other_country_unchanged(self):
        ru = markings.style('RU')
        self.assertEqual(ru.centre_rural, (3.,9.))
        self.assertEqual(ru.centre_urban, (2.,6.))
        self.assertEqual(ru.lane_motorway, (4.,12.))
        self.assertEqual(ru.centre, 'line_white')
        self.assertEqual(markings.style('US').centre, 'line_yellow')

    def test_russian_town_face_writes_bundled_cyrillic_and_exit_slash(self):
        with tempfile.TemporaryDirectory() as folder:
            entry = townsigns.write_face(folder, folder, 'ПЕРВОУРАЛЬСК', townsigns.G_ENTRY, country='RU')
            exit = townsigns.write_face(folder, folder, 'ПЕРВОУРАЛЬСК', townsigns.G_EXIT, country='RU')
            self.assertNotEqual(entry, exit)
            self.assertTrue(Path(entry['texture']).is_file())
            self.assertTrue(Path(entry['shape']).is_file())
            self.assertNotEqual(Path(entry['texture']).read_bytes(),Path(exit['texture']).read_bytes())
        with patch.object(townsigns, 'ENV', ''):
            self.assertTrue(townsigns.enabled(True))
            self.assertFalse(townsigns.enabled(False))

    def test_ru_motorway_atlas_has_green_field_and_living_zone_blue(self):
        from PIL import Image
        table = roadsigns.tables()[0]
        ids = [r['id'] for r in table['roles']]
        path = ROOT / 'mod/beamng_earth/levels/beamng_earth/art/shapes/beamngEarth/bne_signs_vienna_ru.color.dds'
        with Image.open(path) as img:
            def cell(name):
                k=ids.index(name); x=k % table['cols']*256; y=k // table['cols']*256
                return np.array(img.convert('RGB').crop((x,y,x+256,y+256))).astype(int)
            rgb = cell('info.motorway')
            self.assertGreater(((rgb[:,:,1]>rgb[:,:,0]+40)&(rgb[:,:,1]>rgb[:,:,2]+20)).sum(),20000)
            rgb = cell('info.living_street')
            self.assertGreater(((rgb[:,:,2]>rgb[:,:,0]+40)&(rgb[:,:,2]>rgb[:,:,1]+20)).sum(),20000)

    def test_marker_ground_uses_production_drawn_ground_vector_contract(self):
        import geodesy
        import roadmesh
        from unittest.mock import Mock
        frame = geodesy.EnuFrame(56.8, 60.4, 0.)
        spec = roads.Spec(8., 'paved', False, 'secondary', False)
        line = np.array([[-200., 50., 0.], [600., 50., 0.]])
        clear = furniture.RoadClearance([(4., line)])
        # Exactly the callback supplied by blockworker._tile_parts. Even a
        # single query returns a one-dimensional array, never a float.
        ground = Mock(side_effect=lambda x, y: roadmesh.drawn_ground(
            frame, lambda lat, lon: np.zeros_like(lat), np.c_[x, y]))
        rows = ruinfra.markers([('r', spec, line, 60.)], (0., 0., 256., 256.), clear, ground)
        self.assertTrue(rows)
        self.assertTrue(np.isfinite([r[3] for r in rows]).all())
        self.assertEqual(ground.call_count, 1)

    def test_optional_marker_failure_does_not_abort_furniture_or_wires(self):
        spec = roads.Spec(8., 'paved', False, 'secondary', False)
        line = np.array([[-200., 50., 0.], [600., 50., 0.]])
        def unavailable(x, y):
            raise ValueError('terrain unavailable')
        wires = []
        with patch.object(ruinfra, '_warned_markers', -float('inf')):
            with self.assertLogs('earthd.ruinfra', level='WARNING') as messages:
                rows = furniture.place([('r', spec, line, 60.)], [], (0., 0., 256., 256.),
                                       country='RU', wires=wires, ground=unavailable)
        self.assertTrue(any(r[0] == ruinfra.POLE for r in rows))
        self.assertTrue(wires)
        self.assertFalse(any(r[0] == ruinfra.MARKER for r in rows))
        self.assertIn('terrain unavailable', messages.output[0])

    def test_road_tile_pipeline_writes_ru_objects_with_real_terrain_callback(self):
        import roadmesh
        from test_roads import FRAME, features
        # Real production geometry/terrain code, synthetic roads and heights:
        # no network and no prewarmed developer cache needed in CI.
        feats = features([[(-300., 100.), (600., 100.)]], ['secondary'],
                         surfaces=[(0, 'asphalt')])
        for slope in (0., .01):
            with self.subTest(slope=slope), tempfile.TemporaryDirectory() as folder:
                def elev(lat, lon):
                    return 10. + slope * FRAME.geodetic_to_enu(lat, lon, 0.)[0]
                def ground(x, y):
                    return roadmesh.drawn_ground(FRAME, elev, np.c_[x, y])
                props, wires, walks = [], [], []
                with self.assertNoLogs('earthd.ruinfra', level='WARNING'):
                    chunks = roads.build_tile(FRAME, 0, 0, [feats], elev, walks=walks,
                                              props=props, wires=wires, country='RU',
                                              ground=ground)
                self.assertTrue(chunks, 'a successful tile must contain drivable road geometry')
                markers = [r for r in props if r[0] == ruinfra.MARKER]
                self.assertTrue(markers, 'a swallowed decorative error must fail this test')
                self.assertTrue(any(r[0] == ruinfra.POLE for r in props))
                xy = np.array([r[1:3] for r in markers])
                np.testing.assert_allclose([r[3] for r in markers], ground(xy[:,0], xy[:,1]))
                mesh = roadmesh.build(FRAME, chunks, elev, (0.,0.,0.), .05,
                                      clip=roads.tile_bbox(0,0), follow=True)
                result = roads.write_tile(folder, '/temp/test', 1, 0, 0, chunks,
                                          walks=walks, road_mesh=mesh, props=props, wires=wires)
                self.assertGreater(result[1], 0)
                data = json.loads((Path(folder)/'roads_1_0_0.json').read_text())
                self.assertIn(ruinfra.MARKER, data['props']['groups'])
                self.assertIn(ruinfra.POLE, data['props']['groups'])
                self.assertTrue(list(Path(folder).glob('*.cdae')))

    def test_registered_scenery_models_and_materials_exist(self):
        import xml.etree.ElementTree as ET
        base=ROOT/'mod/beamng_earth/levels/beamng_earth/art/shapes/beamngEarth'
        for rel in ['city_lamps/bne_lamp_eu_steel.dae','city_lamps/bne_lamp_eu_concrete.dae',
                    'city_lamps/bne_lamp_ru_bracket.dae','europe_infrastructure/bne_eu_pole_concrete_three.dae',
                    'europe_infrastructure/bne_eu_marker_red_black.dae','sign_town_body_ru.dae']:
            ET.parse(base/rel)
        for group in (ruinfra.POLE,ruinfra.MARKER,ruinfra.BRACKET,*ruinfra.citylamps.GROUPS):
            self.assertIn(group,(ROOT/'mod/beamng_earth/lua/ge/extensions/beamngEarth/trees.lua').read_text())
