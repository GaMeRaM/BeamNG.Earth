# Russian direction and highway signs (experimental)

Enable **World → Roads → Highway signs** for posted Russian exit destinations.
Enable **Direction signs** as well for additional junction boards pointing towards towns.
Install this fork's companion application: the Python generator runs locally, so updating
only the BeamMP client mod is insufficient. Existing caches do not need deleting.

## Two sources, different confidence

* Highway exit boards use OSM's mapped destination names, route references and exit
  numbers. Missing destinations produce no board. The existing metric exit planner
  places approach, decision and ramp boards beside the corresponding carriageway,
  checking road clearance and bridge footprints. These are generated placements,
  not surveyed locations of physical signs.
* Direction boards use Overture roads and a bundled snapshot of towns. The existing
  junction algorithm selects destinations by direction and proximity; it does not
  compute a road route to each town. Russian boards therefore omit approximate
  distances and English names. A suggested town can still be inappropriate.

Both use Cyrillic-capable native text rendering. Blue boards represent ordinary
out-of-town roads, green actual `motorway` roads, and white urban boards. A divided
`trunk` alone does not qualify for green. Russian route network tags and Latin/Cyrillic
М/Р/А references are supported. This is an approximate Russian visual profile,
not a claim of full GOST compliance (`verified: false` in the style).
American overhead boards and mile markers remain US-specific.

## Checked near Yekaterinburg

Live source audit west of the city found posted exits towards **Пермь**, **ЕКАД (север)**
and **ЕКАД (юг)**, with references Р-242, М-12 and 65К-4108000. Using actual road
geometry and a flat test elevation produced nine placements and five distinct faces.
Other sampled approaches (Polevskoy/EKAD and the eastern Р-351 approach) had no mapped
exit objects in the inspected area. Coverage is not sufficient to promise a complete
GPS-free journey everywhere.

Native tests cover distinct Cyrillic glyphs, textured meshes, material joins, route
references, board colours and mapped exits with inferred direction boards disabled.
Visual face inspection and real-data generation were performed headlessly; driving,
terrain clearance and readability at speed still require an in-game check.

## Sources and scope

