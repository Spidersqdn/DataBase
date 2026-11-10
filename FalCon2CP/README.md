# FalCon2CP files
Served at https://spidersqdn.github.io/DataBase/FalCon2CP/

Maps (`map250k.pmtiles`, `map500k.pmtiles`) are not committed (git limit 100 MB).
Upload them to Release tag `falcon2cp-maps` (Releases > Draft a new release > tag `falcon2cp-maps` > attach files > Publish).
Then Actions > Build offline map and deploy > Run workflow. It copies every `*.pmtiles` from the release here.
To replace a map: delete the old asset in the release, upload the new one, save.
