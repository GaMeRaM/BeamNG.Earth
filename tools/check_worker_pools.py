"""Exercise spawn queues and recycling through the packaged app, offline and without a game."""
import concurrent.futures
import logging
import multiprocessing
import sys
import tempfile
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))


def main():
    import blockworker
    import pools
    logging.basicConfig(level=logging.WARNING)
    with tempfile.TemporaryDirectory(prefix='bnge-worker-check-') as root:
        initargs = (root, True, False, False, False, False, None, logging.WARNING)
        workers = [pools.RespawningPool(name, 1, mp_context=multiprocessing.get_context('spawn'),
                                       initializer=blockworker.init, initargs=initargs)
                   for name in ('block check', 'road check', 'far tile check', 'far building check')]
        try:
            for round_ in range(3):
                jobs = [(p.submit(abs, -n), n) for p in workers for n in range(1, 5)]
                for f, n in jobs:
                    assert f.result(timeout=90) == n
                if round_ == 0:
                    assert workers[-1].recycle('packaged queue recovery check')
            print('Packaged worker queues: 4 pools, 3 rounds and recycle passed', flush=True)
        finally:
            for p in workers:
                p.shutdown(wait=True, cancel_futures=True)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