* [OSM destination tags](https://wiki.openstreetmap.org/wiki/Key:destination), via the
  existing [weekly sign index](https://tecnagamer.github.io/BeamNG.Earth-data/signs/).
* [Russian route networks](https://wiki.openstreetmap.org/wiki/RU:Key:network).
* Overture divisions 2026-10-21.0: 3,738 Russian localities added to the existing
  four-country snapshot. See `server/data/places.NOTICE.md`.

The initial maplibre.6 exit-board implementation inspected PRs #505, #883, #882
and #843 without importing them; it used native version 149 and the metric exit
planner. The extended pack below now imports selected code/assets, requires native
version 163 and adds the `road_signs` settings message and `rsigns` sign meshes.

## Extended Russian pack

The next experimental build additionally enables, for Russia:

* Ordinary road signs: crossings, bends, narrowing, roundabouts, no entry,
  dead ends, motorway/living-zone/one-way signs, tunnels, bus stops and parking,
  plus mapped stop/give-way nodes. These reuse PR #882's native road-network
  rules; locations inferred from geometry are not surveyed physical signs.
  A dedicated atlas gives motorways green fields and living-zone boards blue
  fields. This remains an approximate visual profile, not a certified GOST renderer.
* Town entry/exit boards with Cyrillic names, white background and red exit slash.
  PR #597's built-up-area algorithm places them along eligible paved streets.
  It excludes motorway/trunk/link roads, so it does not yet cover blue name-only
  highway boards. Boundary estimates may differ substantially from real sign locations.
* Russian marking profile: representative permitted 1:3 dash/gap patterns
  (urban 2/6 m, rural 3/9 m, motorway lane lines 4/12 m), urban line width 0.10 m,
  rural 0.15 m. Source: GOST R 51256-2018, table A.1, published by
  [Moscow city](https://www.mos.ru/upload/documents/files/1106/GOSTR51256-2018TehnicheskiesredstvaorganizaciidorojnogodvijeniyaR_.pdf).
  Road class/urban context selects a representative pattern, not surveyed paint.
* Concrete utility poles with their own insulator/wire attachment coordinates,
  steel/concrete street lamps, and brackets on utility poles. Lens and glow
  positions follow the new luminaires. Concrete/steel distribution is a scenery
  preset, not a national statistic. Existing clearance and bridge checks remain.
* Inferred reflector posts on paved rural main roads, at a stable 50 m sampling
  interval, away from segment ends and other carriageways. These are decorative,
  without collision meshes. Placement is not a reconstruction of a road's actual
  reflector inventory.

`Road signs` is enabled by default and can be toggled in World settings. It needs
`Roads` and `Highway signs`. Town boards and local scenery are enabled for Russia
by default; set `BNE_TOWNSIGNS=off` or `BNE_RU_INFRA=off` before starting the
companion to disable either. Explicit `BNE_TOWNSIGNS=on` also opts in to the
imported town generator's other supported countries. `BNE_ROADSIGNS=off` disables
ordinary signs globally. These environment changes require restarting the local
companion application. No remote server restart is performed by this change.

The country gate follows the existing companion country detection (nearest airport).
If its airport database is unavailable and the country is unknown, Russian-specific
scenery/ordinary signs will not be selected. Accurate polygon country selection is
not included. Traffic-light housings, AI priorities and unposted speed defaults
remain the existing implementation; the pack does not claim a complete Russian
traffic-rules simulation.

Pinned upstream sources:
* PR #882: `c7ce1e88995260b7e40427187500a39340e62853`.
* PR #597: `01c7c547755828ba1b94a5b927bf61b6bbf40780`.
* PR #883: `7220275748c8bfd2b5941fd3dfad1fb8a089dad5`.
* PR #505: `eb73b0f7f02b1ddc42664d5da7ffcd095469daa2`.

Validation: 186 targeted Python tests and offline LuaJIT sign/town/road/Forest
lifecycle tests. A real-data audit produced crossing and bus-stop signs near VIZ
and found Revda/Pervouralsk town polygons. Generated face inspection was performed
headlessly. In-game appearance, night lighting, terrain clearance and performance
still require a driving test; no FPS claim is made.

## Incident and rollback (2026-11-09)

The maplibre.7 player log showed 57 distinct road geotiles repeatedly failing in
`ruinfra.markers`: `float(ground(x, y))` assumed a scalar, while the actual
`roadmesh.drawn_ground` callback returns an `(n,)` NumPy array even for one query.
This was a local companion road-generation failure, not a VPS container restart.
The first tests omitted the production terrain callback and missed the integration bug.

The experiment now samples all post heights in one vectorized call, validates the
result size, and isolates optional post-generation errors so they cannot abort road
geometry. A regression test uses the actual `drawn_ground` callback; another forces
a terrain failure and verifies that poles and wires still build. The affected
Python test selection (165 tests) passes.

Production was rolled back to official **v1.8.2-beta / a4053d3**, retaining the
Yekaterinburg spawn, custom server plugin and shared cache. The fix remains on the
experimental branch and is not deployed. Players must also run the official
companion EXE: changing the BeamMP server alone cannot replace a running local
maplibre.7 generator. Further production changes/restarts require explicit approval.

## Checks before another experimental release

The Windows build now runs the bounded road/terrain integration suite before
packaging an EXE. The foundation gate also includes the Russian scenery, road,
furniture, worker, sign and marking tests. Diagnostic artifacts retain per-module
logs and the tested Python dependency versions, including on a failed build.

The end-to-end synthetic scene uses real `roads.build_tile`, `drawn_ground`, native
road meshes and `roads.write_tile` on flat and sloping terrain. It asserts that
road geometry, Russian poles and reflector posts actually exist, that their
heights agree with the terrain callback, and that no optional-layer warning was
silently swallowed. Injecting the previous production failure makes the scene
fail. This complements the failure-isolation test: decorative failures must not
break drivable roads, but must still be detected by validation.

Passing these automated checks does not replace an in-game acceptance drive.
Before production, compare a fixed route in Yekaterinburg, the Р-242/ЕКАД junction
and a rural road against the official build, with cold and warm caches, day/night,
and reconnects. Check logs for failed tiles, visible holes and missing scenery.
Until that acceptance is done, production stays on the official release.

## Local roadside fixes (not released, 2026-11-09)

At 56.66043, 61.16976, two Microsoft ML Buildings footprints (14 and 18 m²)
lay 4.35–4.39 m from the road centre, inside its generated 9 m carriageway.
The previous fixed 4 m centre-distance filter kept both. Near the second report,
56.62750, 61.28645, another ML footprint's centre was 6.23 m away but its outline
protruded over 1 m into the carriageway. Near and far building generation now use
road-spec widths and reject ML footprints centred on the road or with vertices
more than 0.5 m inside its edge. Explicit OSM buildings retain their existing
handling. This is a collision-avoidance heuristic for ML footprints, not a claim
that the source objects have been identified as vehicles or bus shelters.

Buildings explicitly classified as `shelter`, `roof` or `carport` now have a thin
roof and posts in the near, far, skyline and collision meshes, rather than closed
house walls. Unclassified stop shelters cannot be distinguished reliably from
other small ML footprints; this does not introduce a complete bus-stop model.

The offline fixture `server/tests/fixtures/ekb_roadside_buildings.json` preserves
the reported contours, road geometry and widths, plus adjacent buildings which
must remain. Tests also exercise actual tile filtering (ML versus OSM) and cast
rays through canopy entrances in all four mesh variants. The building module is
included in the experimental Windows and local foundation gates. The targeted
seven-module run passes 299 tests; in-game verification remains outstanding.

### Raised sidewalks at merges and slip lanes

The previous cut tested only the sidewalk centreline. At a shallow slip-lane fork,
the remaining 2.5 m slab could protrude into the carriageway. The cut now samples
the entire cross-section, including mitres and the sloping back of the slab, using
the existing native blocker test. Joining two short runs checks the resulting
slab too, so it cannot reconnect across the lane. The existing centreline cut is
retained for sidewalk ownership at ordinary street corners.

Corner returns had a separate sparse-probe failure: generated slabs near the
Makarovsky bridge crossed their adjacent roads between the probes. Candidate
corners now also check their actual mesh vertices, triangle edge midpoints and
centroids against the carriageways. The radius search tries a tighter corner;
a corner which cannot fit is omitted instead of placing a raised obstacle on the
road. This does not change bridge deck elevations or road grading.

`test_walk_clearance` checks shallow forks, a fork at a tile seam, slab backs,
unsafe run joins, and captured Makarovsky corner geometry. It tests both visible
and collision meshes; disabling full-width clipping reproduces the old failure.
The Windows and local gates now include this and the existing sidewalk, island,
corner, approach and junction modules. The targeted selection passes 403 tests.

A headless replay checked four road tiles at each of Р-242/ЕКАД, Koltsovo
(56.77166, 60.88242) and Makarovsky (56.8478, 60.5894). After the changes, the
sampled raised mesh vertices and triangle centroids no longer intruded over
0.15 m into the checked ground carriageways at 0.08–0.6 m above their road
profiles. Р-242/ЕКАД generated no raised sidewalks in these four tiles, so that
scene does not validate raised sidewalks there. Width measurement was disabled
for this replay; it is a reproducible geometry check, not an in-game acceptance
drive or a guarantee for every interchange. Local audit output is under
`build/ekb-bridge-audit/walks-final.json`.
