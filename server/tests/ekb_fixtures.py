"""Captured road features expressed in the usual offline test frame, independent of the network."""
import numpy as np
from test_roads import features, rules


def roads_of(rows):
    f = features([r['xy'] for r in rows], [r['attrs']['class'] for r in rows], ids=[r['id'] for r in rows])
    names = sorted({name for r in rows for name in r['rules']})
    for name in names:
        entries = [(i, value, a, b) for i, r in enumerate(rows) for value, a, b in r['rules'].get(name, ())]
        numeric = name in ('width', 'level', 'oneway', 'speed', 'lanes')
        f.rules[name] = rules(entries, 'float' if numeric else 'text')
    for name in sorted({k for r in rows for k in r['attrs']} - {'cx', 'cy', 'class'}):
        numeric = name in ('lane_count', 'osm_lanes', 'osm_layer', 'osm_maxspeed', 'osm_width')
        values = [r['attrs'].get(name) for r in rows]
        f.attrs[name] = np.array([np.nan if v is None else float(v) for v in values], np.float64) if numeric else np.array(values, object)
    return f
