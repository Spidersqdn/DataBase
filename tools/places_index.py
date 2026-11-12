#!/usr/bin/env python3
"""Offline place-search index for AirNavFlow + FalCon2CP (served as CoWork/places.json).
Reads the named points of the 'places' layer (city, town, village, ...) and of the useful kinds
of the 'pois' layer (airfield, hospital, temple, peak, dam, ...) from the highest zoom of the
Protomaps map (thailand.pmtiles) and writes one compact JSON file:
  {"v":1, "built":"YYYY-MM-DD", "kinds":[...],
   "p":[[name_th, name_en_or_"", lat, lon, kind_index], ...]}   (places first, then by rank)
Usage: python3 tools/places_index.py map/thailand.pmtiles site/CoWork/places.json"""
import gzip, json, math, os, sys, time
from multiprocessing import Pool

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles, tileid_to_zxy  # noqa: F401

LAYERS = (b"places", b"pois")
# pois kinds worth finding from the air (others, e.g. shops, are skipped to keep the file small)
POI_KINDS = {
    "aerodrome", "airfield", "airport", "helipad", "heliport", "military", "naval_base", "barracks",
    "hospital", "clinic", "school", "university", "college", "place_of_worship", "temple", "monastery",
    "peak", "volcano", "saddle", "cliff", "cave_entrance", "waterfall", "spring", "beach", "bay",
    "cape", "island", "islet", "dam", "weir", "reservoir", "lake", "lighthouse", "tower",
    "communications_tower", "power_plant", "plant", "stadium", "golf_course", "park",
    "national_park", "nature_reserve", "protected_area", "forest", "zoo", "theme_park",
    "attraction", "viewpoint", "museum", "castle", "ruins", "archaeological_site", "monument",
    "memorial", "train_station", "station", "bus_station", "ferry_terminal", "pier", "marina",
    "harbour", "port", "bridge", "townhall", "government", "police", "fire_station",
    "prison", "university_campus", "racetrack", "camp_site", "resort", "quarry", "landfill",
}
SKIP_PLACE_KINDS = {"country", "ocean", "sea", "marine"}
PLACE_ORDER = {"region": 0, "county": 1, "city": 2, "town": 3, "locality": 4, "suburb": 5,
               "village": 6, "neighbourhood": 7, "hamlet": 8}


def _varint(data, j):
    v = s = 0
    while True:
        b = data[j]; j += 1
        v |= (b & 0x7F) << s; s += 7
        if b < 0x80:
            return v, j


def _skip(data, i, wt):
    if wt == 0:
        return _varint(data, i)[1]
    if wt == 1:
        return i + 8
    if wt == 2:
        ln, j = _varint(data, i); return j + ln
    if wt == 5:
        return i + 4
    raise ValueError("bad wire type")


def _layer_name(body):
    i = 0
    while i < len(body):
        key, i = _varint(body, i)
        if key == 0x0A:
            ln, j = _varint(body, i); return body[j:j + ln]
        i = _skip(body, i, key & 7)
    return b""


def only_layers(data):
    """Keep only the wanted layers (vector tile field 3) so decoding skips buildings, roads..."""
    out, i = [], 0
    while i < len(data):
        s = i
        key, i = _varint(data, i)
        e = _skip(data, i, key & 7)
        if key == 0x1A:
            ln, j = _varint(data, i)
            if _layer_name(data[j:j + ln]) in LAYERS:
                out.append(data[s:e])
        i = e
    return b"".join(out)


def first_xy(geom):
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Point":
        return c
    if t == "MultiPoint":
        return c[0]
    if t == "LineString":
        return c[len(c) // 2]
    if t == "Polygon":
        r = c[0]; return [sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)]
    if t in ("MultiPolygon", "MultiLineString"):
        return first_xy({"type": t[5:], "coordinates": c[0]})
    return None


def work(item):
    (z, x, y), data, gz = item
    if gz:
        data = gzip.decompress(data)
    data = only_layers(data)
    if not data:
        return []
    tile = mapbox_vector_tile.decode(data, default_options={"y_coord_down": True})
    out, n = [], 2 ** z
    for lname, lay in tile.items():
        ext = lay.get("extent", 4096)
        for f in lay.get("features", []):
            p = f.get("properties", {})
            name = p.get("name:th") or p.get("name") or p.get("name:en")
            if not name:
                continue
            kind = str(p.get("kind_detail") if lname == "places" and p.get("kind") == "locality"
                       and p.get("kind_detail") else p.get("kind") or "")
            if lname == "places" and (kind in SKIP_PLACE_KINDS or p.get("kind") in SKIP_PLACE_KINDS):
                continue
            if lname == "pois" and kind not in POI_KINDS and str(p.get("kind_detail")) not in POI_KINDS:
                continue
            xy = first_xy(f.get("geometry") or {})
            if not xy or not (0 <= xy[0] < ext and 0 <= xy[1] < ext):
                continue  # point in the tile buffer: its own tile lists it
            lon = (x + xy[0] / ext) / n * 360 - 180
            lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + xy[1] / ext) / n))))
            en = p.get("name:en") or ""
            if en == name:
                en = ""
            rank = PLACE_ORDER.get(kind, 9) if lname == "places" else 20
            out.append((rank, -(p.get("population") or 0), str(name), str(en),
                        round(lat, 5), round(lon, 5), kind))
    return out


def main(src, dst):
    t0 = time.time()
    with open(src, "rb") as f:
        get = MmapSource(f)
        hdr = Reader(get).header()
        z = int(os.environ.get("PLACES_ZOOM") or hdr["max_zoom"])
        gz = hdr.get("tile_compression") in (2, "GZIP") or str(hdr.get("tile_compression")).endswith("GZIP")
        items = ((zxy, d, gz) for zxy, d in all_tiles(get) if zxy[0] == z)
        rows = []
        with Pool() as pool:
            for r in pool.imap_unordered(work, items, chunksize=64):
                rows.extend(r)
    seen, kinds, kidx, pts = set(), [], {}, []
    rows.sort()
    for rank, _, name, en, lat, lon, kind in rows:
        key = (name, kind, round(lat, 2), round(lon, 2))
        if key in seen:
            continue
        seen.add(key)
        if kind not in kidx:
            kidx[kind] = len(kinds); kinds.append(kind)
        pts.append([name, en, lat, lon, kidx[kind]])
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "built": time.strftime("%Y-%m-%d", time.gmtime()), "zoom": z,
                   "kinds": kinds, "p": pts}, f, ensure_ascii=False, separators=(",", ":"))
    count = {}
    for p in pts:
        count[kinds[p[4]]] = count.get(kinds[p[4]], 0) + 1
    print(f"places.json: {len(pts)} points, {os.path.getsize(dst) / 1e6:.1f} MB, z{z}, {time.time() - t0:.0f} s")
    print(" ".join(f"{k}:{v}" for k, v in sorted(count.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
