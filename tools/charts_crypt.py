#!/usr/bin/env python3
"""Password protection for AirNavFlow built-in charts (SPD 26 NOV 2026, thread "Login").

The repo is public, so chart files are stored and served only encrypted (AES-256-GCM).
Key = PBKDF2-SHA256(password, salt, iter). Password = repo secret CHART_KEY (env CHART_KEY).
The app derives the same key from the password the user types, checks it against enc.json 'check'.

File format (.enc): b'ANF1' + 12-byte IV + ciphertext+tag.
<dir>/enc.json (committed, not secret): {"v":1,"iter":N,"salt":b64,"check":b64}

Usage (workflow):
  charts_crypt.py lock <dir>            encrypt every plain chart file in <dir> to <file>.enc, delete the plain file
  charts_crypt.py unlock <dir> <out>    decrypt every .enc into <out> (same sub-folders) for charts_index.py
  charts_crypt.py index <plain> <dir>   <plain>/index.json -> <dir>/index.json with 'u' (.enc path), enc sizes, 'enc'
"""
import base64, hashlib, json, os, re, sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b'ANF1'
CHECK = b'AirNavFlow CHART OK'
ITER = 310000
PLAIN = re.compile(r'\.(png|jpe?g|webp|pdf)$', re.I)
b64 = lambda b: base64.b64encode(b).decode()


def key_from(meta):
    pw = os.environ.get('CHART_KEY', '')
    if not pw:
        sys.exit('CHART_KEY secret is not set (DataBase > Settings > Secrets and variables > Actions)')
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=base64.b64decode(meta['salt']), iterations=meta['iter'])
    return AESGCM(kdf.derive(pw.encode('utf-8')))


def seal(aes, data):
    iv = os.urandom(12)
    return MAGIC + iv + aes.encrypt(iv, data, None)


def opn(aes, blob):
    if blob[:4] != MAGIC:
        raise ValueError('not an ANF1 file')
    return aes.decrypt(blob[4:16], blob[16:], None)


def load_meta(root):
    p = os.path.join(root, 'enc.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as fh:
            meta = json.load(fh)
        aes = key_from(meta)
        try:
            opn(aes, base64.b64decode(meta['check']))
        except Exception:
            sys.exit('CHART_KEY does not match enc.json (password changed?). Old files need the old password.')
        return meta, aes
    meta = {'v': 1, 'iter': ITER, 'salt': b64(os.urandom(16))}
    aes = key_from(meta)
    meta['check'] = b64(seal(aes, CHECK))
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh)
    print('new enc.json')
    return meta, aes


def walk(root, rx):
    for d, _, fs in os.walk(root):
        for f in sorted(fs):
            if rx.search(f):
                yield os.path.join(d, f)


def lock(root):
    _, aes = load_meta(root)
    n = 0
    for p in walk(root, PLAIN):
        with open(p, 'rb') as fh:
            data = fh.read()
        with open(p + '.enc', 'wb') as fh:
            fh.write(seal(aes, data))
        os.remove(p)
        n += 1
        print('locked', os.path.relpath(p, root))
    print(n, 'file(s) encrypted')


def unlock(root, out):
    _, aes = load_meta(root)
    for p in walk(root, re.compile(r'\.enc$')):
        rel = os.path.relpath(p, root)[:-4]
        q = os.path.join(out, rel)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        with open(p, 'rb') as fh:
            data = opn(aes, fh.read())
        with open(q, 'wb') as fh:
            fh.write(data)


def index(plain, root):
    with open(os.path.join(root, 'enc.json'), encoding='utf-8') as fh:
        meta = json.load(fh)
    with open(os.path.join(plain, 'index.json'), encoding='utf-8') as fh:
        j = json.load(fh)
    for e in j['charts']:
        e['u'] = e['f'] + '.enc'
        e['bytes'] = os.path.getsize(os.path.join(root, e['u']))
    j['enc'] = {k: meta[k] for k in ('v', 'iter', 'salt', 'check')}
    # fast check for the app's login box (type the right password = logged in at once, like FalCon2CP's PASS_HASH;
    # same SHA-256 FalCon2CP already publishes in its config.js, so nothing new is exposed)
    pw = os.environ.get('CHART_KEY', '')
    if pw:
        j['enc']['ph'] = hashlib.sha256(pw.encode('utf-8')).hexdigest()
    with open(os.path.join(root, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump(j, fh, ensure_ascii=False, separators=(',', ':'))
    print(len(j['charts']), 'charts in index (encrypted)')


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    {'lock': lock, 'unlock': unlock, 'index': index}[cmd](*args)
