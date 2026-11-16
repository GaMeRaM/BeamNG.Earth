"""Russian localization: mapped speed ranges, local names, station text and regional rail defaults."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import busstationsign as bs
import dirsigns
import geocode
import navgraph
import placenames as pn
import railways
import railxing
import roads
import rusigns
import speedsigns
from test_roads import FRAME, features, rules
from test_placenames import town, area, table, LAT, LON
from test_speed_signs import row, place


class RussianLocalization(unittest.TestCase):
    def test_ai_target_is_not_a_mapped_russian_speed(self):
        f = features([[(0, 0), (1000, 0)]], ['motorway'])
        spec = roads.road_specs(f)[0]
        self.assertGreater(navgraph.road_mph(f, 0, spec, False, country='RU'), 0)
        self.assertEqual(speedsigns._limits(f, 0, spec, False, 1, 'RU'), [(0., 0.)])
        self.assertEqual(speedsigns._limits(f, 0, spec, False, 1, 'FR'), [(0., 120.)])
        self.assertEqual(len(place([row([(0, 0), (20000, 0)], 0)])), 0)

    def test_partial_mapped_limit_does_not_fill_gaps_with_ai_speed(self):
        f = features([[(0, 0), (1000, 0)]], ['primary'])
        spec = roads.road_specs(f)[0]
        # Deliberately leave the first/last quarters unmapped.
        f.rules['max_speed_kmh'] = types.SimpleNamespace(
            start=np.array([.25]), end=np.array([.75]), value=np.array([60.]), rows=lambda i: [0])
        limits = speedsigns._limits(f, 0, spec, False, 1, 'RU')
        self.assertEqual(limits, [(0., 0.), (.25, 60.), (.75, 0.)])
        signs = place([row([(0, 0), (1000, 0)], 0, lims=limits)])
        self.assertTrue(len(signs))
        self.assertTrue(np.all(signs[:, 4] == 60))

    def test_invalid_mapped_limit_does_not_create_a_restriction(self):
        for value in [np.nan, np.inf, 0., -20.]:
            f = features([[(0, 0), (1000, 0)]], ['motorway'])
            f.rules['max_speed_kmh'] = rules([(0, value)], 'float')
            self.assertEqual(speedsigns._limits(f, 0, roads.road_specs(f)[0], False, 1, 'RU'), [(0., 0.)])

    def test_russian_primary_names_survive_english_translations(self):
        towns = [town('Екатеринбург', .1, country='RU', region='RU-SVE', en='Yekaterinburg')]
        areas = [area('Свердловская область', 'region', 'RU', 'RU-SVE', en='Sverdlovsk Oblast'),
                 area('Россия', 'country', 'RU', en='Russia')]
        self.assertEqual(pn.pick(table(towns), table(areas), LAT, LON),
                         dict(place='Екатеринбург', region='Свердловская область', country='Россия'))
        self.assertEqual(pn.local_lang('DE'), 'de')
        self.assertEqual(geocode.lang_for('RU'), 'en', 'Photon request languages must remain supported')

    def test_russian_names_are_read_even_if_primary_is_english(self):
        towns = [town('Yekaterinburg', .1, country='RU', region='RU-SVE', ru='Екатеринбург')]
        areas = [area('Sverdlovsk Oblast', 'region', 'RU', 'RU-SVE', ru='Свердловская область'),
                 area('Russia', 'country', 'RU', ru='Россия')]
        self.assertEqual(pn.pick(table(towns), table(areas), LAT, LON),
                         dict(place='Екатеринбург', region='Свердловская область', country='Россия'))

    def test_speed_cache_separates_country_policies(self):
        f = features([[(0, 0), (1000, 0)]], ['motorway'])
        fr = speedsigns._cell_rows(f, FRAME, None, None, False, False, country='FR')
        ru = speedsigns._cell_rows(f, FRAME, None, None, False, False, country='RU')
        self.assertEqual(next(iter(fr.values()))[4], [(0., 120.)])
        self.assertEqual(next(iter(ru.values()))[4], [(0., 0.)])

    def test_station_face_is_localized_and_cache_identity_contains_subtitle(self):
        dirsigns._set_fonts()
        native = bs.fast._ef.dirsign_town_face
        with tempfile.TemporaryDirectory() as out, patch.object(bs.fast._ef, 'dirsign_town_face', wraps=native) as face:
            ru = bs._face(out, '/vfs', 'Северный', 'RU')
            self.assertEqual(face.call_args.args[1], 'Автовокзал')
            en = bs._face(out, '/vfs', 'Северный', 'US')
            self.assertNotEqual(ru[0], en[0])
            self.assertTrue(all(p.read_bytes()[:4] == b'DDS ' for p in Path(out).glob('*.dds')))
        st = types.SimpleNamespace(fid='station')
        with patch('busbays.layout_bays', return_value=[]):
            self.assertEqual(bs.board_rows(st, 'RU')[0], ('Отправление', ''))
            self.assertEqual(bs.board_rows(st, 'US')[0], ('Departures', ''))

    def test_mapped_exit_does_not_take_colour_from_crossing_motorway(self):
        sp = types.SimpleNamespace(width=12., dir=1, oneway=True, urban=False, link=False, cls='motorway')
        sign = dict(travel=[1., 0.], road_point=[10., 0.])
        self.assertEqual(rusigns.board_kind(sign, [('m', sp, np.array([[10., -100.], [10., 100.]]), 0)]), 'road')
        road = np.array([[0., 0.], [100., 0.]])
        self.assertEqual(rusigns.board_kind(sign, [('m', sp, road, 0)]), 'freeway')
        sp.dir = -1
        self.assertEqual(rusigns.board_kind(sign, [('m', sp, road, 0)]), 'road')
        sp.dir, sp.link = 1, True
        self.assertEqual(rusigns.board_kind(sign, [('m', sp, road, 0)]), 'road')

    def test_russian_automatic_crossing_grading_matches_explicit_enable(self):
        from test_roads import flat as dem
        f = features([[(0., 100.), (250., 100.)], [(120., 0.), (120., 250.)]],
                     ['standard_gauge', 'secondary'], subtypes=['rail', 'road'])
        with patch.object(railxing, '_ENV', ''), patch.object(railxing, 'country_at', return_value='RU'):
            with patch.object(railxing, 'ENABLED', False):
                automatic = railways.grade_plans(FRAME, [f], roads.tile_bbox(0, 0), dem)
            with patch.object(railxing, 'ENABLED', True):
                explicit = railways.grade_plans(FRAME, [f], roads.tile_bbox(0, 0), dem)
            np.testing.assert_allclose(automatic[0][2], explicit[0][2])
            at = np.argmin(np.abs(automatic[0][1][:, 0] - 120.))
            self.assertLess(float(automatic[0][2][at]), 9.7)

    def test_mapped_rail_gauge_overrides_russian_fallback_in_the_mesh(self):
        def mesh_width(mapped):
            f = features([[(0., 100.), (250., 100.)]], ['standard_gauge'], subtypes=['rail'])
            if mapped:
                f.attrs['osm_gauge'] = np.array(['1435'])
            with patch.object(railxing, 'country_at', return_value='RU'):
                mesh = railways.tile_mesh(FRAME, 0, 0, [f], lambda xy: np.full(len(xy), 10.))
            p, t, _uv, _mat, mi = mesh
            steel = p[np.unique(t[mi == 2])]
            return np.ptp(steel[:, 1])
        self.assertAlmostEqual(mesh_width(False) - mesh_width(True), .085, delta=.002)

    def test_russian_rail_policy_obeys_explicit_switch(self):
        with patch.object(railxing, '_ENV', ''), patch.object(railxing, 'ENABLED', False):
            self.assertTrue(railxing.enabled('RU'))
            self.assertFalse(railxing.enabled('US'))
            with patch.object(railxing, 'country_at', return_value='RU'):
                self.assertTrue(railxing.enabled(frame=FRAME))
            with patch.object(railxing, 'country_at', return_value=None):
                self.assertFalse(railxing.enabled('RU', FRAME), 'unknown border profile keeps all geometry paths in the old mode')
            with patch.object(railxing, '_ENV', 'off'):
                self.assertFalse(railxing.enabled('RU'))
        self.assertEqual(railways.gauge('standard_gauge', country='RU'), 1.520)
        self.assertEqual(railways.gauge('standard_gauge', 'fi', 'RU'), 1.524)
        self.assertEqual(railways.gauge('standard_gauge', country='US'), 1.435)
        self.assertEqual(railways.gauge('narrow_gauge', country='RU'), 1.)


if __name__ == '__main__':
    unittest.main()
