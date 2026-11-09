"""Keep ThreadPoolExecutor's lazy thread creation off the world event loop."""
import contextvars
from concurrent.futures import ThreadPoolExecutor

# Imported with the world server, before its event loop starts.
_submitter = ThreadPoolExecutor(1, thread_name_prefix='tile-submit')
_submitter.submit(lambda: None).result()


def submit(loop, pool, fn, *args):
    result = loop.create_future()
    context = contextvars.copy_context()
    pending = [None]

    def deliver(future):
        if result.done():
            return
        if future.cancelled():
            result.cancel()
        elif future.exception() is not None:
            result.set_exception(future.exception())
        else:
            result.set_result(future.result())

    def notify(future):
        if not loop.is_closed():
            try:
                loop.call_soon_threadsafe(deliver, future)
            except RuntimeError:
                if not loop.is_closed():
                    raise

    def prepare():
        if result.cancelled():
            return
        try:
            future = pool.submit(fn, *args)
        except BaseException as error:
            from concurrent.futures import Future
            future = Future()
            future.set_exception(error)
        pending[0] = future
        if result.cancelled():
            future.cancel()
        # Deliver directly, avoiding two extra trips through the event loop for
        # every tiny cached tile (notably costly with Windows timer granularity).
        future.add_done_callback(notify)

    def cancel(done):
        if done.cancelled() and pending[0] is not None:
            pending[0].cancel()

    result.add_done_callback(cancel)
    _submitter.submit(context.run, prepare)
    return result
