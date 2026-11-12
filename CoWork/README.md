# CoWork: shared data for every app (AirNavFlow, FalCon2CP, ...)
Served at https://spidersqdn.github.io/DataBase/CoWork/

| File | Content |
|---|---|
| `AD.txt` | Airport info (freq, nav aids, remarks) per ICAO |
| `RWY.txt` | Runway ends (ID, bearing, size, lat/long) per ICAO |
| `สนามบิน ทบ.txt` | Army airfields (type, name, MGRS or lat,long, unit) |

Edit here only (pencil icon on GitHub, Commit). The site updates in a few minutes; apps pick it up on next open
and keep an offline copy. Format: `a | b | c` per line, `#` = comment.
AirNavFlow falls back to its own `data/` copy if this site cannot be reached.
