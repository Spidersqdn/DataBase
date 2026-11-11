#!/usr/bin/env python3
"""Write <dir>/index.json for the AirNavFlow CHART box: every PNG/JPG/WEBP/PDF under <dir>
(sub-folders kept), its size, PDF page count and a short label per page (SID / STAR / ILS Rwy 21L ...).
Usage: python3 tools/charts_index.py AirNavFlow/charts"""
import json, os, re, sys

try:
    import pypdf
except ImportError:  # labels are a nice-to-have: list the files anyway
    pypdf = None

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
            if f.lower().endswith('.pdf') and pypdf:
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
    print(len(out), 'charts,', sum(e['bytes'] for e in out) // 1048576, 'MB')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'AirNavFlow/charts')
