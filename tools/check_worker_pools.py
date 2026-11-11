"""Exercise spawn queues and recycling through the packaged app, offline and without a game."""
import concurrent.futures
import logging
import multiprocessing
import sys
import tempfile
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))


def nested():
    # Match launcher.start_server: a second app process, with redirected streams,
    # itself spawning the pools. Direct frozen checks miss this extra level.
    import os
    import subprocess
    script = str(Path(__file__).resolve())
    cmd = ([sys.executable, '--run-addon', script] if getattr(sys, 'frozen', False)
           else [sys.executable, script]) + ['--child']
    env = dict(os.environ, BNGEARTH_PARENT=str(os.getpid()))
    with tempfile.TemporaryDirectory(prefix='bnge-nested-check-') as d:
        log = Path(d) / 'server.log'
        flags = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
        with log.open('w', encoding='utf-8') as out:
            p = subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, **flags)
        try:
            code = p.wait(timeout=240)
        except BaseException:
            p.kill()
            p.wait(timeout=15)
            raise
        print(log.read_text(encoding='utf-8', errors='replace'), flush=True)
        if code:
            raise SystemExit(code)
    print('Nested launcher/server worker check passed', flush=True)


def main():
    import blockworker
    import pools
    logging.basicConfig(level=logging.WARNING)
    with tempfile.TemporaryDirectory(prefix='bnge-worker-check-') as root:
        initargs = (root, True, False, False, False, False, None, logging.WARNING)
        workers = [pools.RespawningPool(name, count, mp_context=multiprocessing.get_context('spawn'),
                                       initializer=blockworker.init, initargs=initargs)
                   for name, count in (('block check', 1), ('road check', 4),
                                       ('far tile check', 2), ('far building check', 1))]
        try:
            for round_ in range(3):
                jobs = [(p.submit(abs, -n), n) for p in workers for n in range(1, 4 * p.workers + 1)]
                for f, n in jobs:
                    assert f.result(timeout=90) == n
                if round_ == 0:
                    assert workers[-1].recycle('packaged queue recovery check')
                    assert workers[1].recycle('shared multi-reader queue recovery check')
            print('Packaged worker queues: 4 pools / 8 workers, 3 rounds and recycle passed', flush=True)
        finally:
            for p in workers:
                p.shutdown(wait=True, cancel_futures=True)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main() if '--child' in sys.argv else nested()
