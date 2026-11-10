#!/usr/bin/env python3
"""Turn the AIP Thailand ENROUTE CHART - ICAO (one A0 PDF page, Lambert conformal) into a
Web-Mercator raster .pmtiles for AirNavFlow (white paper kept; the app can key it out).

Georeference comes from the chart itself: the lat/long labels on the frame edges
(pdftotext -bbox) give the meridian lines (straight, meeting at the cone apex) and the
parallel radii (circles round the apex) = first guess. The sheet is not a pure LCC (east side was
~3 NM off), so every 1 deg graticule crossing inside the frame is then located on the image and a
cubic (lat, lon) -> chart fit through them (~80 points, rms ~0.1 NM) is used. The whole sheet is kept; metadata "frame" = map frame outline [lon, lat] so the app can make
only the inside transparent (legends stay white).

usage: enroute_tiles.py ENROUTE.pdf out.pmtiles [--zmin 5] [--zmax 10]
needs: poppler-utils (pdftoppm, pdftotext), numpy, scipy, pillow, pmtiles
"""
import argparse, io, json, math, re, subprocess, sys, tempfile, os
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from pmtiles.writer import Writer
from pmtiles.tile import zxy_to_tileid, TileType, Compression

Image.MAX_IMAGE_PIXELS = None


def labels(pdf):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "bb.html")
        subprocess.run(["pdftotext", "-bbox", "-f", "1", "-l", "1", pdf, out], check=True, stderr=subprocess.DEVNULL)
        t = open(out, encoding="utf-8").read()
    pw, ph = map(float, re.search(r'<page width="([\d.]+)" height="([\d.]+)"', t).groups())
    mer, par = {}, {}
    for x0, y0, x1, y1, w in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(\d{1,3}°[NE])<', t):
        x0, y0, x1, y1 = map(float, (x0, y0, x1, y1))
        v, cx, cy = int(w[:-2]), (x0 + x1) / 2, (y0 + y1) / 2
        if w.endswith("E"):
            mer.setdefault(v, {})["top" if cy < ph / 2 else "bot"] = cx
        else:
            par.setdefault(v, {})["L" if cx < pw / 2 else "R"] = cy
    mer = {k: v for k, v in mer.items() if "top" in v and "bot" in v}
    par = {k: v for k, v in par.items() if "L" in v and "R" in v}
    if len(mer) < 2 or len(par) < 3:
        sys.exit("not enough lat/long labels on the frame")
    return pw, ph, mer, par


def find_frame(img):
    """two long vertical frame lines (> 75% of the height) -> [x0, y0, x1, y1] in image px"""
    g = np.asarray(img.convert("L")) < 160
    H, W = g.shape
    best = []
    for x in range(W):
        col = g[:, x]
        # longest run
        d = np.diff(np.concatenate(([0], col.astype(np.int8), [0])))
        s, e = np.where(d == 1)[0], np.where(d == -1)[0]
        if len(s):
            i = np.argmax(e - s)
            if e[i] - s[i] > 0.75 * H:
                best.append((x, s[i], e[i]))
    if len(best) < 2:
        sys.exit("map frame not found")
    L, R = best[0], best[-1]
    return L[0], min(L[1], R[1]), R[0], max(L[2], R[2])


