"""Crawl a public Drive folder tree: name, path, id, type label and last-modified date per entry."""
import re, json, sys, html, urllib.request, concurrent.futures as cf
ROOT, OUT = sys.argv[1], sys.argv[2]
ent = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?aria-label="([^"]*)".*?flip-entry-title">([^<]*)<.*?flip-entry-last-modified"><div>([^<]*)<', re.S)
def fetch(fid):
    for _ in range(4):
        try: return urllib.request.urlopen(f"https://drive.google.com/embeddedfolderview?id={fid}", timeout=60).read().decode()
        except Exception as e: err = e
    print("FAIL", fid, err, file=sys.stderr); return ""
items = []
def crawl(fid, path):
    kids = []
    for chunk in fetch(fid).split('<div class="flip-entry" id="entry-')[1:]:
        eid = chunk.split('"', 1)[0]
        href = re.search(r'<a href="([^"]+)"', chunk); title = re.search(r'flip-entry-title">([^<]*)<', chunk)
        if not href or not title: continue
        href = html.unescape(href.group(1))
        mime = re.search(r'/type/([^"]+)"', chunk); label = re.search(r'aria-label="([^"]+)"', chunk)
        mod = re.search(r'flip-entry-last-modified"><div>([^<]*)<', chunk)
        title = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', html.unescape(title.group(1))).strip()
        folder = "/folders/" in href
        items.append({"id": eid, "name": title, "path": path, "folder": folder, "url": href,
                      "type": mime.group(1) if mime else (label.group(1) if label else ""),
                      "shortcut": "drive-shortcut-icon" in chunk, "modified": mod.group(1) if mod else ""})
        if folder and "drive-shortcut-icon" not in chunk: kids.append((eid, path + [title]))
    return kids
queue = [(ROOT, [])]
with cf.ThreadPoolExecutor(12) as ex:
    while queue:
        queue = [k for r in ex.map(lambda a: crawl(*a), queue) for k in r]
print(len(items), "items", file=sys.stderr)
json.dump(items, open(OUT, "w"), ensure_ascii=False)
