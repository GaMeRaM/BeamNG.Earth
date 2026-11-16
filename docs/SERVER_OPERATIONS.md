# Server operations

## Cache helpers disabled — 2026-11-17

The user requested removal of both server-side world cache helpers and their data.
Do not recreate helper containers, helper-cache directories, or prewarming jobs on
future releases. Remote deployment directories carry a `HELPER_DISABLED` marker.
Update game-server packages independently of helper services; legacy deployment
scripts that require a helper must be adapted before use.

Keep private settings and rollback backups. Do not restart occupied game servers.
Delete temporary build `-stage` directories after use once no container mounts them.
