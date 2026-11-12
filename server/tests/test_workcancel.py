"""Owned tile cancellation frees real workers without killing shared producers."""
import asyncio
import collections
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, CancelledError
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncsubmit
import pools
import workcancel


def until_cancelled(path):
    started = Path(path)
    tmp = started.with_suffix('.tmp')
    tmp.write_text(str(os.getpid()))
    tmp.replace(started)
    end = time.monotonic() + 10
    while time.monotonic() < end:
        workcancel.checkpoint()
        time.sleep(.01)
    return False


class ProcessCancellationTest(unittest.TestCase):
    def setUp(self):
        self.pool = pools.RespawningPool('cancel test', 1, cancellable=True,
                                         mp_context=multiprocessing.get_context('spawn'))

    def tearDown(self):
        self.pool.shutdown(wait=True, cancel_futures=True)

    def test_running_worker_stops_cooperatively_and_is_reused(self):
        request = workcancel.Request()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'started'
            with workcancel.scope(request):
                future = self.pool.submit_cancellable(until_cancelled, str(path))
            end = time.monotonic() + 10
            while not path.exists() and time.monotonic() < end:
                time.sleep(.01)
            self.assertTrue(path.exists())
            pid = int(path.read_text())
            request.cancel()
            with self.assertRaises(workcancel.WorkCancelled):
                future.result(timeout=5)
            self.assertEqual(self.pool.submit(os.getpid).result(timeout=5), pid)
            self.assertEqual(self.pool.respawns, 0)
            self.assertEqual(len(self.pool._cancel_free), 1024)

    def test_late_cancel_cannot_cancel_a_reused_slot(self):
        self.pool._cancel_free = collections.deque([0])
        old, current = workcancel.Request(), workcancel.Request()
        with workcancel.scope(old):
            previous = self.pool.submit_cancellable(os.getpid)
        previous.result(timeout=10)
        with workcancel.scope(current):
            future = self.pool.submit_cancellable(time.sleep, .05)
        old.cancel()
        self.assertIsNone(future.result(timeout=5))

    def test_plain_submit_keeps_shared_producer_running(self):
        request = workcancel.Request()
        with workcancel.scope(request):
            future = self.pool.submit(time.sleep, .05)
        request.cancel()
        self.assertIsNone(future.result(timeout=10))

    def test_obsolete_call_queue_item_never_enters_its_build(self):
        self.pool.submit(os.getpid).result(timeout=10)
        blocker = self.pool.submit(time.sleep, .5)
        request = workcancel.Request()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'must-not-start'
            with workcancel.scope(request):
                future = self.pool.submit_cancellable(until_cancelled, str(path))
            end = time.monotonic() + 3
            while not future.running() and time.monotonic() < end:
                time.sleep(.001)
            self.assertTrue(future.running(), 'exercise a job already handed to the process call queue')
            request.cancel()
            blocker.result(timeout=5)
            with self.assertRaises(workcancel.WorkCancelled):
                future.result(timeout=5)
            self.assertFalse(path.exists())


class RotatingCancellationTest(ProcessCancellationTest):
    """Owned cancellation remains valid across upstream's generation queue."""
    def setUp(self):
        self.pool = pools.RespawningPool('rotating cancel test', 1, cancellable=True,
                                         tasks_per_child=3,
                                         mp_context=multiprocessing.get_context('spawn'))

    def test_obsolete_call_queue_item_never_enters_its_build(self):
        self.pool.submit(os.getpid).result(timeout=10)
        blocker = self.pool.submit(time.sleep, .3)
        request = workcancel.Request()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'must-not-start'
            with workcancel.scope(request):
                future = self.pool.submit_cancellable(until_cancelled, str(path))
            request.cancel()
            blocker.result(timeout=5)
            with self.assertRaises(CancelledError):
                future.result(timeout=5)
            self.assertFalse(path.exists())
            self.assertEqual(len(self.pool._cancel_free), 1024)

    def test_cancelled_slot_does_not_leak_across_generations(self):
        for _ in range(8):
            request = workcancel.Request()
            with workcancel.scope(request):
                future = self.pool.submit_cancellable(os.getpid)
            self.assertGreater(future.result(timeout=10), 0)
            request.cancel()
        self.assertEqual(len(self.pool._cancel_free), 1024)
        self.assertGreaterEqual(self.pool.rotations, 2)


