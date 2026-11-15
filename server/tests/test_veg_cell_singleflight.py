"""Cold vegetation cells shared between spawn processes; failures/cancellation never strand a cache claim."""
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pools
import vegetation as veg
import xproc


def items():
    return veg.Items(*(np.array([n], dtype=np.float64) for n in range(9)))


def read_cell(cache, go, release, events, result):
    """A real spawn process with synthetic generation: no raster downloads or hardware speed assumptions."""
    v = veg.Vegetation(None, cache)
    once = xproc.once

    def traced(*args, **kwargs):
        kwargs['on_wait'] = lambda: events.put(('wait', os.getpid()))
        return once(*args, **kwargs)

    def build(x, y):
        events.put(('build', os.getpid()))
        if not release.wait(15):
            raise TimeoutError('test producer was not released')
        return items()

    v._build = build
    events.put(('ready', os.getpid()))
    if not go.wait(15):
        raise TimeoutError('test readers were not started')
    with patch.object(xproc, 'once', side_effect=traced):
        got = v.cell((14, 10946, 5019))
    result.put([getattr(got, f).tolist() for f in got.__dataclass_fields__])


def leave_claim(cache):
    """A producer that exits before publishing: its cache claim survives the process."""
    v = veg.Vegetation(None, cache)
    if not xproc.take(v._path(1, 2) + '.lock'):
        raise RuntimeError('test claim was not acquired')


class CellSharingTest(unittest.TestCase):
    def test_three_processes_build_once_then_read_identical_items(self):
        ctx = multiprocessing.get_context('spawn')
        with tempfile.TemporaryDirectory() as cache:
            events, result = ctx.Queue(), ctx.Queue()
            go, release = ctx.Event(), ctx.Event()
            procs = [ctx.Process(target=read_cell, args=(cache, go, release, events, result)) for _ in range(3)]
            try:
                for p in procs:
                    p.start()
                self.assertEqual([events.get(timeout=20)[0] for _ in procs], ['ready'] * 3)
                go.set()
                phases = [events.get(timeout=20)[0] for _ in procs]
                self.assertCountEqual(phases, ['build', 'wait', 'wait'])
                release.set()
                results = [result.get(timeout=20) for _ in procs]
                self.assertTrue(all(r == results[0] for r in results))
                for p in procs:
                    p.join(20)
                    self.assertEqual(p.exitcode, 0)
                v = veg.Vegetation(None, cache)
                with patch.object(v, '_build', side_effect=AssertionError('warm read must not rebuild')):
                    self.assertEqual(len(v.cell((14, 10946, 5019))), 1)
                self.assertFalse(Path(v._path(10946, 5019) + '.lock').exists())
            finally:
                go.set()
                release.set()
                for p in procs:
                    if p.pid is not None:
                        p.join(5)
                        if p.is_alive():
                            p.terminate()
                            p.join(5)
                events.close()
                result.close()

    def test_failed_producer_releases_claim_and_next_reader_recovers(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            with patch.object(v, '_build', side_effect=OSError('canopy unavailable')):
                with self.assertRaisesRegex(OSError, 'canopy unavailable'):
                    v.cell((14, 1, 2))
            self.assertFalse(Path(v._path(1, 2) + '.lock').exists())
            with patch.object(v, '_build', return_value=items()):
                self.assertEqual(len(v.cell((14, 1, 2))), 1)

    def test_cancelled_producer_releases_claim_without_caching(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            with patch.object(v, '_build', side_effect=pools.Abandoned('moved away')):
                with self.assertRaises(pools.Abandoned):
                    v.cell((14, 1, 2))
            self.assertFalse(Path(v._path(1, 2)).exists())
            self.assertFalse(Path(v._path(1, 2) + '.lock').exists())

    def test_exited_producers_claim_is_recovered(self):
        with tempfile.TemporaryDirectory() as cache:
            p = multiprocessing.get_context('spawn').Process(target=leave_claim, args=(cache,))
            p.start()
            p.join(20)
            try:
                self.assertEqual(p.exitcode, 0)
                v = veg.Vegetation(None, cache)
                self.assertTrue(Path(v._path(1, 2) + '.lock').exists())
                with patch.object(veg, 'CELL_WAIT_S', 0.2), patch.object(veg, 'CELL_LIVE_S', 0.2), \
                        patch.object(v, '_build', return_value=items()):
                    self.assertEqual(len(v.cell((14, 1, 2))), 1)
                self.assertFalse(Path(v._path(1, 2) + '.lock').exists())
            finally:
                if p.is_alive():
                    p.terminate()
                    p.join(5)

    def test_failed_cache_publication_releases_claim(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            with patch.object(v, '_build', return_value=items()), \
                    patch.object(veg.staging, 'replace_cached', side_effect=PermissionError('file busy')):
                with self.assertRaises(PermissionError):
                    v.cell((14, 1, 2))
            self.assertFalse(Path(v._path(1, 2) + '.lock').exists())

    def test_dem_incomplete_does_not_publish_a_cell_to_other_readers(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            def build(x, y):
                v._tl.dem_failed = True
                return items()
            with patch.object(v, '_build', side_effect=build):
                self.assertEqual(len(v._load(1, 2)), 1)
            self.assertFalse(Path(v._path(1, 2)).exists())
            self.assertFalse(Path(v._path(1, 2) + '.lock').exists())

    def test_corrupt_cache_is_rebuilt_and_shared(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            path = Path(v._path(1, 2))
            path.parent.mkdir(parents=True)
            path.write_bytes(b'cut-off archive')
            with patch.object(v, '_build', return_value=items()) as build:
                first = v._load(1, 2)
                second = v._load(1, 2)
            self.assertEqual(build.call_count, 1)
            np.testing.assert_array_equal(first.lon, second.lon)

    def test_bounded_wait_fallback_does_not_release_another_producers_claim(self):
        with tempfile.TemporaryDirectory() as cache:
            v = veg.Vegetation(None, cache)
            with patch.object(xproc, 'once', return_value=(None, False)), \
                    patch.object(xproc, 'release') as release, patch.object(v, '_build', return_value=items()):
                self.assertEqual(len(v._load(1, 2)), 1)
            release.assert_not_called()


if __name__ == '__main__':
    unittest.main()
