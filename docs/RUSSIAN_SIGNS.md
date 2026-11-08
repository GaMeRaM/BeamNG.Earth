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

Upstream PRs #505, #883, #882 and #843 were inspected. Their wider infrastructure,
town-board or US-shield changes were not merged: this implementation reuses the
existing native version 149 and the metric exit planner, with no protocol change.

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
