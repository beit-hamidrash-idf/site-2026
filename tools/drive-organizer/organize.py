"""Download both Drive folders and lay them out in the suggested structure.
Usage: python organize.py new.json main.json catalog.py OUTDIR"""
import sys, os, re, json, csv, hashlib, urllib.request, concurrent.futures as cf, collections
NEW, MAIN, CATPY, OUT = sys.argv[1:5]
# reuse the catalog's classification (everything before the workbook part)
src = open(CATPY, encoding="utf-8").read().split("# ---------- workbook ----------")[0]
g = {"__name__": "cat"}; sys.argv = ["x", NEW, MAIN, "/dev/null"]; exec(src, g)
rows, CATS, CAT_NAME = g["rows"], g["CATS"], g["CAT_NAME"]

BAD = re.compile(r'[\\/:*?<>|‎‏‪-‮]')
def safe(s): return re.sub(r"\s+", " ", BAD.sub("-", s.replace('"', "״"))).strip(" .-") or "ללא שם"
EXT = {"application/pdf": ".pdf", "application/msword": ".doc", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
       "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx", "image/jpeg": ".jpg", "image/png": ".png",
       "text/plain": ".txt", "audio/x-m4a": ".m4a", "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "video/mp4": ".mp4",
       "application/vnd.google-apps.document": ".docx"}
VEH = [("שבת ועירובין", "שבת|עירוב|מוקצה|הבדלה|קידוש|מלאכ"), ("מועדים", "מועד|חג|פסח|סוכות|חנוכה|פורים|תשרי|אלול|בין המ|עומר|שבועות|תעני|צום|עצמאות|טבת|סליחות"),
       ("תפילה וברכות", "תפיל|ברכ|קריאת|ציצית|נטילת|זימון|כבוד בית|מנחה|ערבית|שחרית|מניין"), ("כשרות", "כשרות|בשר וחלב|בישולי|טבילת כלים|איסורים"),
       ("שמיטה ותרומות ומעשרות", "שמיטה|שביעית|תרומות|מעשרות"), ("צבא ומלחמה", "צבא|מלחמה|סכנה|מבצע"), ("מזוזה", "מזוזה"),
       ("לימוד תורה ושמירת הלשון", "לימוד תורה|שמירת הלשון|לשון הרע"), ("שונות", ".")]
WRAP = {"'והגית'", "מאגר דפי והגית בו", "PDF", "Word", "עיקרי הפרסומים", "הלכה כסדרה", "שבת", "קבצי וורד", "תורת המחנה", "לוח דינים ומנהגים",
        "דפי מקורות", "חוברות מקצועיות שונות", "השתלמות בית מדרש", "הלכה וטכנולוגיה", "פרשת שבוע", "לוח הלכתי", "לוח דינים"}
def subfolder(r):
    if r["cat"] == "vehagit":
        hay = " ".join(r["path"][1:]) + " " + r["name"]
        inner = [p for p in r["path"][1:] if p not in WRAP and p != "תפילה"]
        hay = " ".join(inner) + " " + r["name"]
        return next(n for n, rx in VEH if re.search(rx, hay))
    if r["cat"] in ("training",):
        return r["path"][1] if len(r["path"]) > 1 else ""
    parts = [p for p in r["path"] if p not in WRAP and p != CAT_NAME[r["cat"]]]
    parts = [re.sub(r"^(הלכה כסדרה|והגית|דפי והגית|חוברות והגית( בו)?)\s*\|\s*", "", p) for p in parts]
    return " - ".join(parts[:2])

URL = "https://drive.usercontent.google.com/download?id={}&export=download&confirm=t"
def fetch(r):
    fid = re.search(r"/d/([^/]+)", r["url"]).group(1)
    u = (f"https://docs.google.com/document/d/{fid}/export?format=docx" if r["type"] == "application/vnd.google-apps.document" else URL.format(fid))
    for _ in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300).read()
            if data[:15].lstrip().lower().startswith((b"<!doctype html", b"<html")): raise ValueError("got a web page, not the file")
            return data
        except Exception as e: err = e
    raise RuntimeError(str(err))

report, seen, used = [], {}, collections.defaultdict(set)
todo = [r for r in rows if "/d/" in r["url"] and not r["type"].endswith("shortcut")]
for r in rows:
    if r not in todo: report.append([r["src"], r["where"], r["name"], "", "דולג", "קיצור דרך – לא קובץ"])
cat_idx = {k: i + 1 for i, (k, *_) in enumerate(CATS)}
def run(r):
    try: return r, fetch(r), None
    except Exception as e: return r, None, str(e)
done = 0
with cf.ThreadPoolExecutor(8) as ex:
    for r, data, err in ex.map(run, todo):
        done += 1
        if done % 200 == 0: print(done, "/", len(todo), flush=True)
        if err: report.append([r["src"], r["where"], r["name"], "", "נכשל", err[:120]]); continue
        h = hashlib.sha256(data).hexdigest()
        if h in seen:
            report.append([r["src"], r["where"], r["name"], seen[h], "הוסר", "עותק זהה בדיוק לקובץ שנשמר"]); continue
        folder = os.path.join(f"{cat_idx[r['cat']]:02d} {CAT_NAME[r['cat']]}", *[safe(p) for p in [subfolder(r)] if p])
        base = safe(re.sub(r"\.(pdf|docx?|pptx?|jpe?g|png|txt|m4a|mp3|mp4|ogg)$", "", r["name"], flags=re.I))[:120]
        ext = EXT.get(r["type"], os.path.splitext(r["name"])[1] or "")
        name, n = base + ext, 2
        while name.lower() in used[folder]: name, n = f"{base} ({n}){ext}", n + 1
        used[folder].add(name.lower())
        os.makedirs(os.path.join(OUT, folder), exist_ok=True)
        with open(os.path.join(OUT, folder, name), "wb") as f: f.write(data)
        rel = os.path.join(folder, name); seen[h] = rel
        report.append([r["src"], r["where"], r["name"], rel, "נשמר", ""])
with open(os.path.join(OUT, "דוח סידור הקבצים.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["קישור מקור", "מיקום מקורי", "שם מקורי", "מיקום חדש", "מצב", "הערה"]); w.writerows(report)
c = collections.Counter(x[4] for x in report); print(dict(c))
