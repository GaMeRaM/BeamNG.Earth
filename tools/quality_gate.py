#!/usr/bin/env python3
"""Bounded foundation regression gate. Uses synthetic data, not a gameplay benchmark.

Run after installing server/requirements.txt, lupa and scipy and building tools/build_native.py.
The existing full server suite remains available through tools/run_tests.py.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "test_protocol", "test_protocol_agreement", "test_geodesy", "test_cache",
    "test_budget", "test_class_grid", "test_install", "test_updates",
    "test_selfupdate", "test_bmplaunch", "test_launcher_linux", "test_launcher_lifecycle",
    "test_process_lifecycle", "test_connection_cleanup", "test_initial_loading", "test_tile_ownership",
    "test_matslots", "test_stream_reconnect", "test_netfetch", "test_mapdata",
    "test_rangeread", "test_grading", "test_roadz", "test_roadz_inputs",
    "test_road_seams", "test_roadgeo", "test_fast", "test_restart",
    "test_revisit", "test_plancache", "test_bake_formats", "test_chunkcache",
    "test_pools", "test_prefetch_chain", "test_demand", "test_roadwidth",
    "test_roadcorners", "test_sketchfab_assets", "test_subsea_tunnels", "test_tunnels",
    "test_worldbundle", "test_world_cache", "test_peerwork", "test_host_package",
    "test_ru_infrastructure", "test_furniture", "test_buildings", "test_roads",
    "test_blockworker", "test_roadsigns", "test_townentry", "test_markings",
    "test_sign_packaging", "test_walk_clearance", "test_sidewalk_collision", "test_islands",
    "test_carriageway_cell_seams", "test_junction_landing", "test_junction_corridor", "test_junction_pads",
    "test_approaches", "test_bridge_junction_surface", "test_building_passages", "test_bridge_chain_clearance",
    "test_under_deck", "test_underpass_profiles", "test_bridge_clearance", "test_crossings",
    "test_carriageways", "test_package_stamps", "test_carriageway_solver", "test_portugal_imagery",
    "test_gradesep", "test_bridgeattachments", "test_railways", "test_footbridges",
    "test_guardrails", "test_powerlines", "test_power_clearance", "test_vegetation",
    "test_building_overrides", "test_lamp_collision", "test_seacarve", "test_tilepublish",
    "test_colormatch", "test_cpupin", "test_asyncsubmit", "test_logqueue",
    "test_staging", "test_abutment_pad", "test_rail_crossing_assets", "test_native_stress",
    "test_bridge_level_spans", "test_container", "test_designs", "test_de_signs",
    "test_germany", "test_lane_rules", "test_regionaldata", "test_bdtopo",
    "test_revisit_side", "test_revisitpack", "test_workcancel", "test_reach",
    "test_abandon", "test_grade_binned", "test_farpvs", "test_ground_standin",
    "test_ground_square", "test_far_first", "test_halo_reads", "test_enginepatch",
    "test_prov_refresh", "test_drivability",
    "test_memwatch", "test_portals", "test_road_clearance", "test_roadlayercache", "test_speed242", "test_tilecuts", "test_deckjoins", "test_deckpad_levels", "test_warm_queue",
    "test_determinism",
    "test_decisions", "test_latework", "test_enginepatch_terfast", "test_aerialpacks", "test_base_photo_revisit", "test_blockcache", "test_bnwt", "test_farrestore", "test_photo_lawns_in_use", "test_revisit_scopes", "test_world_reset",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--par", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600, help="seconds per Python test module")
    args = ap.parse_args()
    if args.par < 1 or args.timeout < 1:
        ap.error("--par and --timeout must be positive")
    # Optional cached-world tests must not silently change the CI workload on a developer's machine.
    os.environ["BNGE_ROADGEO_REAL"] = "0"
    # Fail before tests instead of accepting skipped native/data-provider coverage.
    sys.path.insert(0, str(ROOT / "server"))
    import fast
    import duckdb
    import fsspec
    import lupa.luajit21
    import lupa.lua53
    import scipy.optimize       # test-only independent reference for the native carriageway QP
    fast.require(fast.MIN_VERSION, "quality gate")
    print(f"Python {sys.version.split()[0]}, earthfast {fast._ef.VERSION}, "
          f"DuckDB {duckdb.__version__}, fsspec {fsspec.__version__}", flush=True)
    commands = [
        [sys.executable, "tools/run_tests.py", *MODULES, "--par", str(args.par),
         "--timeout", str(args.timeout), "--logs", "build/quality-tests"],
        [sys.executable, "tools/run_lua_tests.py"],
        ["node", "--test", "mod/tests/test_mapmath.mjs", "server/tests/test_mapmath.mjs"],
        ["cargo", "test", "--locked", "--manifest-path", "native/serverlist/Cargo.toml"],
        [sys.executable, "tools/package.py", "--beammp", "--out", "build/quality-packages"],
    ]
    for command in commands:
        print("+ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
