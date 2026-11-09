"""Keep ThreadPoolExecutor's lazy thread creation off the world event loop."""
import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

# Imported with the world server, before its event loop starts. This lane is
# already running when a pose submits the first vegetation/building tile.
_submitter = ThreadPoolExecutor(1, thread_name_prefix='tile-submit')
_submitter.submit(lambda: None).result()


def submit(loop, pool, fn, *args):
    context = contextvars.copy_context()

    async def run():
        future = await loop.run_in_executor(_submitter, context.run, pool.submit, fn, *args)
        return await asyncio.wrap_future(future)

    return loop.create_task(run())
