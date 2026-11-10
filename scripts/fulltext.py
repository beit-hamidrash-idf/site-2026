"""Download every document from Drive and extract its text, for searching inside the booklets.

Writes a JSON list aligned with the documents list: one cleaned text string per document ("" when
no text could be extracted, e.g. scanned pages)."""
import io, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile
import concurrent.futures as cf

docs = json.load(open(sys.argv[1], encoding='utf-8'))
URL = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'
STRIP = re.compile(r'[֑-ׇ​-‏‪-‮⁦-⁩﻿­]')

def fetch(fid):
    for _ in range(3):
        try:
            return urllib.request.urlopen(URL.format(fid), timeout=120).read()
        except Exception as e:
            err = e
    print('download failed', fid, err, file=sys.stderr)
    return b''

def from_docx(data):
    import docx
    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts.extend(c.text for c in row.cells)
    return '\n'.join(parts)

def run(cmd, data, suffix):
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(data); f.flush()
        r = subprocess.run(cmd + [f.name] + (['-'] if cmd[0] == 'pdftotext' else []),
                           capture_output=True, timeout=300)
        return r.stdout.decode('utf-8', 'replace')

def extract(data):
    if data[:4] == b'%PDF':
        return run(['pdftotext', '-enc', 'UTF-8'], data, '.pdf')
    if data[:2] == b'PK':
        try:
            return from_docx(data)
        except (zipfile.BadZipFile, KeyError, ValueError):
            return ''
    if data[:4] == b'\xd0\xcf\x11\xe0':  # old .doc
        try:
            return run(['catdoc', '-d', 'utf-8', '-w'], data, '.doc')
        except FileNotFoundError:
            return ''
    return ''

FIELDS = re.compile(r'\b(?:HYPERLINK|PAGEREF|TOC)\b(?:\s+(?:\\[a-zA-Z]|"[^"]*"|_Toc\d+|\d+(?:-\d+)?))*')

def clean(t):
    t = FIELDS.sub(' ', t)
    t = STRIP.sub('', t)
    t = re.sub(r'[ \t\f\r]+', ' ', t)
    t = re.sub(r'\s*\n\s*', '\n', t)
    return t.strip()

# Text already extracted in earlier builds, by Drive file id (DRIVE_CACHE; the workflow keeps it for a week),
# so each build only downloads files it has not seen.
CACHE = os.path.join(os.environ.get('DRIVE_CACHE', ''), 'text.json') if os.environ.get('DRIVE_CACHE') else None
cache = {}
if CACHE and os.path.exists(CACHE):
    try: cache = json.load(open(CACHE, encoding='utf-8'))
    except ValueError: cache = {}

def one(d):
    # Word first (cleanest text), then PDF.
    for kind in ('word', 'pdf'):
        if kind in d['f']:
            fid = d['f'][kind]
            if cache.get(fid): return cache[fid]
            text = clean(extract(fetch(fid)))
            if len(text) > 80:
                cache[fid] = text
                return text
    return ''

with cf.ThreadPoolExecutor(8) as ex:
    texts = list(ex.map(one, docs))
empty = sum(1 for t in texts if not t)
print(f'{len(texts)} documents, {empty} without text, {sum(map(len, texts)) // 1024} KB of text', file=sys.stderr)
if len(texts) > 100 and empty > len(texts) // 2:
    print('Warning: most documents came back without text (Drive may be limiting downloads).', file=sys.stderr)
if CACHE:
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(texts, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
