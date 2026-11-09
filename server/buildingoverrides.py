"""Verified OSM parts missing from an Overture release, added only to their exact parent."""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=1)
def _parts():
    return json.loads((Path(__file__).parent / 'data/building_part_overrides.json').read_text(encoding='utf-8'))['parts']


def missing(frame, building_id, present_sources):
    """Use source geometry/heights, never fill arbitrary gaps or change mapped elevated parts."""
    present = {str(s).split('@')[0] for s in present_sources}
    out = []
    for part in _parts():
        if part['building_id'] != building_id or part['source'] in present:
            continue
        ring = np.asarray(part['ring'], np.float64)
        e, n, _ = frame.geodetic_to_enu(ring[:, 1], ring[:, 0], np.zeros(len(ring)))
        out.append((np.c_[e, n], (part['height'] - part['min_height'], part['min_height']),
                    {'roof_shape': 'flat', 'source': part['source']}))
    return out
