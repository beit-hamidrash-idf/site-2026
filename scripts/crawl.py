import re, json, sys, html, urllib.request, concurrent.futures as cf
ROOT = "1GNB_nxa9GEel6ThtYqLgL0yHyt8_EMz4"
ent = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?flip-entry-title">([^<]*)<', re.S)
def fetch(fid):
    for i in range(4):
        try:
            u = f"https://drive.google.com/embeddedfolderview?id={fid}"
            return urllib.request.urlopen(u, timeout=60).read().decode()
        except Exception as e:
            err = e
    print("FAIL", fid, err, file=sys.stderr); failed.append(fid); return ""
items = []
failed = []
def crawl(fid, path):
    h = fetch(fid)
    kids = []
    for eid, href, title in ent.findall(h):
        title = html.unescape(title).strip()
        is_folder = "/folders/" in href
        items.append({"id": eid, "name": title, "path": path, "folder": is_folder, "url": html.unescape(href)})
        if is_folder: kids.append((eid, path + [title]))
    return kids
queue = [(ROOT, [])]
with cf.ThreadPoolExecutor(12) as ex:
    while queue:
        res = list(ex.map(lambda a: crawl(*a), queue))
        queue = [k for r in res for k in r]
        print(len(items), "items, next level", len(queue), file=sys.stderr)
json.dump(items, open(sys.argv[1], "w"), ensure_ascii=False)
if failed:
    sys.exit(f"{len(failed)} folders could not be read; keeping the previous site online.")
