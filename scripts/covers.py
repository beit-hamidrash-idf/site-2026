"""Render the first page of each featured ("חדש") file as a JPEG cover for its card.

Usage: python scripts/covers.py data-new.json _site/covers
Adds "img": "covers/<id>.jpg" to every entry whose cover was made, and rewrites data-new.json.
A file that cannot be downloaded or rendered simply keeps a card without a picture."""
import json, os, subprocess, sys, tempfile, urllib.request

new_path, out_dir = sys.argv[1], sys.argv[2]
URL = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'
items = json.load(open(new_path, encoding='utf-8'))
os.makedirs(out_dir, exist_ok=True)

def fetch(fid):
    for _ in range(3):
        try:
            return urllib.request.urlopen(URL.format(fid), timeout=120).read()
        except Exception as e:
            err = e
    print('download failed', fid, err, file=sys.stderr)
    return b''

def first_page(data, fid):
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'f')
        open(src, 'wb').write(data)
        if data[:2] == b'PK':  # Word file: convert to PDF first, if LibreOffice is available
            r = subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, src],
                               capture_output=True, timeout=180)
            src = os.path.join(tmp, 'f.pdf')
            if not os.path.exists(src): return False
        elif data[:4] != b'%PDF':
            return False
        base = os.path.join(out_dir, fid)
        r = subprocess.run(['pdftoppm', '-f', '1', '-l', '1', '-singlefile', '-jpeg', '-jpegopt', 'quality=82',
                            '-scale-to-x', '640', '-scale-to-y', '-1', src, base], capture_output=True, timeout=120)
        return r.returncode == 0 and os.path.exists(base + '.jpg')

for d in items:
    fid = d['f'].get('pdf') or d['f'].get('word')
    data = fetch(fid) if fid else b''
    try:
        ok = bool(data) and first_page(data, fid)
    except Exception as e:
        print('cover failed', fid, e, file=sys.stderr); ok = False
    if ok: d['img'] = f'covers/{fid}.jpg'
    print('cover', 'ok ' if ok else 'none', d['t'], file=sys.stderr)

json.dump(items, open(new_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
