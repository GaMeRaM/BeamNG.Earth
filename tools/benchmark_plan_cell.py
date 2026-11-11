#!/usr/bin/env python3
"""Time one fresh cell plan with cached source data, without a game or downloads.

Run each sample as a NEW process; alternate --server-root to compare checkouts.
The timer excludes worker initialization and optional diagnostic serialization.
This measures planning, not game FPS or end-to-end startup. Complete cached plans
are deliberately bypassed; source caches remain enabled. Example:

python tools/benchmark_plan_cell.py --cache /path/to/cache --cell 14/10950/5035
"""
import argparse
import json
import os
from pathlib import Path
import pickle
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--cell', required=True, help='z/x/y')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--save-plans', type=Path, help='optional trusted local diagnostic pickle')
    args = parser.parse_args()
    sys.path.insert(0, str(args.server_root.resolve() / 'server'))
    import blockworker
    import mapcells
    import plancache
    os.environ.pop(plancache.RUN_ENV, None)
    blockworker.init(str(args.cache.resolve()), True, True, True, True, True, None, 30)
    key = mapcells.CellKey(*(int(v) for v in args.cell.split('/')))
    lat, lon = key.center()
    grader, _ = blockworker._s.anchor(999, lat, lon)
    planner = grader.store.planner_of_cell(key)
    planner.shared = None
    start, cpu = time.perf_counter(), time.process_time()
    plans = planner._cell_plans(key)
    wall_s, cpu_s = time.perf_counter() - start, time.process_time() - cpu
    if not plans:
        raise RuntimeError('No plans: choose a populated cell with its source data cached')
    result = dict(cell=str(key), wall_s=wall_s, cpu_s=cpu_s, plans=len(plans),
                  mode='offline source cache; fresh process and plans')
    if args.save_plans:
        args.save_plans.parent.mkdir(parents=True, exist_ok=True)
        args.save_plans.write_bytes(pickle.dumps(plans))
    encoded = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end='', flush=True)


if __name__ == '__main__':
    main()
