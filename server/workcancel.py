"""Cooperative cancellation of one owned tile build, never of a shared producer.

Requests live in the server's threads. A cancellable process pool gives each
request one byte in an inherited RawArray, held until its actual future ends.
Workers check it only at explicit safe boundaries; no process is terminated.
"""
import contextvars
import threading
from contextlib import contextmanager


class WorkCancelled(BaseException):
    """Not an ordinary build failure: broad geometry fallbacks must not swallow it."""


_current = contextvars.ContextVar('tile_work_request', default=None)
_flags = None


class Request:
    def __init__(self):
        self._lock = threading.Lock()
        self._cancelled = False
        self._callbacks = []

    def bind(self, callback):
        with self._lock:
            cancelled = self._cancelled
            if not cancelled:
                self._callbacks.append(callback)
        if cancelled:
            callback()

    def cancel(self):
        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            callback()
        return True

    def checkpoint(self):
        if self._cancelled:
            raise WorkCancelled()


class WorkerRequest:
    def __init__(self, flags, slot):
        self.flags, self.slot = flags, slot

    def checkpoint(self):
        if self.flags[self.slot]:
            raise WorkCancelled()


def attach(flags):
    global _flags
    _flags = flags


def current():
    return _current.get()


@contextmanager
def scope(request):
    token = _current.set(request)
    try:
        yield
    finally:
        _current.reset(token)


def worker_scope(slot):
    return scope(WorkerRequest(_flags, slot) if slot is not None and _flags is not None else None)


def checkpoint():
    request = current()
    if request is not None:
        request.checkpoint()