def model(mer, par, frame_pt):
    FL, FT, FR, FB = frame_pt
    lines = {v: (np.array([d["top"], FT]), np.array([d["bot"], FB])) for v, d in mer.items()}
    # apex = least-squares intersection of all meridian lines
    A, b = [], []
    for p1, p2 in lines.values():
        n = np.array([-(p2 - p1)[1], (p2 - p1)[0]]); n /= np.linalg.norm(n)
        A.append(n); b.append(n @ p1)
    apex = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)[0]
    lons = sorted(lines)
    ang = [math.atan2(lines[v][1][0] - apex[0], lines[v][1][1] - apex[1]) for v in lons]
    th = np.polyfit(lons, ang, 1)                      # theta(lon), linear in LCC
    lats = sorted(par)
    rad = [(math.hypot(FL - apex[0], par[v]["L"] - apex[1]) + math.hypot(FR - apex[0], par[v]["R"] - apex[1])) / 2 for v in lats]
    rho = np.polyfit(lats, rad, min(3, len(lats) - 1))  # rho(lat)
    res = max(abs(np.polyval(rho, a) - r) for a, r in zip(lats, rad))
    print("apex", apex.round(1), "theta/deg", round(th[0], 6), "rho fit max err pt", round(res, 2))
    return apex, th, rho


def poly_terms(lat, lon, deg=3):
    a = (np.asarray(lat, float) - 13) / 8; b = (np.asarray(lon, float) - 101) / 6
    return np.stack([a ** i * b ** j for i in range(deg + 1) for j in range(deg + 1 - i)], -1)


def grid_fit(gimg, kk, frame_pt, lcc):
    """the sheet is not a pure LCC: find every 1 deg graticule crossing inside the frame (grey lines)
    near the LCC guess and fit a cubic (lat, lon) -> chart pt through them"""
    im = np.asarray(gimg).astype(int); r, g, b = im[..., 0], im[..., 1], im[..., 2]
    gray = (abs(r - g) < 12) & (abs(g - b) < 12) & (r > 110) & (r < 215)
    FL, FT, FR, FB = [v * kk for v in frame_pt]; W = 40
    pts = []
    for lat in range(-5, 35):
        for lon in range(85, 120):
            x, y = lcc(lat, lon); x = int(x * kk); y = int(y * kk)
            if x < FL + W or x > FR - W or y < FT + W or y > FB - W:
                continue
            win = gray[y - W:y + W, x - W:x + W]; cs = win.sum(0); rs = win.sum(1)
            cx, cy = int(np.argmax(cs)), int(np.argmax(rs))
            if cs[cx] >= W * 1.2 and rs[cy] >= W * 1.2:
                pts.append((lat, lon, (x - W + cx) / kk, (y - W + cy) / kk))
    if len(pts) < 20:
        return None
    P = np.array(pts, float); keep = np.ones(len(P), bool)
    for _ in range(3):
        T = poly_terms(P[keep, 0], P[keep, 1])
        cx = np.linalg.lstsq(T, P[keep, 2], rcond=None)[0]; cy = np.linalg.lstsq(T, P[keep, 3], rcond=None)[0]
        T = poly_terms(P[:, 0], P[:, 1]); e = np.hypot(T @ cx - P[:, 2], T @ cy - P[:, 3])
        keep = e < max(1.5, 3 * np.median(e))
    print("graticule crossings", len(P), "used", int(keep.sum()), "rms pt", round(float(np.sqrt((e[keep] ** 2).mean())), 2), "max pt", round(float(e[keep].max()), 2))
    return cx, cy


