"""Download every document from Drive and extract its text, for searching inside the booklets.

Writes a JSON list aligned with the documents list: one cleaned text string per document ("" when
no text could be extracted, e.g. scanned pages)."""
import io, json, re, subprocess, sys, tempfile, urllib.request, zipfile
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

def one(d):
    # Word first (cleanest text), then PDF.
    for kind in ('word', 'pdf'):
        if kind in d['f']:
            text = clean(extract(fetch(d['f'][kind])))
            if len(text) > 80:
                return text
    return ''

with cf.ThreadPoolExecutor(8) as ex:
    texts = list(ex.map(one, docs))
empty = sum(1 for t in texts if not t)
print(f'{len(texts)} documents, {empty} without text, {sum(map(len, texts)) // 1024} KB of text', file=sys.stderr)
if len(texts) > 100 and empty > len(texts) // 2:
    sys.exit('Most documents came back without text; keeping the previous site online.')
json.dump(texts, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
