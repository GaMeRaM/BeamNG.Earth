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
