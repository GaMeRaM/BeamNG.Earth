import logging
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import logqueue


class LoggingTest(unittest.TestCase):
    def test_slow_output_does_not_hold_producer_and_shutdown_drains(self):
        entered, release = threading.Event(), threading.Event()
        records = []

        class SlowOutput(logging.Handler):
            def emit(self, record):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('test output not released')
                records.append(record.getMessage())

        logger = logging.Logger('queue-test', logging.DEBUG)
        output = SlowOutput(logging.WARNING)
        logger.addHandler(output)
        stop = logqueue.start(logger)
        try:
            logger.warning('first')
            self.assertTrue(entered.wait(2))
            # The listener holds the output lock here. This call must not wait for it.
            producer = threading.Thread(target=lambda: logger.error('second'))
            producer.start()
            producer.join(.5)
            self.assertFalse(producer.is_alive())
            logger.info('filtered')
        finally:
            release.set()
            stop()
        self.assertEqual(records, ['first', 'second'])
        self.assertEqual(logger.handlers, [output])
