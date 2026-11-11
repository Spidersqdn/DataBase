#!/usr/bin/env python3
"""Write <dir>/index.json for the AirNavFlow CHART box: every PNG/JPG/WEBP/PDF under <dir>
(sub-folders kept), its size, PDF page count, a short label per page (SID / STAR / ILS Rwy 21L ...)
'nts': for pages without a grid fit, one known point [x, y, lat, lon] or null (the app then uses the
runway midpoint), and 'geo': per page the preset georeference found from the lat/long grid labels (tools/chart_georef.py),
as [[x, y, lat, lon], ...] in pixels of the app's render (long side 2600 px), or null.
Usage: python3 tools/charts_index.py AirNavFlow/charts"""
import json, os, re, sys

try:
    import pymupdf  # labels + grid georeference
except ImportError:
    pymupdf = None
try:
    import pypdf  # labels only
except ImportError:  # labels are a nice-to-have: list the files anyway
    pypdf = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chart_georef import page_anchor, page_georef  # noqa: E402


def page_geo(page):
    """preset control points in px of the app render (same scale as chartPdfToPng)."""
    g = page_georef(page)
    if not g:
        return None
    W, H = page.rect.width, page.rect.height
    sc = min(6, 2600 / max(W, H))
    return [[round(u * W * sc, 1), round(v * H * sc, 1), la, lo] for u, v, la, lo in g]


def page_nts(page, geo):
    """page without a grid fit: one known point (single lat + long label) for the NOT TO SCALE overlay, px."""
    if geo:
        return None
    a = page_anchor(page)
    if not a:
        return None
    W, H = page.rect.width, page.rect.height
    sc = min(6, 2600 / max(W, H))
    return [round(a[0] * W * sc, 1), round(a[1] * H * sc, 1), a[2], a[3]]

EXT = re.compile(r'\.(png|jpe?g|webp|pdf)$', re.I)
APCH = re.compile(r'\b((?:ILS|LOC|RNP|RNAV|GPS|VOR|NDB|DME|TACAN|VISUAL)(?:\s*(?:or|/)\s*(?:LOC|DME|ILS))?(?:\s+[A-Z])?\s+Rwy\s*\d{2}[LRC]?)', re.I)
SID = re.compile(r'\b([A-Z]{5}\s+\d[A-Z])\b')


def page_label(text):
    t = re.sub(r'[ \t]+', ' ', text or '')
    m = APCH.search(t)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).replace('Rwy', 'RWY')
    up = t.upper()
    kind = 'RNAV SID' if 'RNAV SID' in up else 'RNAV STAR' if 'RNAV STAR' in up else \
        'SID' if re.search(r'\bSID\b', up) else 'STAR' if re.search(r'\bSTAR\b', up) else ''
    if kind:
        names = []
        for n in SID.findall(t):
            if n not in names:
                names.append(n)
        return (kind + ' ' + ' '.join(names[:2])).strip()
    if 'TAXI' in up or 'PARKING' in up or 'APRON' in up:
        return 'AIRPORT / TAXI'
    if 'AIRPORT' in up or 'ARP' in up:
        return 'AIRPORT'
    return ''


def main(root):
    out = []
    for d, _, fs in os.walk(root):
        for f in sorted(fs):
            if not EXT.search(f):
                continue
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            e = {'f': rel, 'bytes': os.path.getsize(p)}
            if f.lower().endswith('.pdf') and pymupdf:
                try:
                    doc = pymupdf.open(p)
                    e['pages'] = len(doc)
                    e['labels'] = [page_label(pg.get_text()) for pg in doc]
                    e['geo'] = [page_geo(pg) for pg in doc]
                    e['nts'] = [page_nts(pg, g) for pg, g in zip(doc, e['geo'])]
                except Exception as ex:
                    print('warn', rel, ex, file=sys.stderr)
            elif f.lower().endswith('.pdf') and pypdf:
                try:
                    r = pypdf.PdfReader(p)
                    e['pages'] = len(r.pages)
                    e['labels'] = [page_label(pg.extract_text()) for pg in r.pages]
                except Exception as ex:  # unreadable PDF: still listed
                    print('warn', rel, ex, file=sys.stderr)
            out.append(e)
    out.sort(key=lambda e: e['f'])
    with open(os.path.join(root, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump({'charts': out}, fh, ensure_ascii=False, separators=(',', ':'))
    geo = sum(1 for e in out for g in e.get('geo') or [] if g)
    pages = sum(e.get('pages', 1) for e in out)
    print(len(out), 'charts,', sum(e['bytes'] for e in out) // 1048576, 'MB,', geo, '/', pages, 'pages georeferenced')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'AirNavFlow/charts')
