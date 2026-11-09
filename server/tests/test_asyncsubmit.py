import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncsubmit


class SubmitTest(unittest.IsolatedAsyncioTestCase):
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
