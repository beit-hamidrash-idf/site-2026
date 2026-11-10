"""Collect every video of the YouTube channel for the "שיעורים מוקלטים" section.

Usage: python scripts/videos.py src/videos.json data-videos.json
YouTube's public feed lists only the newest 15 videos, so the list is cumulative: the feed is merged
with the list this site published on its previous build (videos.json on the live site) and with the
starter list in src/videos.json. Newest first. If YouTube cannot be reached, the older lists are kept."""
import html, json, re, sys, urllib.error, urllib.request

CHANNEL = 'UCNySKxULy7VBPkZIY5N0_3g'
FEED = f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}'
LIVE = 'https://beit-hamidrash-idf.github.io/site-2026/videos.json'
seed_path, out_path = sys.argv[1], sys.argv[2]

def get(url):
    for _ in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read().decode('utf-8')
        except Exception as e:
            err = e
    print('could not read', url, err, file=sys.stderr)
    return ''

feed = []
for e in re.findall(r'<entry>(.*?)</entry>', get(FEED), re.S):
    vid = re.search(r'<yt:videoId>([\w-]{11})</yt:videoId>', e)
    title = re.search(r'<title>(.*?)</title>', e, re.S)
    date = re.search(r'<published>(\d{4}-\d\d-\d\d)', e)
    if vid and title:
        feed.append({'id': vid.group(1), 't': html.unescape(title.group(1)).strip(), 'd': date.group(1) if date else ''})
try:
    previous = json.loads(get(LIVE) or '[]')
except ValueError:
    previous = []
seed = json.load(open(seed_path, encoding='utf-8'))

def gone(vid):
    """True when YouTube says the video no longer exists (deleted, or replaced by a new upload)."""
    try:
        urllib.request.urlopen(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json', timeout=30)
        return False
    except urllib.error.HTTPError as e:
        return e.code in (400, 401, 403, 404)
    except Exception:
        return False   # network trouble: keep it

out, seen = [], set()
for v in feed + previous + seed:
    if v.get('id') and v['id'] not in seen:
        seen.add(v['id']); out.append(v)
if feed:   # YouTube is reachable: check the older entries are still there
    removed = [v for v in out if v not in feed and gone(v['id'])]
    out = [v for v in out if v not in removed]
    if removed: print('removed from YouTube:', ', '.join(v['id'] for v in removed), file=sys.stderr)
print(len(feed), 'in feed,', len(out), 'videos in total', file=sys.stderr)
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
