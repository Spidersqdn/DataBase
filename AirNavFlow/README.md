# AirNavFlow files
Served at https://spidersqdn.github.io/DataBase/AirNavFlow/
- `thailand.pmtiles` offline OSM map (built by the workflow, not stored in git)
- `elevation.pmtiles` elevation (built by the workflow, not stored in git)
Other files committed here are published as they are.
- `ENROUTE.pdf` AIP Thailand ENROUTE CHART - ICAO (AIRAC AMDT 11/26, eff. 29 OCT 26). Replace with the same name for a new AIRAC; the workflow rebuilds `enroute.pmtiles`.
- `charts/` aerodrome charts (PDF / PNG / JPG, sub-folders allowed) shown in the app's CHART box as "ชาร์ตในแอพ". Add or replace files here; the workflow writes `charts/index.json` (file list, PDF page count, page labels) on deploy.
