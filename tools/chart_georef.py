#!/usr/bin/env python3
"""Find the lat/long grid of a chart page from its labels ("14-00" = 14°00', "100-30" = 100°30')
and return control points [[u, v, lat, lon], ...] (u, v = fraction of page width / height).
Labels sit on the grid line or beside its tick mark: each label is snapped to the nearest
line segment across it, then lat(y) and lon(x) are fitted as straight lines (north-up chart).
Returns None when the page has no usable grid (NOT TO SCALE charts, text pages)."""
import math
import re

LBL = re.compile(r'^(\d{2,3})-(\d{2}(?:\.\d)?)$')


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


def _lsq(pairs):
    """least squares val = a*pos + b"""
    n = len(pairs)
    mx = sum(p for p, _ in pairs) / n
    my = sum(v for _, v in pairs) / n
    sxx = sum((p - mx) ** 2 for p, _ in pairs)
    if sxx < 1e-6:
        return None
    a = sum((p - mx) * (v - my) for p, v in pairs) / sxx
    return a, my - a * mx


def _cands(pairs, tol=7.0):
    """grid fits val = a*pos + b from every pair of different labels; labels within tol pt of the
    line are inliers (a page may hold an inset with its own grid, or labels beside a tick).
    Returns [(score, a, b), ...] best first, one per inlier set."""
    out, seen = [], set()
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            (p1, v1), (p2, v2) = pairs[i], pairs[j]
            if v1 == v2 or abs(p1 - p2) < 10:
                continue
            a = (v2 - v1) / (p2 - p1)
            b = v1 - a * p1
            inl = tuple(k for k, (p, v) in enumerate(pairs) if abs((v - b) / a - p) <= tol)
            if inl in seen or len({pairs[k][1] for k in inl}) < 2:
                continue
            seen.add(inl)
            f = _lsq([pairs[k] for k in inl])
            if f:  # score = page span covered by the labels: the main diagram wins over an inset
                ps = [pairs[k][0] for k in inl]
                out.append((max(ps) - min(ps) + len(inl), f[0], f[1]))
    out.sort(key=lambda c: -c[0])
    return out[:12]


def _merge(pairs, gap=25):
    """same label printed on both sides of its tick (or repeated on one line): one point at the mean."""
    out = []
    for p, v in sorted(pairs, key=lambda q: (q[1], q[0])):
        if out and out[-1][1] == v and p - out[-1][2] <= gap:
            g = out[-1]
            g[0].append(p)
            g[2] = p
        else:
            out.append([[p], v, p])
    return [(sum(g[0]) / len(g[0]), g[1]) for g in out]


def page_georef(page):
    W, H = page.rect.width, page.rect.height
    hs, vs = _segments(page)
    lat, lon = [], []
    for x0, y0, x1, y1, t, *_ in page.get_text('words'):
        m = LBL.match(t)
        if not m:
            continue
        deg, mn = int(m.group(1)), float(m.group(2))
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
    lat, lon = _merge(lat), _merge(lon)
    latc = sorted(v for _, v in lat)[len(lat) // 2]
    cos = math.cos(math.radians(latc))
    cy, cx = _cands(lat), _cands(lon)
    best = None
    for ny, ay, by in cy:
        for nx, ax, bx in cx:
            if ay >= 0 or ax <= 0:        # north must be up, east to the right
                continue
            k = (1 / -ay) / (1 / ax / cos)  # conformal: 1' lat = 1' lon * cos(lat) on the page
            if 0.85 < k < 1.15 and (best is None or ny + nx > best[0]):
                best = (ny + nx, ay, by, ax, bx)
    if best:
        _, ay, by, ax, bx = best
    else:
        # only one label value on an axis: take its scale from the other axis
        if cy and not cx and len({v for _, v in lon}) == 1 and cy[0][1] < 0:
            ay, by = cy[0][1], cy[0][2]
            ax = -ay / cos
            bx = lon[0][1] - ax * lon[0][0]
        elif cx and not cy and len({v for _, v in lat}) == 1 and cx[0][1] > 0:
            ax, bx = cx[0][1], cx[0][2]
            ay = -ax * cos
            by = lat[0][1] - ay * lat[0][0]
        else:
            return None
    pts = []
    for u, v in ((0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
        x, y = u * W, v * H
        pts.append([round(u, 4), round(v, 4), round(ay * y + by, 6), round(ax * x + bx, 6)])
    return pts


def page_anchor(page):
    """NOT TO SCALE pages: one point whose lat/long is known from a single lat label and a single
    long label (crossing of the two grid lines). Returns [u, v, lat, lon] or None."""
    hs, vs = _segments(page)
    lat, lon = {}, {}
    for x0, y0, x1, y1, t, *_ in page.get_text('words'):
        m = LBL.match(t)
        if not m or float(m.group(2)) >= 60:
            continue
        deg, val = int(m.group(1)), int(m.group(1)) + float(m.group(2)) / 60
        if 0 <= deg <= 30 and len(m.group(1)) == 2:
            lat.setdefault(val, _snap((y0 + y1) / 2, x0, x1, hs, 6, 14))
        elif 90 <= deg <= 120:
            lon.setdefault(val, _snap((x0 + x1) / 2, y0, y1, vs, 8, 14))
    if not lat or not lon:
        return None
    la, y = sorted(lat.items())[0]
    lo, x = sorted(lon.items())[0]
    return [round(x / page.rect.width, 4), round(y / page.rect.height, 4), round(la, 6), round(lo, 6)]