class SharedPlanCancellationTest(unittest.TestCase):
    def test_ready_check_cancel_releases_a_just_acquired_real_claim(self):
        import plancache
        import xproc
        request = workcancel.Request()
        take = xproc.take
        def acquired(path, kind):
            got = take(path, kind)
            if got:
                request.cancel()
            return got
        with tempfile.TemporaryDirectory() as d:
            cache = plancache.PlanCache(d, 'test')
            key = (14, 10950, 5035)
            with workcancel.scope(request), mock.patch.object(xproc, 'take', side_effect=acquired):
                with self.assertRaises(workcancel.WorkCancelled):
                    cache.claim(key)
            self.assertFalse(Path(cache._path(key) + '.lock').exists())
            got, mine = cache.claim(key)
            self.assertIsNone(got)
            self.assertTrue(mine)
            cache.release(key)

    def test_completed_region_is_cached_and_unlocked_before_stopping(self):
        import grading
        import mapcells
        from test_roads import FRAME
        planner = grading._Planner(FRAME, None, None)
        planner.shared = mock.Mock()
        planner.shared.region_claim.return_value = None, True
        home = mapcells.cell_of(FRAME.lat0, FRAME.lon0)
        request = workcancel.Request()
        complete = {'parts': [], 'prof': {}}
        def finish(*args):
            request.cancel()
            return complete
        with mock.patch.object(grading._xs, 'ON', True), \
                mock.patch.object(planner, '_cw_region_calc', side_effect=finish) as build:
            with workcancel.scope(request), self.assertRaises(workcancel.WorkCancelled):
                planner._cw_region(home)
            planner.shared.region_store.assert_called_once()
            planner.shared.region_release.assert_called_once()
            self.assertIs(planner._cw_region(home), complete)
            self.assertEqual(build.call_count, 1)

    def test_incomplete_cell_is_not_persisted_and_its_claim_is_released(self):
        import grading
        import mapcells
        from test_roads import FRAME
        planner = grading._Planner(FRAME, None, None)
        planner.shared = mock.Mock()
        planner.shared.claim.return_value = None, True
        home = mapcells.cell_of(FRAME.lat0, FRAME.lon0)
        request = workcancel.Request()
        def stop(*args):
            request.cancel()
            workcancel.checkpoint()
        with mock.patch.object(planner, '_cell_deck_patches', return_value=[]), \
                mock.patch.object(planner, '_make_cell', side_effect=stop), \
                workcancel.scope(request), self.assertRaises(workcancel.WorkCancelled):
            planner._cell_plans(home)
        planner.shared.store.assert_not_called()
        planner.shared.release.assert_called_once()
        self.assertNotIn(home, planner.cells)


class AsyncCancellationTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancelling_shared_consumer_does_not_interrupt_its_producer(self):
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        def shared_build():
            self.assertIsNone(workcancel.current())
            entered.set()
            if not release.wait(3):
                raise TimeoutError('shared build not released')
            workcancel.checkpoint()
            completed.set()             # another consumer can still use the completed shared result
            return 42
        with ThreadPoolExecutor(1) as pool:
            future = asyncsubmit.submit(asyncio.get_running_loop(), pool, shared_build)
            try:
                while not entered.is_set():
                    await asyncio.sleep(.001)
                asyncsubmit.request_cancel(future)
                self.assertFalse(future.done())
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(future, 2)
            self.assertTrue(completed.is_set())

    async def test_request_keeps_slot_until_worker_acknowledges(self):
        entered, release = threading.Event(), threading.Event()

        def build():
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test worker not released')
            workcancel.checkpoint()
            return 'obsolete output'

        with ThreadPoolExecutor(1) as pool:
            future = asyncsubmit.submit(asyncio.get_running_loop(), pool, build, owned=True)
            try:
                while not entered.is_set():
                    await asyncio.sleep(.001)
                self.assertTrue(asyncsubmit.request_cancel(future))
                await asyncio.sleep(.01)
                self.assertFalse(future.done(), 'a cancellation request is not worker completion')
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(future, 2)

    async def test_geo_tracker_protects_camera_and_other_car_then_prioritizes_new_place(self):
        import roads
        import geotiles
        entered, release, fresh = threading.Event(), threading.Event(), threading.Event()
        requests = {}

        def build(aid, gx, gy, *args):
            requests[gx] = workcancel.current()
            if gx == 0:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('old tile not released')
                workcancel.checkpoint()
            else:
                fresh.set()
            return None

        def quad(frame, gx, gy):
            return np.array([[gx * 256., 0.], [(gx + 1) * 256., 0.],
                             [(gx + 1) * 256., 256.], [gx * 256., 256.]])

        tracker = roads.GeoTracker()
        conn = mock.Mock()
        loop, frame = asyncio.get_running_loop(), object()
        with mock.patch.object(roads, 'BUILD_PER_POSE', 1), \
                mock.patch.object(roads, 'geo_wanted', side_effect=lambda f, x, y, *v: {(0 if x < 500 else 100, 0): 0.}), \
                mock.patch.object(geotiles, 'tiles_near', return_value=[(0, 0, 0.)]), \
                mock.patch.object(geotiles, 'quad', side_effect=quad):
            try:
                tracker.on_pose(conn, 1, 0., 0., loop, build, frame=frame)
                while not entered.is_set():
                    await asyncio.sleep(.001)
                old = tracker.futs[(0, 0)]
                tracker.on_pose(conn, 1, 1100., 0., loop, build, frame=frame)
                requests[0].checkpoint()     # retain work inside the larger drop radius: no edge jitter
                tracker.on_pose(conn, 1, 25600., 0., loop, build, view=(0., 0.), frame=frame)
                requests[0].checkpoint()     # still needed by the camera
                tracker.on_pose(conn, 1, 25600., 0., loop, build, foci=[(0., 0., 100., True)], frame=frame)
                requests[0].checkpoint()     # still needed by another vehicle's collision focus
                tracker.on_pose(conn, 1, 25600., 0., loop, build, frame=frame)
                with self.assertRaises(workcancel.WorkCancelled):
                    requests[0].checkpoint()
                self.assertIn((0, 0), tracker.building)
                self.assertFalse(fresh.is_set())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(old, 2)
                await asyncio.sleep(.01)
                tracker.on_pose(conn, 1, 25600., 0., loop, build, frame=frame)
                end = loop.time() + 2
                while not fresh.is_set() and loop.time() < end:
                    await asyncio.sleep(.001)
                self.assertTrue(fresh.is_set(), 'the next slot builds at the new position')
            finally:
                release.set()
                tracker.close()


if __name__ == '__main__':
    unittest.main()
