# AGENTS.md — Spidersqdn/DataBase

Shared static data & map assets for **AirNavFlow** and **FalCon2CP**, served at `https://spidersqdn.github.io/DataBase/<folder>/`.
Reply to the owner (SPD) in Thai, keep answers short, and open small PRs.

## Token-saving & data rules
- **NEVER read `CoWork/AIP/*.txt` files in full** (~1.5 MB auto-fetched eAIP text). Use `rg` with specific section numbers (e.g. `AD 2.12`, `AD 2.18`, `AD 2.19`) or check the `aip-watch` GitHub Issue diff. Do not hand-edit `CoWork/AIP/`.
- **NEVER read binary files** (`*.enc`, `*.pdf`, `*.pmtiles`). Never commit `*.pmtiles` (git limit 100 MB).
- **Master editable files live in `CoWork/`** (`|`-separated, `#` = comment):
  - `AP.txt`: `ICAO | IATA | name_th | province | lat | lon | elev_ft | note`
  - `AD.txt`: `ICAO | kind (TWR/GND/APP/NDB/VOR/ILS/TAC/MORSE/...) | value`
  - `RWY.txt`: `ICAO | rwy_id | true_brg_deg | len_x_wid_m | thr_lat_DMS | thr_lon_DMS` (2 consecutive lines per runway)
  - `สนามบิน ทบ.txt`: `type (สนามบิน/หน่วยบิน/ค่ายทหาร) | name | MGRS_or_lat,lon | unit`
- **Folders & tools:**
  - `AirNavFlow/`: `ENROUTE.pdf` → `enroute.pmtiles` (`tools/enroute_tiles.py`); `charts/*.pdf.enc` + `enc.json` (`tools/charts_crypt.py`, `charts_index.py`, `chart_georef.py`, `charts_geo_manual.json`, encrypted with secret `CHART_KEY`); `thailand.pmtiles` & `elevation.pmtiles` built by workflow.
  - `FalCon2CP/`: `map250k.pmtiles` & `map500k.pmtiles` copied from Release tag `falcon2cp-maps` at deploy.
  - `CoWork/places.json`: built at deploy by `tools/places_index.py` from `thailand.pmtiles`.
- **Workflows:** `.github/workflows/build-map-and-deploy.yml` (builds & deploys Pages), `.github/workflows/aip-watch.yml` (`.github/scripts/aip_diff.py`, checks new AIRAC Mondays).
