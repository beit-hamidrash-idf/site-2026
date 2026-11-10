"""Collect the episodes of the Spotify show for the "שיעורים מוקלטים" section.

Usage: python scripts/spotify.py src/spotify.json data-spotify.json
Spotify publicly shows only a show's newest episode, so the list is cumulative: the newest episode
(read from the show's embed page) is merged with the list this site published on its previous build
(spotify.json on the live site) and with the starter list in src/spotify.json. Newest first."""
import json, re, sys, urllib.request

SHOW = '14hwNL6upLWg2VC1Z67pr5'
EMBED = f'https://open.spotify.com/embed/show/{SHOW}'
LIVE = 'https://beit-hamidrash-idf.github.io/site-2026/spotify.json'
seed_path, out_path = sys.argv[1], sys.argv[2]

def get(url):
    for _ in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read().decode('utf-8')
        except Exception as e:
            err = e
    print('could not read', url, err, file=sys.stderr)
    return ''

def tidy(t):
    t = t.strip()
    if t.startswith('?'): t = t[1:].strip() + '?'  # a question mark that slipped to the start in RTL
    return t

latest = []
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', get(EMBED), re.S)
if m:
    try:
        e = json.loads(m.group(1))['props']['pageProps']['state']['data']['entity']
        eid = e['uri'].rsplit(':', 1)[-1]
        latest.append({'id': eid, 't': tidy(e['title']), 'd': ((e.get('releaseDate') or {}).get('isoString') or '')[:16],
                       's': round((e.get('duration') or 0) / 1000)})
    except (KeyError, ValueError, TypeError) as err:
        print('unexpected embed data', err, file=sys.stderr)
try:
    previous = json.loads(get(LIVE) or '[]')
except ValueError:
    previous = []
seed = json.load(open(seed_path, encoding='utf-8'))

# the show page lists all current episodes: when it can be read, it is the whole truth
# (episodes that were removed or replaced drop out); details come from each episode's embed page
listed = list(dict.fromkeys(re.findall(r'/episode/([A-Za-z0-9]{22})', get(f'https://open.spotify.com/show/{SHOW}'))))
if listed:
    known = {v['id']: v for v in latest + previous + seed}
    current = []
    for eid in listed:
        if eid in known: current.append(known[eid]); continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', get(f'https://open.spotify.com/embed/episode/{eid}'), re.S)
        try:
            e = json.loads(m.group(1))['props']['pageProps']['state']['data']['entity']
            current.append({'id': eid, 't': tidy(e['title']), 'd': ((e.get('releaseDate') or {}).get('isoString') or '')[:16],
                            's': round((e.get('duration') or 0) / 1000)})
        except (AttributeError, KeyError, ValueError, TypeError):
            print('could not read episode', eid, file=sys.stderr)
    latest, previous, seed = current, [], []

out, seen = [], set()
for v in latest + previous + seed:
    if v.get('id') and v['id'] not in seen:
        seen.add(v['id']); out.append(v)
out.sort(key=lambda v: v.get('d', ''), reverse=True)
print(len(latest), 'new from Spotify,', len(out), 'episodes in total', file=sys.stderr)
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