def merc_tile_latlon(z, x, y, n=256):
    s = (np.arange(n) + 0.5) / n
    X = (x + s[None, :]) / 2 ** z
    Y = (y + s[:, None]) / 2 ** z
    lon = X * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * Y))))
    return np.broadcast_to(lat, (n, n)), np.broadcast_to(lon, (n, n))


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("out")
    ap.add_argument("--zmin", type=int, default=5); ap.add_argument("--zmax", type=int, default=10)
    ap.add_argument("--dpi", type=int, default=0, help="render dpi (default: enough for zmax)")
    ap.add_argument("--quality", type=int, default=82)
    a = ap.parse_args()

    pw, ph, mer, par = labels(a.pdf)
    # pt per degree latitude on the chart vs px per degree at zmax (~13N) -> dpi
    lats = sorted(par); ptdeg = abs(par[lats[-1]]["L"] - par[lats[0]]["L"]) / (lats[-1] - lats[0])
    need = (2 ** a.zmax * 256 / 360) / math.cos(math.radians(13)) / ptdeg
    dpi = a.dpi or int(math.ceil(need * 72 * 1.05))
    print("render dpi", dpi)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", "1", "-l", "1", "-png", "-singlefile", a.pdf, os.path.join(d, "p")], check=True, stderr=subprocess.DEVNULL)
        img = Image.open(os.path.join(d, "p.png")).convert("RGB"); img.load()
    def frame_and_snap(im, kk):
        f0, g0, f1, g1 = find_frame(im)
        # labels sit beside their line: snap each to the graticule line drawn just inside the frame
        gray = np.asarray(im.convert("L"))
        def snap(arr, c, span):
            lo = max(0, int(c) - span); seg = arr[lo:int(c) + span + 1]
            return lo + int(np.argmin(seg)) if len(seg) and seg.min() < 200 else c
        sp = int(round(12 * kk))
        for v, d in mer.items():
            d["top"] = snap(gray[g0 + 6, :], d["top"] * kk, sp) / kk
            d["bot"] = snap(gray[g1 - 6, :], d["bot"] * kk, sp) / kk
        for v, d in par.items():
            d["L"] = snap(gray[:, f0 + 6], d["L"] * kk, sp) / kk
            d["R"] = snap(gray[:, f1 - 6], d["R"] * kk, sp) / kk
        return f0 / kk, g0 / kk, f1 / kk, g1 / kk
    # georeference on a fixed 140 dpi render (same result whatever the output detail)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", "140", "-f", "1", "-l", "1", "-png", "-singlefile", a.pdf, os.path.join(d, "g")], check=True, stderr=subprocess.DEVNULL)
        gimg = Image.open(os.path.join(d, "g.png")).convert("RGB"); gimg.load()
        frame_pt = frame_and_snap(gimg, 140 / 72.0)
    k = dpi / 72.0
    fx0, fy0, fx1, fy1 = [int(round(v * k)) for v in frame_pt]
    print("frame px", fx0, fy0, fx1, fy1, "image", img.size)
    print("mer", {v: (round(d["top"], 1), round(d["bot"], 1)) for v, d in sorted(mer.items())})
    print("par", {v: (round(d["L"], 1), round(d["R"], 1)) for v, d in sorted(par.items())})
    apex, th, rho = model(mer, par, frame_pt)
    def lcc(lat, lon):  # chart pt
        r = np.polyval(rho, lat); t = np.polyval(th, lon)
        return apex[0] + r * np.sin(t), apex[1] + r * np.cos(t)
    gf = grid_fit(gimg, 140 / 72.0, frame_pt, lcc); del gimg

    # whole sheet kept (legends stay white); the app keys white -> transparent inside the frame only (metadata "frame")
    rgb = np.asarray(img); del img
    PH, PW = rgb.shape[:2]
    al = np.full(rgb.shape[:2], 255, np.uint8)
    rgba = np.dstack([rgb, al]); del rgb, al

    def chart_px(lat, lon):
        if gf is None:
            X, Y = lcc(lat, lon)
        else:
            T = poly_terms(lat, lon); X, Y = T @ gf[0], T @ gf[1]
        return X * k, Y * k

    lat_s = np.linspace(-20, 50, 7001); rho_s = np.polyval(rho, lat_s); o = np.argsort(rho_s)
    def px_latlon(x, y):  # chart px -> (lon, lat), inverse of chart_px (LCC guess + Newton)
        u = x / k - apex[0]; v = y / k - apex[1]
        lo, la = (math.atan2(u, v) - th[1]) / th[0], float(np.interp(math.hypot(u, v), rho_s[o], lat_s[o]))
        for _ in range(8):
            X, Y = chart_px(la, lo); h = 1e-4
            Xa, Ya = chart_px(la + h, lo); Xo, Yo = chart_px(la, lo + h)
            J = np.array([[(Xa - X) / h, (Xo - X) / h], [(Ya - Y) / h, (Yo - Y) / h]], float)
            dla, dlo = np.linalg.solve(J, [x - X, y - Y]); la += dla; lo += dlo
        return float(lo), float(la)
    # frame outline in lon/lat (edges are straight on the chart, curved on the web map)
    frame = []
    for (xa, ya), (xb, yb) in [((fx0, fy0), (fx1, fy0)), ((fx1, fy0), (fx1, fy1)), ((fx1, fy1), (fx0, fy1)), ((fx0, fy1), (fx0, fy0))]:
        for t in np.linspace(0, 1, 24, endpoint=False):
            lo, la = px_latlon(xa + (xb - xa) * t, ya + (yb - ya) * t); frame.append([round(lo, 5), round(la, 5)])
    # bbox of the whole sheet in lat/lon (sample its edge)
    lat_g, lon_g = np.meshgrid(np.linspace(-10, 40, 501), np.linspace(80, 125, 451))
    X, Y = chart_px(lat_g, lon_g)
    inside = (X >= 0) & (X <= PW) & (Y >= 0) & (Y <= PH)
    W_, S_, E_, N_ = lon_g[inside].min() - .1, lat_g[inside].min() - .1, lon_g[inside].max() + .1, lat_g[inside].max() + .1
    print("bounds", round(W_, 2), round(S_, 2), round(E_, 2), round(N_, 2))

    levels = {}  # zoom -> (array, scale) pyramid so low zooms are not aliased
    base_scale = 1.0
    cur = rgba
    tiles = []
    for z in range(a.zmax, a.zmin - 1, -1):
        sc = 2 ** (a.zmax - z)
        if sc > 1:
            h, w = cur.shape[:2]
            cur = np.asarray(Image.fromarray(cur).resize((max(1, w // 2), max(1, h // 2)), Image.LANCZOS))
        f = 1 / sc
        chans = [cur[..., c].astype(np.float32) for c in range(4)]
        x0, y1 = lonlat_to_tile(W_, S_, z); x1, y0 = lonlat_to_tile(E_, N_, z)
        cnt = 0
        for ty in range(int(y0), int(y1) + 1):
            for tx in range(int(x0), int(x1) + 1):
                lat, lon = merc_tile_latlon(z, tx, ty)
                X, Y = chart_px(lat, lon)
                X = X * f; Y = Y * f
                if X.max() < 0 or Y.max() < 0 or X.min() > cur.shape[1] or Y.min() > cur.shape[0]:
                    continue
                out = np.dstack([map_coordinates(c, [Y, X], order=1, mode="constant", cval=0) for c in chans])
                if out[..., 3].max() < 8:
                    continue
                b = io.BytesIO()
                Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA").save(b, "WEBP", quality=a.quality, method=4)
                tiles.append((zxy_to_tileid(z, tx, ty), b.getvalue())); cnt += 1
        print("z", z, "tiles", cnt)

    tiles.sort()
    with open(a.out, "wb") as fo:
        w = Writer(fo)
        for tid, data in tiles:
            w.write_tile(tid, data)
        w.finalize(
            {"tile_type": TileType.WEBP, "tile_compression": Compression.NONE,
             "min_zoom": a.zmin, "max_zoom": a.zmax,
             "min_lon_e7": int(W_ * 1e7), "min_lat_e7": int(S_ * 1e7), "max_lon_e7": int(E_ * 1e7), "max_lat_e7": int(N_ * 1e7),
             "center_zoom": 6, "center_lon_e7": int((W_ + E_) / 2 * 1e7), "center_lat_e7": int((S_ + N_) / 2 * 1e7)},
            {"name": "ENROUTE CHART - ICAO (AIP Thailand)", "attribution": "AIP Thailand / CAAT", "frame": frame})
    print("wrote", a.out, round(os.path.getsize(a.out) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
