"""Check the shipped lamp shells, not just the builder's normals."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_city_lamps as lamps

NS = {'c': 'http://www.collada.org/2005/11/COLLADASchema'}
KINDS = ('steel', 'concrete', 'pole_concrete_three', 'pole_concrete_round')


def triangles(kind):
    utility = kind.startswith('pole_')
    name = ('bne_eu_' if utility else 'bne_lamp_eu_') + kind
    folder = lamps.OUT.parent / 'europe_infrastructure' if utility else lamps.OUT
    path = folder / (name + '.dae')
    tree = ET.parse(path)
    geom = tree.find(".//c:geometry[@id='" + name + "-col-g']", NS)
    xyz = np.fromstring(geom.find('.//c:float_array', NS).text, sep=' ').reshape(-1, 3)
    indices = np.concatenate([np.fromstring(p.text, sep=' ', dtype=int)
                              for p in geom.findall('.//c:triangles/c:p', NS)])
    return xyz[indices.reshape(-1, 3)]


class LampCollisionTest(unittest.TestCase):
    def test_closed_shell_with_consistent_outward_winding(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                ts = triangles(kind)
                edges = {}
                for tri in ts:
                    for a, b in zip(tri, np.roll(tri, -1, axis=0)):
                        a, b = tuple(a), tuple(b)
                        key = tuple(sorted((a, b)))
                        edges[key] = edges.get(key, 0) + (1 if a < b else -1)
                self.assertTrue(all(v == 0 for v in edges.values()))
                volume = np.einsum('ij,ij->i', ts[:, 0],
                                   np.cross(ts[:, 1], ts[:, 2])).sum() / 6
                self.assertGreater(volume, 0)

    def test_first_hit_from_outside_is_an_outward_face(self):
        for kind in KINDS:
            ts = triangles(kind)
            normals = np.cross(ts[:, 1] - ts[:, 0], ts[:, 2] - ts[:, 0])
            for z in (.25, 1., 3., 7.):
                for angle in np.linspace(0, 2 * np.pi, 24, endpoint=False):
                    origin = np.array([np.cos(angle), np.sin(angle), z])
                    direction = np.array([-np.cos(angle), -np.sin(angle), 0.])
                    hits = []
                    for tri, normal in zip(ts, normals):
                        den = normal @ direction
                        if abs(den) < 1e-10:
                            continue
                        t = normal @ (tri[0] - origin) / den
                        point = origin + t * direction
                        sides = [np.cross(b - a, point - a) @ normal
                                 for a, b in zip(tri, np.roll(tri, -1, axis=0))]
                        if t >= 0 and min(sides) >= -1e-10:
                            hits.append((t, den))
                    self.assertTrue(hits, (kind, z, angle))
                    distance, facing = min(hits)
                    self.assertLess(facing, 0, (kind, z, angle))
                    if kind == 'steel':
                        radius = .19 if z < .55 else .135 + (.062 - .135) * z / 8.3
                        # The render model's polygon is inscribed in this circle.
                        self.assertGreaterEqual(1 - distance, radius * np.cos(np.pi / 12))
                    elif kind.startswith('pole_'):
                        # Both RU round concrete masts are 8.5 m, with ten
                        # sides at the nearest visual LOD. Check every angle,
                        # including the old collider's narrow pentagon flats.
                        radius = .185 - .08 * z / 8.5
                        self.assertGreaterEqual(1 - distance, radius * np.cos(np.pi / 10))


if __name__ == '__main__':
    unittest.main()
