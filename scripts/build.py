import json, re, sys, collections
items = json.load(open(sys.argv[1]))
SKIP_EXT = ('.txt', '.lnk')
def fmt_of(name):
    n = name.lower().strip()
    if n.endswith('.pdf') or n.endswith('pdf'): return 'pdf'
    if n.endswith(('.docx', '.doc')) or n.endswith('וורד'): return 'word'
    return 'pdf'
def base(name):
    n = re.sub(r'\.(pdf|docx?|PDF)$', '', name.strip(), flags=re.I)
    n = re.sub(r'(PDF| \| וורד)$', '', n).strip()
    n = n.replace('‏', '').replace('‎', '').replace('‫', '').replace('‬', '')
    n = re.sub(r'\s*\(\d+\)\s*$', '', n.strip())
    return n.strip(' _')
def heb(s):
    s = s.replace("''", '״').replace('"', '״').replace('_', '״')
    s = re.sub(r"(?<=[א-ת])'(?=[א-ת])", '״', s)
    s = s.replace("'", '׳')
    return re.sub(r'\s+', ' ', s).strip()
DATE = re.compile(r'(תש|תשע|תשפ|ניסן|אייר|סיון|סיוון|תמוז|אב|אלול|תשרי|חשון|חשוון|כסלו|טבת|שבט|אדר)')
def parse_vehagit(b):
    num = None
    m = re.match(r'^(\d+)\.\s*', b)
    if m: num = int(m.group(1)); b = b[m.end():]
    b = re.sub(r'^_*והגית(\s+בו)?\s*', '', b)
    m = re.match(r'^(?:גיליון|גליון)?\s*(\d+)\s*', b)
    if m:
        num = num or int(m.group(1)); b = b[m.end():]
    b = b.strip(' -–')
    parts = [p.strip() for p in re.split(r'\s*[-–]\s*', b) if p.strip()]
    date = None
    m = re.search(r'\s*\.(\d+)$', parts[-1]) if parts else None
    if m:
        num = num or int(m.group(1)); parts[-1] = parts[-1][:m.start()].strip()
    if len(parts) > 1 and DATE.search(parts[-1]) and re.search(r'ת[״_\'"]?ש|תש', parts[-1]) and len(parts[-1]) < 25:
        date = parts.pop()
    title = ' - '.join(parts) or b
    return title, num, date
def clean_folder(f):
    f = re.sub(r'^הלכה כסדרה \| ', '', f)
    return heb(f)
docs = collections.OrderedDict()
for it in items:
    if it['folder']: continue
    if it['name'].lower().endswith(SKIP_EXT): continue
    path = it['path']
    coll = path[0]
    topic = [p for p in path[1:] if p not in ('PDF', 'Word')]
    b = base(it['name'])
    key = (coll, tuple(topic), re.sub(r'[\s_]+', '', b))
    if coll == 'מאגר דפי והגית בו':
        title, num, date = parse_vehagit(b)
    else:
        title, num, date = b, None, None
        title = re.sub(r'^(הנחיות הלכתיות|הלכה כסדרה|לוח דינים ומנהגים|תורת המחנה [א-ד]׳?|\'?) \| ', '', title) or title
    d = docs.setdefault(key, {'t': heb(title), 'c': coll, 'p': [clean_folder(x) for x in topic], 'n': num, 'd': heb(date) if date else None, 'f': {}, 'o': heb(b)})
    fid = re.search(r'/d/([^/]+)', it['url']).group(1)
    d['f'].setdefault(fmt_of(it['name']), fid)
# dedupe Vehagit "חוברות" folders' path noise
out = []
for d in docs.values():
    p = d['p']
    p2 = []
    for x in p:
        x = re.sub(r'^(דפי והגית|חוברות והגית( בו)?|חוברת והגית בו) \| ', '', x)
        if x in ('מועדים',) and p2 and p2[-1] == 'מועדים': continue
        if p2 and x == p2[-1]: continue
        p2.append(x)
    d['p'] = [x.replace('בין המיצרים', 'בין המצרים') for x in p2]
    d['t'] = re.sub(r'\s*\(\d+\)', '', d['t'])
    r = {k: v for k, v in d.items() if v not in (None, {}, [])}
    if r['o'] == r['t']: r.pop('o')
    out.append(r)
merged, byk = [], {}
for r in out:
    k = (r['c'], r.get('n'), re.sub(r'\W', '', r['t'])[:6])
    o = byk.get(k) if r.get('n') else None
    if o and len(o['f']) == 1 and len(r['f']) == 1 and set(o['f']) != set(r['f']):
        o['f'].update(r['f'])
        for kk in ('d', 'o'):
            if kk in r and kk not in o: o[kk] = r[kk]
        if len(r.get('p', [])) > len(o.get('p', [])): o['p'] = r['p']
        continue
    byk[k] = r; merged.append(r)
out = merged
print(len(out), 'docs', file=sys.stderr)
print(collections.Counter(d['c'] for d in out), file=sys.stderr)
print(collections.Counter(len(d['f']) for d in out), file=sys.stderr)
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
