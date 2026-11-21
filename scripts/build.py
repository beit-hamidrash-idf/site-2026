import json, re, sys, collections
items = json.load(open(sys.argv[1]))
PRIVATE_FOLDER = 'פנימי – לא לפרסום'  # internal/classified files: never published on the site
items = [it for it in items if PRIVATE_FOLDER not in it['path']]
import datetime
NEW_FOLDER = 'חדש'  # the old repository's "new" folder: its files stay featured at the top of the page
# From this date on, every file added anywhere in the repository is also featured for a week,
# then stays only in its own folder (the site is rebuilt every day, so it drops off by itself)
AUTO_NEW_FROM = datetime.date(2026, 11, 23)
AUTO_NEW_DAYS = 7
today = datetime.date.today()
def recent(it):
    if it['folder'] or not it.get('m') or it['path'][:1] == [NEW_FOLDER]: return False
    d = datetime.date.fromisoformat(it['m'])
    return d >= AUTO_NEW_FROM and (today - d).days < AUTO_NEW_DAYS
new_items = [it for it in items if it['path'][:1] == [NEW_FOLDER]]
auto_new = [it for it in items if recent(it)]
items = [it for it in items if it['path'][:1] != [NEW_FOLDER] and it['path']]
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
# The same sheet sometimes sits twice in one folder (a Word copy without the issue number,
# or a PDF-only copy next to the PDF+Word entry). Fold those into one row, unless both
# carry different issue numbers (then they really are two different sheets).
tkey = lambda r: re.sub(r'[^א-ת0-9a-zA-Z]', '', r['t'])
merged, seen = [], collections.defaultdict(list)
for r in out:
    k = (r['c'], tuple(r.get('p', [])), tkey(r))
    o = next((x for x in seen[k] if not (x.get('n') and r.get('n') and x['n'] != r['n'])), None)
    if o:
        for fk, fv in r['f'].items():
            o['f'].setdefault(fk, fv)
        for kk in ('n', 'd', 'o'):
            if kk in r and kk not in o: o[kk] = r[kk]
        continue
    seen[k].append(r); merged.append(r)
out = merged
# A sheet filed under two topics may have only its PDF in one of them: give every copy
# all the formats that exist for that same sheet (same collection, number and title).
fmts = collections.defaultdict(dict)
for r in out:
    if r.get('n'):
        for fk, fv in r['f'].items(): fmts[(r['c'], r['n'], tkey(r))].setdefault(fk, fv)
for r in out:
    if r.get('n'):
        for fk, fv in fmts[(r['c'], r['n'], tkey(r))].items(): r['f'].setdefault(fk, fv)
print(len(out), 'docs', file=sys.stderr)
print(collections.Counter(d['c'] for d in out), file=sys.stderr)
print(collections.Counter(len(d['f']) for d in out), file=sys.stderr)
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
# Featured "new" files: one card per document, PDF and Word side by side.
def new_title(name):
    b = heb(re.sub(r"(?<![א-ת])ה'(?=ת)", 'ה׳', base(name)))
    parts = [x.strip() for x in b.split('|') if x.strip()]
    series = parts.pop(0) if len(parts) > 1 else ''
    return series, ' · '.join(parts) or b
feat = collections.OrderedDict()
for it in sorted(auto_new, key=lambda x: (x['m'], x['name']), reverse=True) + sorted(new_items, key=lambda x: x['name']):
    if it['folder'] or it['name'].lower().endswith(SKIP_EXT): continue
    m = re.search(r'/d/([^/]+)', it['url'])
    if not m: continue
    series, title = new_title(it['name'])
    if not series and it['path'] != [NEW_FOLDER]: series = clean_folder(it['path'][-1])
    d = feat.setdefault(re.sub(r'[^א-ת0-9a-zA-Z]', '', series + title), {'t': title, 's': series, 'f': {}})
    d['f'].setdefault(fmt_of(it['name']), m.group(1))
feat = [{k: v for k, v in d.items() if v} for d in feat.values()]
print(len(feat), 'new', file=sys.stderr)
if len(sys.argv) > 3:
    json.dump(feat, open(sys.argv[3], 'w'), ensure_ascii=False, separators=(',', ':'))
