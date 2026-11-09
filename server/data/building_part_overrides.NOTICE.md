# Missing OSM building parts

Source: OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright

Captured 2026-11-09 directly from the OSM API:
https://www.openstreetmap.org/api/0.6/relation/2673798/full
The source relation's version is stored in building_part_overrides.json.

Relation 2673798 is the middle triangular volume of ТЦ «Свердловск» / «Призма»,
Екатеринбург, Героев России, 2. Its mapped range is 50.4–122.4 m.
It is absent from the locally decoded Overture building_part layer, while the
adjoining upper parts and parent r2673797 are present. The supplement uses the
source ring and heights without interpolation. It is not added if the source
relation is already present in the loaded parts.
