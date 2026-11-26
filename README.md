# DataBase

Big data files for AirNavFlow, FalCon2CP and future projects, served on GitHub Pages.

One folder per project, served at https://spidersqdn.github.io/DataBase/<folder>/

- `AirNavFlow/thailand.pmtiles` offline OSM map (~260 MB) and `AirNavFlow/elevation.pmtiles` elevation (~117 MB), built by the workflow
- `AirNavFlow/ENROUTE.pdf` AIP enroute chart; the workflow turns it into `AirNavFlow/enroute.pmtiles` (georeferenced from the lat/long labels on the frame, white made transparent, zoom 5-10) shown in the app as MAP "ENROUTE (AIP)". New AIRAC: upload the new PDF with the same name.
- `CoWork/places.json` offline place-search index (towns, villages, airfields, hospitals, temples, peaks, dams ...: Thai + English names, lat/lon) built at deploy by `tools/places_index.py` from `thailand.pmtiles`; used by AirNavFlow and FalCon2CP. Format: `{"kinds":[...],"p":[[name_th,name_en,lat,lon,kind_index],...]}`
- `AirNavFlow/charts/` built-in charts for the app's CHART box, **password protected**: stored and served only as `<name>.enc` (AES-256-GCM, `tools/charts_crypt.py`). Add a chart: upload the plain PDF here; the workflow encrypts it, deletes the plain file and commits. Password = repo secret `CHART_KEY` (Settings → Secrets and variables → Actions); users type the same password in the app (🔓 LOGIN CHART). `enc.json` holds the salt (not secret); changing the password needs every chart re-encrypted.
- `FalCon2CP/` reserved for FalCon2CP
- `CoWork/` shared data used by several apps (airport info `AD.txt`, runways `RWY.txt`, army airfields `สนามบิน ทบ.txt`). Edit these here; AirNavFlow and FalCon2CP read them from https://spidersqdn.github.io/DataBase/CoWork/
- New project: add a folder and add its name to the `for d in ...` line in the workflow

Built by `.github/workflows/build-map-and-deploy.yml` on push, on the 2nd of each month, or Actions → Run workflow.
Settings → Pages → Source must be **GitHub Actions**.
Map size/area: edit `MAP_MAXZOOM`, `ELEV_MAXZOOM`, `MAP_BBOX` in the workflow.
