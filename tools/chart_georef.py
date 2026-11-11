#!/usr/bin/env python3
"""Find the lat/long grid of a chart page from its labels ("14-00" = 14°00', "100-30" = 100°30')
and return control points [[u, v, lat, lon], ...] (u, v = fraction of page width / height).
Labels sit on the grid line or beside its tick mark: each label is snapped to the nearest
line segment across it, then lat(y) and lon(x) are fitted as straight lines (north-up chart).
Returns None when the page has no usable grid (NOT TO SCALE charts, text pages)."""
import math
import re

LBL = re.compile(r'^(\d{2,3})-(\d{2})$')


def _segments(page):
    hs, vs = [], []
    for dr in page.get_drawings():
        for it in dr['items']:
            if it[0] != 'l':
                continue
            a, b = it[1], it[2]
            if abs(a.y - b.y) < 0.3 and abs(a.x - b.x) >= 3:
                hs.append((a.y, min(a.x, b.x), max(a.x, b.x)))
            elif abs(a.x - b.x) < 0.3 and abs(a.y - b.y) >= 3:
                vs.append((a.x, min(a.y, b.y), max(a.y, b.y)))
    return hs, vs


def _snap(c, lo, hi, segs, tol, reach):
    """c = label centre across the line, lo..hi = label extent along it; nearest segment within tol."""
    best = None
    for pos, s0, s1 in segs:
        d = abs(pos - c)
        if d <= tol and s0 <= hi + reach and s1 >= lo - reach and (best is None or d < best[0]):
            best = (d, pos)
    return best[1] if best else c


def _fit(pairs):
    """least squares val = a*pos + b; drops the worst outlier while it is clearly off."""
    pairs = list(pairs)
    while len(pairs) >= 2:
        n = len(pairs)
        mx = sum(p for p, _ in pairs) / n
        my = sum(v for _, v in pairs) / n
        sxx = sum((p - mx) ** 2 for p, _ in pairs)
        if sxx < 1e-6:
            return None
        a = sum((p - mx) * (v - my) for p, v in pairs) / sxx
        b = my - a * mx
        res = [abs(a * p + b - v) for p, v in pairs]
        worst = max(range(n), key=lambda i: res[i])
        span = max(v for _, v in pairs) - min(v for _, v in pairs)
        if res[worst] > max(0.02 * span, 0.05 / 60) and n > 2:
            pairs.pop(worst)
            continue
        if len({round(v, 6) for _, v in pairs}) < 2 or res[worst] > 0.05 * span:
            return None
        return a, b
    return None


def page_georef(page):
    W, H = page.rect.width, page.rect.height
    hs, vs = _segments(page)
    lat, lon = [], []
    for x0, y0, x1, y1, t, *_ in page.get_text('words'):
        m = LBL.match(t)
        if not m:
            continue
        deg, mn = int(m.group(1)), int(m.group(2))
        if mn >= 60:
            continue
        val = deg + mn / 60
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if 0 <= deg <= 30 and len(m.group(1)) == 2:      # latitude label -> horizontal line
            lat.append((_snap(cy, x0, x1, hs, 6, 14), val))
        elif 90 <= deg <= 120:                            # longitude label -> vertical line
            lon.append((_snap(cx, y0, y1, vs, 8, 14), val))
    if not lat or not lon:
        return None
    latc = (min(v for _, v in lat) + max(v for _, v in lat)) / 2
    cos = math.cos(math.radians(latc))
    fy, fx = _fit(lat), _fit(lon)
    # only one label on an axis: take its scale from the other axis (conformal chart: dlat = dlon * cos(lat))
    if fy and not fx and len({v for _, v in lon}) == 1:
        ax = -fy[0] / cos
        fx = (ax, lon[0][1] - ax * lon[0][0])
    elif fx and not fy and len({v for _, v in lat}) == 1:
        ay = -fx[0] * cos
        fy = (ay, lat[0][1] - ay * lat[0][0])
    if not fy or not fx:
        return None
    (ay, by), (ax, bx) = fy, fx
    if ay >= 0 or ax <= 0:            # north must be up, east to the right
        return None
    # scale check: 1' lat (NM) vs 1' lon * cos(lat) should match within 15 % on a conformal chart
    k = (1 / -ay) / (1 / ax / cos)
    if not 0.85 < k < 1.15:
        return None
    pts = []
    for u, v in ((0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
        x, y = u * W, v * H
        pts.append([round(u, 4), round(v, 4), round(ay * y + by, 6), round(ax * x + bx, 6)])
    return pts
