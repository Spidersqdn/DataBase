# DataBase

Big offline files for [AirNavFlow](https://spidersqdn.github.io/AirNavFlow/), served on GitHub Pages:

- https://spidersqdn.github.io/DataBase/thailand.pmtiles (offline OSM map, ~260 MB)
- https://spidersqdn.github.io/DataBase/elevation.pmtiles (elevation, ~117 MB)

Built by `.github/workflows/build-map-and-deploy.yml` on push, on the 2nd of each month, or Actions → Run workflow.
Settings → Pages → Source must be **GitHub Actions**.
Map size/area: edit `MAP_MAXZOOM`, `ELEV_MAXZOOM`, `MAP_BBOX` in the workflow.
