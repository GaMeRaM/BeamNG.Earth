# Fork changes and the 1.9.0 add-on API

Use `origin/dev` (`TecnaGamer/BeamNG.Earth`, branch `dev`) as the integration
upstream for this fork. `main` and release tags remain the reference for official
releases. Locally, `origin/HEAD` and the tracking branch `upstream-dev` point to
`origin/dev`; `experiment/maplibre-dashboard` tracks the fork's branch for pushes.

Fetch upstream before comparing or merging. Integrate `origin/dev` explicitly,
resolve overlaps with the fork's world-generation changes, and run the quality
gate and reported-site audit before building or deploying. Do not reuse an
upstream cache format number for different fork output without invalidating it.


The supported API in [ADDONS.md](ADDONS.md) provides player pose/place, GPS destination,
teleportation, notifications and world/arrival events. The companion feed exposes position.
It does not provide hooks for Python world generation, generated meshes/collision, tile
providers, vehicle navigation screens or the built-in map UI.

Consequently these fork features currently remain core patches:

- Vector tiles, dark map style, dashboard renderer and route overlay: require map/provider
  and dashboard renderer hooks. GPS API v1 gives destination and progress, not route geometry.
- Russian roadside assets, placement and direction signs: require a tile prop/sign provider.
- Building passage cuts and collision: require a building geometry modifier.
- Bridge grading and ramp/sidewalk corrections: require terrain/road planning hooks and
  cache-version integration; retain them as core fixes suitable for upstream contributions.
- Centre-line rules: require a marking-style provider.

New GPS consumers, driving missions and location overlays should use the documented API
and ship as separate mods. Do not replace internal functions at runtime to simulate missing
hooks: that would keep the same compatibility problems while hiding them in another ZIP.
No registry entry or external release is published by this merge. Extraction should happen
feature by feature when the corresponding supported hook exists.
