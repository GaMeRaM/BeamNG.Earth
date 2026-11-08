# Bundled direction-sign destination database

Derived from Overture Maps Foundation divisions/division, release **2026-10-21.0**.
© OpenStreetMap contributors; available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Source: https://stac.overturemaps.org/2026-10-21.0/divisions/division/00000/00000.json

The derived snapshot contains cities, towns, and villages with population at least
3,000, retaining names, coordinates, class and population. It contains 12,543 places:
CZ 567, DE 4,121, PL 2,293, RU 3,738, UA 1,824.

Rebuild from the repository root with DuckDB installed:

```sh
python tools/build_places.py --countries UA,CZ,PL,DE,RU --output server/data/places_2026-10-21.0.json.gz
```

SHA-256 of the compressed snapshot:
`3e245bc2ed118ff69720e14284ab5e7d42b701eaa512f8d7fdff6e0316fae14d`.
The tool sorts rows and uses deterministic gzip headers. The snapshot is shipped;
players do not need DuckDB extensions or to download the full divisions dataset.
