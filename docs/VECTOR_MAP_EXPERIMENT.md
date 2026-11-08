# MapLibre vector map experiment

Branch: `experiment/maplibre-dashboard` in https://github.com/GaMeRaM/BeamNG.Earth

Both the vehicle navigator and the M map use OpenFreeMap's Dark style:
https://tiles.openfreemap.org/styles/dark. No API key is needed.
MapLibre GL JS 4.7.1 is bundled locally, including its BSD license.
When WebGL is unavailable (as in BeamNG CEF), OpenLayers 10.11.0 with
ol-mapbox-style 13.9.0 draws the same vector tiles and Dark style through
Canvas2D. Canvas labels use the local Arial font instead of remote PBF glyphs. This version
supports WebGL 1 fallback, chosen for the game's embedded CEF rather than requiring WebGL 2.

Install the mod and run the companion **from the same branch**. The new
`vector_resource` protocol is needed on both sides. Restart both after updating.
Use the existing dashboard enable switch (now labelled “Vector map on dashboard
screens”). On M, choose Layers → Vector Dark (OpenFreeMap). New profiles default to
Vector; existing saved base-layer choices are respected.

The main map keeps its existing input, search, markers, GPS, cache overlay and
teleport controls. Its geographic overlays stay above the MapLibre canvas.
MapLibre zoom is one lower than the old 256-pixel raster zoom, preserving scale.
Vehicle maps follow position and heading at the existing 10 Hz update rate.

The companion fetches the style, TileJSON, glyphs, sprite images and tile data.
A MapLibre custom protocol delivers JSON or binary buffers through the existing
Lua/TCP bridge; browser HTTP access to the provider is unnecessary. Requests are
restricted to HTTPS on tiles.openfreemap.org, at most four active per map page,
with 60-second client timeouts. A shared 64-entry memory LRU and 2 MiB per-resource
limit bound caching. No disk cache or offline-area download is implemented for
this layer. The public service is an external dependency.

## Validation

Automated checks cover binary/JSON transport, provider restrictions, cache reuse,
response size, request concurrency/cancellation, vehicle camera scale and screen
lifecycle. The Vue script and template compile successfully. Live companion
fetches have been checked for style, TileJSON, a vector tile, sprite JSON/PNG and
a glyph range.

A browser smoke test with WebGL disabled and browser HTTP requests blocked
rendered real OpenFreeMap vector tiles, buildings, labels and sprites through the
Lua-bridge API shim. It confirmed `webgl: false`, Canvas2D rendering and no page
errors. Resource HTTP was handled by the test harness, representing the companion.

Still requires BeamNG validation: visible rendering on an actual car screen,
alignment of M-map overlays, reopening M, switching cars, and frame time while
driving. The supplied screenshot showed `GL_VENDOR = Disabled` in BeamNG; this
is why the Canvas2D fallback is now used there. If initialization fails, the
screen reports the error; disabling its dashboard switch restores the stock page.

## Rebuilding the Canvas bundle

```
cd tools/vector_canvas
npm ci
npm run build
```

The pinned lockfile and source produce `earth_canvas.js`, `earth_canvas.css` and
`earth_canvas.LICENSES.txt` under the mod's `vehicles/common/` directory. The
Windows experiment workflow rebuilds them before packaging. No npm installation
is needed by the player.

The Canvas camera negates clockwise vehicle bearing to match OpenLayers view
rotation. Regression tests use OL’s real coordinate-to-pixel transform at ten
headings and ensure forward stays up and right stays right. Run `npm test` in
`tools/vector_canvas/`. Both renderers default to OpenFreeMap’s Dark style.
