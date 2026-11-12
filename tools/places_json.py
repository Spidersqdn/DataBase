#!/usr/bin/env python3
"""Write FalCon2CP/places.json for the FalCon2CP place-search box, from the AirNavFlow repo:
- airports: the AP list in AirNavFlow index.html (ICAO, IATA, name, province, lat, lon, elev ft, note)
- Army airfields / units / camps: AirNavFlow data/สนามบิน ทบ.txt (MGRS or "lat, lon")
Output: {"src":..., "built":..., "p":[[id, name, sub, lat, lon, elev, kind], ...]}
kind: AD (airport) / ARMY (สนามบิน) / UNIT (หน่วยบิน) / CAMP (ค่ายทหาร)
Usage: python3 tools/places_json.py <AirNavFlow checkout> <out.json>"""
import ast, datetime, json, os, re, sys

import mgrs  # pip install mgrs


def dms(d, m, s=0):
    return d + m / 60 + s / 3600


def airports(html):
    m = re.search(r'^var AP=\[(.*?)^\];', html, re.S | re.M)
    if not m:
        raise SystemExit('AP list not found in AirNavFlow index.html')
    body = re.sub(r'/\*.*?\*/', '', m.group(1), flags=re.S)
    body = re.sub(r'dms\(([^)]*)\)', lambda g: repr(dms(*map(float, g.group(1).split(',')))), body)
    out = []
    for a in ast.literal_eval('[' + body + ']'):
        icao, iata, name, prov, lat, lon, el = a[:7]
        out.append([icao, name, prov + (' · ' + iata if iata else ''), round(lat, 6), round(lon, 6), el, 'AD'])
    return out


def army(txt):
    conv, out = mgrs.MGRS(), []
    for line in txt.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        f = [x.strip() for x in line.split('|')] + ['', '', '', '']
        dd = re.match(r'^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$', f[2])
        try:
            lat, lon = (float(dd[1]), float(dd[2])) if dd else conv.toLatLon(f[2].replace(' ', '').upper())
        except Exception:
            print('skip (bad coord):', line)
            continue
        kind = 'CAMP' if 'ค่าย' in f[0] else 'UNIT' if 'หน่วย' in f[0] else 'ARMY'
        out.append(['', f[1], f[3], round(lat, 6), round(lon, 6), None, kind])
    return out


def main(src, dst):
    html = open(os.path.join(src, 'index.html'), encoding='utf-8').read()
    p = airports(html)
    f = os.path.join(src, 'data', 'สนามบิน ทบ.txt')
    if os.path.exists(f):
        p += army(open(f, encoding='utf-8').read())
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    doc = {'src': 'AirNavFlow', 'built': datetime.date.today().isoformat(), 'p': p}
    with open(dst, 'w', encoding='utf-8') as o:
        json.dump(doc, o, ensure_ascii=False, separators=(',', ':'))
    print(f'{dst}: {len(p)} places')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
