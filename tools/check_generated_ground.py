"""Offline generated-ground smoke check, also run inside the packaged Windows EXE.

Enable BNE_GEN_GROUND=on before starting the process. Real map semantics and
missing-layer retries are covered by test_genground*, not this packaging check.
"""
import sys
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))


def main():
    from types import SimpleNamespace
    import numpy as np
    import buildings
    import fast
    import genground
    import geodesy
    assert genground.ON, 'Start this check with BNE_GEN_GROUND=on'
    fast.require(fast.MIN_VERSION, 'packaged generated ground')
    frame = geodesy.EnuFrame(56.83, 60.6)
    surface = SimpleNamespace(classes=lambda lat, lon: (np.full(lat.shape, 30, np.uint8), True))
    rgb = np.full((64, 64, 3), (90, 125, 65), np.uint8)
    a, complete = genground.generate(rgb, frame, 0., 0., 64., 64, None, surface)
    b, _ = genground.generate(rgb, frame, 0., 0., 64., 64, None, surface)
    assert complete and a.shape == rgb.shape and a.dtype == np.uint8
    np.testing.assert_array_equal(a, b)
    assert np.unique(a.reshape(-1, 3), axis=0).shape[0] > 1
    assert buildings._photo_sources(frame, 0., 0., 64., 64.) == ()
    assert buildings.roof_photo_final(frame, 0., 0., 64., 64., '/unused-smoke-cache') == (None, True, None)
    print('Packaged generated ground: native ABI, deterministic texture, roof photo bypass passed')


if __name__ == '__main__':
    main()
