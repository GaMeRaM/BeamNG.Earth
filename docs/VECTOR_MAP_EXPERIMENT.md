# MapLibre vector map experiment

Branch: `experiment/maplibre-dashboard` in https://github.com/GaMeRaM/BeamNG.Earth

Both the vehicle navigator and the M map use OpenFreeMap's Liberty style:
https://tiles.openfreemap.org/styles/liberty. No API key is needed.
MapLibre GL JS 4.7.1 is bundled locally, including its BSD license. This version
supports WebGL 1 fallback, chosen for the game's embedded CEF rather than requiring WebGL 2.

Install the mod and run the companion **from the same branch**. The new
`vector_resource` protocol is needed on both sides. Restart both after updating.
Use the existing dashboard enable switch (now labelled “Vector map on dashboard
screens”). On M, choose Layers → Vector (OpenFreeMap). New profiles default to
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

Still requires BeamNG validation: WebGL/worker availability in the vehicle
WebView, visible rendering on an actual car screen, alignment of M-map overlays,
reopening M, switching cars, and frame time while driving. In particular, this
experiment does not establish that MapLibre works in the game's CEF runtime.
If a vehicle WebView cannot create WebGL, the screen reports the initialization
error; disabling its dashboard switch restores the stock navigation page.
