import re, json, sys, html, datetime, urllib.request, concurrent.futures as cf
# The organized Drive folder the site is built from
ROOT = "14PifxaezRR8-LCZtONNsUS1iPUlkmITk"
# The previous repository: its "חדש" folder stays featured as it is,
# and any shortcut leading back to the old root is not followed (it would list everything twice)
OLD_ROOT = "1GNB_nxa9GEel6ThtYqLgL0yHyt8_EMz4"
LEGACY_NEW = "1bTWYqwRjodhIa6qMFj_iDXe3-kxvE5yB"
PRIVATE_FOLDER = "פנימי – לא לפרסום"  # internal files: never read, never published
ent = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?flip-entry-title">([^<]*)<'
                 r'(?:.*?flip-entry-last-modified"><div>([^<]*)<)?', re.S)
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
TODAY = datetime.date.today()
def parse_date(s):
    """Drive's folder view shows 'Nov 8' (this year), '8/11/24' (older) or a time of day (today)."""
    s = (s or "").strip()
    m = re.fullmatch(r"([A-Z][a-z]{2}) (\d{1,2})", s)
    if m and m.group(1) in MON:
        d = datetime.date(TODAY.year, MON[m.group(1)], int(m.group(2)))
        return (d if d <= TODAY + datetime.timedelta(days=1) else d.replace(year=d.year - 1)).isoformat()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", s)
    if m:
        return datetime.date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
    if re.search(r"\d:\d\d", s):
        return TODAY.isoformat()
    return None
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
seen = {ROOT, OLD_ROOT}
def crawl(fid, path):
    h = fetch(fid)
    kids = []
    for eid, href, title, mod in ent.findall(h):
        title = html.unescape(title).strip()
        href = html.unescape(href)
        is_folder = "/folders/" in href
        if is_folder:
            target = re.search(r"/folders/([^/?#]+)", href).group(1)
            # shortcuts can point back up the tree; follow every folder once only
            if title == PRIVATE_FOLDER or target in seen: continue
            seen.add(target)
        it = {"id": target if is_folder else eid, "name": title, "path": path, "folder": is_folder, "url": href}
        dt = parse_date(mod)
        if dt: it["m"] = dt
        items.append(it)
        if is_folder: kids.append((target, path + [title]))
    return kids
queue = [(ROOT, []), (LEGACY_NEW, ["חדש"])]
items.append({"id": LEGACY_NEW, "name": "חדש", "path": [], "folder": True,
              "url": f"https://drive.google.com/drive/folders/{LEGACY_NEW}"})
seen.add(LEGACY_NEW)
with cf.ThreadPoolExecutor(12) as ex:
    while queue:
        res = list(ex.map(lambda a: crawl(*a), queue))
        queue = [k for r in res for k in r]
        print(len(items), "items, next level", len(queue), file=sys.stderr)
json.dump(items, open(sys.argv[1], "w"), ensure_ascii=False)
main = [it for it in items if it["path"][:1] != ["חדש"] and not it["folder"]]
if len(main) < 200:
    sys.exit(f"only {len(main)} files were readable in the repository folder (is it shared as 'anyone with the link'?); keeping the previous site online.")
if failed:
    sys.exit(f"{len(failed)} folders could not be read; keeping the previous site online.")
