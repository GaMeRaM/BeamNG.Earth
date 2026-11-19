# Bundled direction-sign destination databases

Derived from Overture Maps Foundation divisions/division.
© OpenStreetMap contributors; available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).

- [2026-11-18.0](https://stac.overturemaps.org/2026-11-18.0/divisions/division/00000/00000.json)
  supplies the Czech, German, Polish and Ukrainian destinations.
  SHA-256 `40b3f23fd1f955e7249aad81b0f36cff3fd7551368af05c9fd9a8c9a2963be89`.
- [2026-10-21.0](https://stac.overturemaps.org/2026-10-21.0/divisions/division/00000/00000.json)
  supplies 3,738 Russian destinations. The bundled file retains all 12,543 rows
  of the original snapshot. The loader selects its Russian rows.
  SHA-256 `3e245bc2ed118ff69720e14284ab5e7d42b701eaa512f8d7fdff6e0316fae14d`.

The snapshots retain place names, coordinates, class and population. They
include cities, towns, and villages with population of at least 3,000.
With DuckDB installed, use `tools/build_places.py --release … --countries … --output …`
to rebuild a snapshot. The tool sorts rows and uses deterministic gzip
headers. Players receive the snapshots with the app.
