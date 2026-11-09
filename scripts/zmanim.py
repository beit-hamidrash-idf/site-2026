"""Turn the "לוחות זמנים" PDF of לוח דינים ומנהגים into structured data for the site.

Usage: python scripts/zmanim.py data-items.json data-zmanim.json
Finds the file in the Drive listing, downloads it, and reads two kinds of tables:
- daily times per location (one row about every week),
- candle lighting / havdalah (and fast start / end) per location, for each Shabbat and holiday.
The PDF is laid out right to left, so every row is read in reverse."""
import json, re, subprocess, sys, tempfile, urllib.request

items_path, out_path = sys.argv[1:3]
URL = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'
BIDI = re.compile(r'[‎‏‪-‮⁦-⁩]')
TIME = re.compile(r'\b(\d{1,2}):(\d{2})\b')
GREG = re.compile(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2}))?(?!\d)')
MONTHS = r'(?:תשרי|מרחשוון|מרחשון|חשון|חשוון|כסלו|טבת|שבט|אדר א|אדר ב|אדר|ניסן|אייר|סיוון|סיון|תמוז|מנחם אב|אב|אלול)'
HDATE = re.compile(r'([א-ת]{1,3}["״\']?\s+' + MONTHS + r')(?![א-ת])')
DAILY = ['alot90', 'alot72', 'talit', 'sunrise', 'shema', 'tfila', 'chatzot', 'mincha', 'plag', 'sunset', 'tzeit']

def find_file(items):
    for it in items:
        if not it['folder'] and 'לוחות זמנים' in it['name'] and it['name'].lower().endswith('.pdf'):
            return re.search(r'/d/([^/]+)', it['url']).group(1), it['name']
    sys.exit('No "לוחות זמנים" PDF found in the Drive listing.')

def page_text(pdf, n):
    r = subprocess.run(['pdftotext', '-layout', '-f', str(n), '-l', str(n), pdf, '-'], capture_output=True)
    return BIDI.sub('', r.stdout.decode('utf-8', 'replace'))

def pages(pdf):
    r = subprocess.run(['pdfinfo', pdf], capture_output=True, text=True)
    return int(re.search(r'Pages:\s+(\d+)', r.stdout).group(1))

def times(line):
    return [f'{int(h)}:{m}' for h, m in TIME.findall(line)][::-1]   # right-to-left

def greg(line):
    m = None
    for m in GREG.finditer(TIME.sub(' ', line)): pass
    return (int(m.group(1)), int(m.group(2))) if m else None

def civil(dm, hdate):
    """The year runs Tishrei to Elul: September to December are in the first civil year, except Elul."""
    d, mth = dm
    year = start_year if mth >= 9 and 'אלול' not in hdate else start_year + 1
    return f'{year:04d}-{mth:02d}-{d:02d}'

fid, name = find_file(json.load(open(items_path, encoding='utf-8')))
m = re.search(r'תשפ["\'״]*([א-ת])', name)
heb_year = 'תשפ' + (m.group(1) if m else '')
# Tishrei of 5787 (תשפ"ז) falls in 2026
start_year = 5780 + 'אבגדהוזחט'.index(m.group(1)) + 1 - 3761 if m and m.group(1) in 'אבגדהוזחט' else 2026
data = urllib.request.urlopen(URL.format(fid), timeout=180).read()

with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
    f.write(data); f.flush()
    n = pages(f.name)
    texts = [page_text(f.name, i) for i in range(1, n + 1)]

# the location list: the index page, one name per line before its page numbers
locs = []
for t in texts[:2]:
    for line in t.splitlines():
        nums = re.findall(r'\b\d{3}\b', line)
        word = re.sub(r'[\d\s]+', ' ', line).strip()
        if len(nums) == 2 and word and 'זמני' not in word: locs.append(word)
locs = list(dict.fromkeys(locs))
if len(locs) < 5: sys.exit(f'Could not read the location list (found {locs}).')

