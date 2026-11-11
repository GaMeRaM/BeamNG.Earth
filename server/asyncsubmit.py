"""Keep ThreadPoolExecutor's lazy thread creation off the world event loop."""
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import CancelledError
import workcancel

# Imported with the world server, before its event loop starts.
_submitter = ThreadPoolExecutor(1, thread_name_prefix='tile-submit')
_submitter.submit(lambda: None).result()


def submit(loop, pool, fn, *args, owned=False):
    result = loop.create_future()
    request = workcancel.Request()
    result.work_request = request
    context = contextvars.copy_context()
    pending = [None]

    def deliver(future):
        if result.done():
            return
        try:
            request.checkpoint()
        except workcancel.WorkCancelled:
            result.cancel()          # completed meanwhile, but no longer wanted: do not publish stale output
            return
        if future.cancelled():
            result.cancel()
        elif future.exception() is not None:
            error = future.exception()
            if isinstance(error, (CancelledError, workcancel.WorkCancelled)):
                result.cancel()
            else:
                result.set_exception(error)
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
            request.checkpoint()
            @functools.wraps(fn)
            def run():
                request.checkpoint()
                # Shared/coalesced producers must finish for their other
                # consumers. Only explicitly owned builds expose inner checkpoints.
                with workcancel.scope(request if owned else None):
                    value = fn(*args)
                request.checkpoint()
                return value
            future = pool.submit(run)
        except BaseException as error:
            from concurrent.futures import Future
            future = Future()
            future.set_exception(error)
        pending[0] = future
        request.bind(future.cancel)
        if result.cancelled():
            future.cancel()
        # Deliver directly, avoiding two extra trips through the event loop for
        # every tiny cached tile (notably costly with Windows timer granularity).
        future.add_done_callback(notify)

    def cancel(done):
        if done.cancelled():
            request.cancel()

    result.add_done_callback(cancel)
    preparation = _submitter.submit(context.run, prepare)
    request.bind(preparation.cancel)
    def prepared(future):
        if future.cancelled() or future.exception() is not None:
            notify(future)
    preparation.add_done_callback(prepared)
    return result


def request_cancel(future):
    """Ask a build to stop; leave its slot occupied until it actually stops."""
    request = getattr(future, 'work_request', None)
    return request.cancel() if request is not None else False
