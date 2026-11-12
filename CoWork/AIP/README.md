# CoWork/AIP: latest AIP Thailand cycle as plain text
Filled by `.github/workflows/aip-watch.yml` (every Monday 14:00 Bangkok, or Actions > AIP AIRAC watch > Run workflow).
When a new AIRAC is out it replaces the `*.txt` here (one file per eAIP page: AD 2 per airport, ENR 3/4/5.1, AMDT, SUP, AIC),
writes `AIRAC.txt` (cycle date), commits, redeploys and opens an Issue with what changed. Older cycles: git history.
Do not edit these files by hand; edit `../AD.txt`, `../RWY.txt` using the Issue as a guide.
Source: https://aip.caat.or.th/ (public eAIP).