daily = {l: [] for l in locs}
shabbat = []          # [{date, hdate, name, kind, times: {loc: [in, out]}}]
pending = None        # rows of the right-hand page of a Shabbat spread, waiting for the left-hand page
for t in texts:
    lines = [l for l in t.splitlines() if l.strip()]
    if not lines: continue
    head = ' '.join(lines[:3])
    if any('כניסה' in l and 'יציאה' in l for l in lines[:6]):
        header = next((l for l in lines if sum(l.count(x) for x in locs) >= 2), None)
        if not header: continue
        cols = sorted(((header.find(x), x) for x in locs if x in header))
        cols = [x for _, x in cols][::-1]                  # right-to-left reading order
        rows = [l for l in lines if TIME.search(l)]
        if any(greg(l) for l in rows):                     # the page that has the dates and names
            out = []
            for l in rows:
                dm = greg(l)
                if not dm: continue
                txt = TIME.sub(' ', GREG.sub(' ', l)).replace('(', ' ').replace(')', ' ')
                segs = [s.strip() for s in re.split(r'\s{2,}', txt) if s.strip()]
                hd = HDATE.search(txt)
                label = ' '.join(s for s in segs[::-1] if not HDATE.fullmatch(s) and s not in ('',))
                label = HDATE.sub('', label).strip(' -')
                out.append({'date': civil(dm, hd.group(1) if hd else ''), 'hdate': hd.group(1) if hd else '', 'name': label, 'times': {}, '_t': times(l)})
            pending = out; target = out
        else:
            target, pending = pending or [], None
            for r, l in zip(target, rows): r['_t'] = times(l)
        for r in target:
            v, k = r.pop('_t', []), len(cols)
            if len(v) == 2 * k:
                for i, c in enumerate(cols): r['times'][c] = [v[2 * i], v[2 * i + 1]]
            elif len(v) == k:
                for i, c in enumerate(cols): r['times'][c] = [None, v[i]]
        for r in target:
            if r not in shabbat: shabbat.append(r)
        continue
    loc = next((x for x in locs if any(x == re.sub(r'[\d/\\\s]+', ' ', l).strip() for l in lines[:3])), None)
    loc = loc or next((x for x in locs if x in head and 'זמן' not in head.replace('זמן', '', 0)), None)
    if not loc: continue
    for l in lines:
        v, dm = times(l), greg(l)
        if len(v) != len(DAILY) or not dm: continue
        hd = HDATE.search(TIME.sub(' ', l))
        row = dict(zip(DAILY, v)); row['hdate'] = hd.group(1) if hd else ''; row['date'] = civil(dm, row['hdate'])
        daily[loc].append(row)

for rows in daily.values():
    rows.sort(key=lambda r: r['date'])
for r in shabbat:
    early = any(a and int(a.split(':')[0]) < 9 for a, _ in r['times'].values())   # a fast starts at dawn
    if not r['name'] and early: r['name'] = 'צום י"ז בתמוז' if 'תמוז' in r['hdate'] else 'תענית'
    r['kind'] = 'fast' if early or re.search(r'צום|תענית|באב', r['name']) else 'shabbat'
# each Shabbat appears on several spreads, each with part of the locations: merge them
merged = {}
for r in shabbat:
    key = (r['date'], r['name'])
    if key in merged: merged[key]['times'].update(r['times'])
    else: merged[key] = r
shabbat = sorted((r for r in merged.values() if r['times']), key=lambda r: r['date'])
missing = [l for l in locs if len(daily[l]) < 20]
print(f'{len(locs)} locations, {sum(map(len, daily.values()))} daily rows, {len(shabbat)} Shabbat/holiday rows; thin: {missing}', file=sys.stderr)
if len(missing) > len(locs) // 2: sys.exit('Most locations came back without daily times.')
# compact rows: [date, hebrew date, ...times in DAILY order]
daily = {l: [[r['date'], r['hdate']] + [r[k] for k in DAILY] for r in rows] for l, rows in daily.items()}
json.dump({'year': heb_year, 'file': fid, 'locations': locs, 'cols': DAILY, 'daily': daily, 'shabbat': shabbat},
          open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
