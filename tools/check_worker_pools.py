"""Exercise packaged spawn queues without a game.

Default: offline startup/recycling only. --world generates real roads, vegetation
and buildings; --online permits missing-data downloads. --cache PATH selects
the download cache. Generated game files stay in a temporary directory.
"""
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
           else [sys.executable, script]) + ['--child'] + [a for a in sys.argv[1:] if a != '--child']
    env = dict(os.environ, BNGEARTH_PARENT=str(os.getpid()))
    with tempfile.TemporaryDirectory(prefix='bnge-nested-check-') as d:
        log = Path(d) / 'server.log'
        flags = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
        with log.open('w', encoding='utf-8') as out:
            p = subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, **flags)
        try:
            code = p.wait(timeout=900 if '--world' in sys.argv else 240)
        except BaseException:
            p.kill()
            p.wait(timeout=15)
            print(log.read_text(encoding='utf-8', errors='replace'), flush=True)
            raise
        print(log.read_text(encoding='utf-8', errors='replace'), flush=True)
        if code:
            raise SystemExit(code)
    print('Nested launcher/server worker check passed', flush=True)


def world_jobs(workers, root):
    import blockworker
    import os
    import time
    out = Path(root) / 'world-output'
    out.mkdir()
    real_roads = 0
    for round_ in range(2):
        jobs = {}
        print(f'WORLD round {round_ + 1}: generating roads, vegetation and buildings at 56.90000,59.96000', flush=True)
        for i, (gx, gy) in enumerate(((87368, 40220), (87369, 40220), (87368, 40221), (87369, 40221))):
            gx += round_ * 2
            args = (1, 56.9, 59.96, 16, gx, gy, 16, str(out), '/temp/beamngEarth_workercheck',
                    True, 0.0, True, False, False, None, True, 0.0, None, 'RU')
            jobs[workers[1].submit(blockworker.roads_geo, *args)] = ('roads', gx, gy)
            jobs[workers[1].submit(blockworker.veg_geo, 1, 56.9, 59.96, 16, gx, gy,
                                    str(out), '/temp/beamngEarth_workercheck')] = ('trees', gx, gy)
            if i < 2:
                jobs[workers[-1].submit(blockworker.far_buildings_tile, 1, 56.9, 59.96, 16, i + round_ * 2, 0,
                                       str(out), '/temp/beamngEarth_workercheck')] = ('buildings', i, 0)
        t0 = time.monotonic()
        for f in concurrent.futures.as_completed(jobs, timeout=600):
            label = jobs[f]
            try:
                got = f.result()
            except BaseException:
                print(f'WORLD FAILED {label}', flush=True)
                raise
            chunks = got['content'][1] if label[0] == 'roads' and got and got.get('content') else 0
            real_roads += int(chunks > 0)
            print(f'WORLD DONE {label} elapsed={time.monotonic()-t0:.1f}s chunks={chunks}', flush=True)
        # Read the same queues again after native generation has actually run.
        for p in workers:
            pid = p.submit(os.getpid).result(timeout=90)
            print(f'POST-WORLD queue ok: {p.name}, pid={pid}', flush=True)
        if round_ == 0:
            workers[1].recycle('real generation recovery check')
            workers[-1].recycle('real building generation recovery check')
    if not real_roads:
        raise RuntimeError('No real road chunks generated: missing offline data; retry with --online')
    print(f'WORLD workload passed: {real_roads} nonempty road tiles, outputs only in temporary folder', flush=True)


def main():
    import blockworker
    import pools
    logging.basicConfig(level=logging.WARNING)
    with tempfile.TemporaryDirectory(prefix='bnge-worker-check-') as root:
        world = '--world' in sys.argv
        cache = Path.home() / '.cache' / 'beamng-earth'
        if '--cache' in sys.argv:
            cache = Path(sys.argv[sys.argv.index('--cache') + 1]).resolve()
        initargs = ((str(cache), '--online' not in sys.argv, True, True, True, True, None, logging.WARNING)
                    if world else (root, True, False, False, False, False, None, logging.WARNING))
        print(f'Worker check: world={world}, online={"--online" in sys.argv}', flush=True)
        if world:
            import netstate
            import plancache
            netstate.init()
            plancache.start_run(str(cache))
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
            if world:
                world_jobs(workers, root)
        finally:
            for p in workers:
                p.shutdown(wait=True, cancel_futures=True)
            if world:
                netstate.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main() if '--child' in sys.argv else nested()
