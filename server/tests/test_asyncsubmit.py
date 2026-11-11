import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncsubmit


class SubmitTest(unittest.IsolatedAsyncioTestCase):
    async def test_completion_waiting_for_loop_is_not_published_after_obsolete(self):
        loop = asyncio.get_running_loop()
        notifications = []
        with ThreadPoolExecutor(1) as pool:
            with mock.patch.object(loop, 'call_soon_threadsafe', side_effect=lambda fn, *args: notifications.append((fn, args))):
                future = asyncsubmit.submit(loop, pool, lambda: 'obsolete result', owned=True)
                end = loop.time() + 2
                while not notifications and loop.time() < end:
                    await asyncio.sleep(.001)
                self.assertTrue(notifications)
                asyncsubmit.request_cancel(future)
                self.assertFalse(future.done())
                for fn, args in notifications:
                    fn(*args)
            with self.assertRaises(asyncio.CancelledError):
                await future

    async def test_obsolete_preparation_is_cancelled_behind_a_slow_thread_start(self):
        entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
        class SlowStart(ThreadPoolExecutor):
            def submit(self, *args, **kwargs):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('test did not release slow submit')
                return super().submit(*args, **kwargs)
        def second_build():
            second_started.set()
        with SlowStart(1) as first_pool, ThreadPoolExecutor(1) as second_pool:
            first = asyncsubmit.submit(asyncio.get_running_loop(), first_pool, lambda: 42)
            try:
                while not entered.is_set():
                    await asyncio.sleep(.001)
                second = asyncsubmit.submit(asyncio.get_running_loop(), second_pool, second_build, owned=True)
                asyncsubmit.request_cancel(second)
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(second, .5)
                self.assertFalse(second_started.is_set())
            finally:
                release.set()
            self.assertEqual(await asyncio.wait_for(first, 2), 42)

    async def test_slow_thread_start_does_not_block_the_event_loop(self):
        entered, release = threading.Event(), threading.Event()
        main = threading.get_ident()

        class SlowStart(ThreadPoolExecutor):
            def submit(self, *args, **kwargs):
                self.assert_worker = threading.get_ident() != main
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('test did not release the executor')
                return super().submit(*args, **kwargs)

        with SlowStart(1) as pool:
            task = asyncsubmit.submit(asyncio.get_running_loop(), pool, lambda: 42)
            try:
                while not entered.is_set():
                    await asyncio.sleep(.001)
                await asyncio.wait_for(asyncio.sleep(.01), .5)
                self.assertTrue(pool.assert_worker)
                self.assertFalse(task.done())
            finally:
                release.set()
            self.assertEqual(await asyncio.wait_for(task, 2), 42)

    async def test_worker_exception_reaches_caller(self):
        def fail():
            raise ValueError('worker failure')
        with ThreadPoolExecutor(1) as pool:
            with self.assertRaisesRegex(ValueError, 'worker failure'):
                await asyncsubmit.submit(asyncio.get_running_loop(), pool, fail)
