"""Keep slow console/file handlers off the world server's event loop."""
import atexit
import logging
from logging.handlers import QueueHandler, QueueListener
from queue import SimpleQueue


def start(logger=None):
    """Move existing output handlers to one listener; preserve ordering and levels.

    Call after basicConfig, before starting workers. Later lightweight handlers
    (such as performance error counters) can still attach to the root logger.
    """
    logger = logging.getLogger() if logger is None else logger
    handlers = tuple(logger.handlers)
    queue = SimpleQueue()
    handler = QueueHandler(queue)
    listener = QueueListener(queue, *handlers, respect_handler_level=True)
    logger.handlers = [handler]
    listener.start()

    def stop():
        logger.handlers = list(handlers)
        listener.stop()      # drains records before logging.shutdown closes outputs
        atexit.unregister(stop)

    atexit.register(stop)
    return stop
