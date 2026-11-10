# DataBase

Big data files for AirNavFlow, FalCon2CP and future projects, served on GitHub Pages.

One folder per project, served at https://spidersqdn.github.io/DataBase/<folder>/

- `AirNavFlow/thailand.pmtiles` offline OSM map (~260 MB) and `AirNavFlow/elevation.pmtiles` elevation (~117 MB), built by the workflow
- `FalCon2CP/` reserved for FalCon2CP
- New project: add a folder and add its name to the `for d in ...` line in the workflow

Built by `.github/workflows/build-map-and-deploy.yml` on push, on the 2nd of each month, or Actions → Run workflow.
Settings → Pages → Source must be **GitHub Actions**.
Map size/area: edit `MAP_MAXZOOM`, `ELEV_MAXZOOM`, `MAP_BBOX` in the workflow.
