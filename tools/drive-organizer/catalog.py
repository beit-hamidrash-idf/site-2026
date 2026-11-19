"""Build a combined catalog workbook of two public Drive folders, sorted into suggested categories."""
import json, re, sys, datetime, collections
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

NEW, MAIN, OUT = sys.argv[1:4]
REPORT = sys.argv[4] if len(sys.argv) > 4 else None
TODAY = datetime.date(2026, 11, 19)
SRC_MAIN, SRC_NEW = "המאגר המקוון (קישור 1)", "התיקייה החדשה (קישור 2)"

CATS = [  # key, sheet name, description, suggested sub-folders
 ("vehagit", "והגית בו", "גיליונות 'והגית בו' – מקום אחד לכל הגיליונות, ממוספרים, PDF ו-Word זה לצד זה", "לפי נושא: שבת ועירובין · מועדים · תפילה וברכות · כשרות · שמיטה ותרו״מ · צבא ומלחמה · שונות"),
 ("units", "הלכה כסדרה ויחידות", "הנחיות הלכתיות מעשיות ליחידות ולמצבים מבצעיים (חמ״ל, מרפאה, נהיגה, יחידות)", "לפי יחידה / מצב: שבת בשטח · חמ״ל · רפואה · יחידות (חיל הים, טנקים, תותחנים…) · מצבי חירום"),
 ("moadim", "מועדים", "חוברות והנחיות לחגים ולזמנים מיוחדים, מכל הסדרות", "תיקייה לכל חג, ובתוכה שנה (תשפ״ו, תשפ״ז)"),
 ("war", "מלחמה ומבצעים", "פרסומים שנכתבו למבצעים: חרבות ברזל, שאגת הארי ועוד", "לפי מבצע, ובתוכו לפי נושא"),
 ("luach", "לוחות", "לוח דינים ומנהגים, לוח הלכתי ולוחות זמנים", "לפי שנה: תשפ״ז (נוכחי) · ארכיון שנים קודמות"),
 ("books", "ספרים וחוברות", "ספרי יסוד (תורת המחנה) וחוברות מקצועיות, טבלאות ו'מחניך'", "תורת המחנה · חוברות מקצועיות · טבלאות הלכה · מחניך"),
 ("topics", "נושאים הלכתיים", "פרסומים בנושאים קבועים: חופה, מזוזה, ציצית, תפילין, בית כנסת, ספר תורה ועוד", "תיקייה לכל נושא"),
 ("shmita", "שמיטה", "חומרי שמיטה ועדכוני ענף הכשרות", "הנחיות · עדכוני שמיטה (ממוספרים) · קטיף ורכש"),
 ("parasha", "פרשת שבוע", "דברי תורה לפרשת השבוע (חלק גדול כצילומי עמודים)", "לפי כותב, ובתוכו לפי חומש ופרשה"),
 ("sources", "דפי מקורות ושיעורים", "דפי מקורות, שיעורים וכתבי רבנים", "לפי רב / נושא"),
 ("training", "השתלמויות והכשרה", "השתלמויות, ימי עיון, מבחנים, מצגות ונהלים פנימיים", "לפי השתלמות ושנה – כדאי שלא יהיה ציבורי"),
 ("tech", "הלכה וטכנולוגיה", "מכשירים במצב שבת, משאבות, קטלוגים", "לפי מכשיר"),
 ("media", "מדיה", "הקלטות שמע ווידאו", "לפי סדרה / השתלמות"),
 ("archive", "ארכיון", "גרסאות ישנות שסומנו כארכיון", "לפי שנה"),
 ("other", "שונות לבדיקה", "קבצים שלא שויכו אוטומטית – למיין ידנית", "—"),
]
CAT_NAME = {k: n for k, n, *_ in CATS}

def has(path_name, *words): return any(w in path_name for w in words)
def category(x):
    t, p = x["type"], " / ".join(x["path"]); pn = p + " / " + x["name"]
    if t.startswith(("audio", "video")): return "media"
    if "ארכיון" in p: return "archive"
    if has(p, "והגית"): return "vehagit"
    if has(p, "פרשת שבוע"): return "parasha"
    if has(p, "שמיטה", "שביעית", "כלאיים"): return "shmita"
    if has(p, "השתלמות", "מבחן כושר", "כתיבת מאמרים", "מצגות", "ימי עיון", "יום עיון", "נהלים", 'קק"צ', "נספח רבנות"): return "training"
    if has(p, "טכנולוגיה"): return "tech"
    if has(p, "חרבות ברזל", "שאגת הארי", "מבצע צבאי", "עלות השחר", "אזעקה", "קשת נחושה", "מלחמה"): return "war"
    if has(p, "לוח דינים", "לוח הלכתי") or (x["path"][:1] == ["לוח דינים ומנהגים"]): return "luach"
    if has(p, "חגים", "דגשים לשבת ומועדים", 'הלכ"ס לחגים', "הלכה כסדרה חגים", "בין המיצרים", "טו בשבט", "יזכור", "מעגל השנה") or has(x["name"], "חנוכה", "פורים", "פסח", "סוכות"): return "moadim"
    if has(p, "הלכה כסדרה", "הלכס", "שבת") and not has(p, "פרשת"): return "units"
    if has(p, "חיל הים", "טנקים", "תותחנים", "טיפול בחללים", "איסוף קרבי", "פיקוד העורף", "עוקץ", "הגנת יישובים", "תצפתניות", "פיקוח נפש",
           "חזרה בשבת", "פלאפון בשבת", "גיוס חירום", "רכב חשמלי", "עט שבת", "בית כלא", "אסון המוני", "משלחת", "ספירת חיילים", "הכנה לתעסוקה", "מרכז הצבי", "מירוץ"): return "units"
    if has(p, "תורת המחנה", "חוברות מקצועיות", "ספרים", "טבלאות הלכה", "מחניך"): return "books"
    if has(p, "דפי מקורות", "הרב ", "שכתבו רבנים", "מכון הסת"): return "sources"
    if x["path"][:1] == ["עיקרי הפרסומים"] and len(x["path"]) > 1: return "topics"
    n = x["name"]                                    # loose files: decide by the file name
    if "לוח דינים" in n: return "luach"
    if has(n, 'בט"ש', "בשבת", "מסדר", "נספח הלכתי"): return "units"
    if has(n, "ספר ", "הלכות ציבור"): return "books"
    if has(n, "כהנים"): return "topics"
    return "other"

TYPES = {"application/pdf": "PDF", "application/msword": "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
         "application/vnd.google-apps.document": "Google Docs", "application/vnd.openxmlformats-officedocument.presentationml.presentation": "מצגת",
         "image/jpeg": "תמונה", "image/png": "תמונה", "text/plain": "טקסט", "application/vnd.google-apps.shortcut": "קיצור דרך", "application/x-ms-shortcut": "קיצור דרך"}
def ftype(t): return TYPES.get(t) or ("שמע" if t.startswith("audio") else "וידאו" if t.startswith("video") else t or "לא ידוע")

MON = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
def mdate(s):
    s = s.strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})$", s)
    if m: return datetime.date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2})$", s)            # Drive omits the year for this year
    if m: return datetime.date(TODAY.year, MON[m.group(1)], int(m.group(2)))
    if re.match(r"\d{1,2}:\d{2}", s): return TODAY             # edited today
    return None

def title(n):
    n = re.sub(r"\.(pdf|docx?|pptx?|jpe?g|png|txt|m4a|mp3|mp4|ogg|lnk)$", "", n, flags=re.I)
    n = re.sub(r"\s*\(\d+\)\s*$", "", n).replace("_", "״").replace("''", "״")
    return re.sub(r"\s+", " ", n).strip(" -")
def dupkey(n):
    k = title(n).lower()
    k = re.sub(r"והגית( בו)?|גיליון|גליון|עותק של", "", k)
    return re.sub(r"[^\w]", "", k)

rows = []
for src, path in ((SRC_MAIN, MAIN), (SRC_NEW, NEW)):
    for x in json.load(open(path, encoding="utf-8")):
        if x["folder"]: continue
        x["src"] = src
        rows.append(x)
by_key = collections.defaultdict(list)
for r in rows: by_key[(dupkey(r["name"]), ftype(r["type"]))].append(r)
for r in rows:
    r["cat"] = category(r); r["kind"] = ftype(r["type"]); r["date"] = mdate(r["modified"]); r["title"] = title(r["name"])
    same = by_key[(dupkey(r["name"]), r["kind"])]
    other_src = any(o["src"] != r["src"] for o in same)
    r["dup"] = ("גם בקישור השני" if other_src else "") if len(same) <= 1 or not dupkey(r["name"]) else (
        f"{len(same)} עותקים" + (" · גם בקישור השני" if other_src else ""))
    notes = []
    if r["kind"] == "קיצור דרך": notes.append("קיצור דרך – לבדוק לאן מפנה")
    if not re.search(r"\.[A-Za-z0-9]{2,4}$", r["name"]) and r["kind"] in ("PDF", "Word"): notes.append("שם בלי סיומת קובץ")
    if re.search(r"לא מענף הלכה|לא ענף הלכה|לא צבאי", " ".join(r["path"])): notes.append("מסומן 'לא ענף הלכה' – להחליט אם לפרסם")
    if r["kind"] == "תמונה": notes.append("צילום – מומלץ לאחד ל-PDF")
    if r["cat"] == "training": notes.append("חומר פנימי – לשקול שלא לפרסם")
    r["note"] = " · ".join(notes)
    sub = [p for p in r["path"] if p not in ("PDF", "Word", "קבצי וורד")]
    r["topic"] = " › ".join(sub[1:]) if len(sub) > 1 else (sub[0] if sub else "")
    r["where"] = " / ".join(r["path"]) or "(תיקייה ראשית)"
# where each file went in the organized folder (from the organizer's report)
placed = {}
if REPORT:
    import csv
    for x in list(csv.reader(open(REPORT, encoding="utf-8-sig")))[1:]:
        placed.setdefault((x[0], x[1], x[2]), []).append(x)
for r in rows:
    hits = placed.get((r["src"], r["where"], r["name"]))
    x = hits.pop(0) if hits else ["", "", "", "", "", ""]      # same name twice in one folder: one report line each
    r["newpath"], r["state"] = x[3], {"נשמר": "בתיקייה המסודרת", "הוסר": "עותק זהה – נשמר פעם אחת", "קישור": "נשאר ב-Drive (וידאו גדול)", "דולג": "קיצור דרך – לא נכלל"}.get(x[4], x[4])
order = {k: i for i, (k, *_ ) in enumerate(CATS)}
rows.sort(key=lambda r: (order[r["cat"]], r["topic"], r["title"]))

# ---------- workbook ----------
F = "Arial"
H = Font(name=F, bold=True, color="FFFFFF", size=11); B = Font(name=F, size=10); BB = Font(name=F, size=10, bold=True)
LINK = Font(name=F, size=10, color="1D5BA6", underline="single"); TITLE = Font(name=F, bold=True, size=16, color="132033")
HFILL = PatternFill("solid", start_color="132033"); ZEBRA = PatternFill("solid", start_color="F4F6F9"); GOLD = PatternFill("solid", start_color="FFF4D6")
thin = Side(style="thin", color="DCE2EA"); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
RTL = Alignment(horizontal="right", vertical="center", wrap_text=True, readingOrder=2)
CEN = Alignment(horizontal="center", vertical="center", readingOrder=2)

wb = Workbook()
def sheet(name, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = name; ws.sheet_view.rightToLeft = True
    return ws
def header(ws, r, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(row=r, column=i, value=c); cell.font = H; cell.fill = HFILL; cell.alignment = CEN; cell.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[r].height = 24

COLS = ["מס'", "כותרת", "נושא / תת-תיקייה", "קטגוריה מוצעת", "מיקום נוכחי", "קישור מקור", "סוג קובץ", "עודכן", "כפילות", "הערה לבדיקה", "קישור", "שם הקובץ המקורי", "מיקום בתיקייה המסודרת", "מצב בתיקייה המסודרת"]
WID  = [6, 46, 30, 20, 40, 22, 11, 11, 20, 30, 9, 40, 55, 24]
def file_rows(ws, items, start):
    for i, r in enumerate(items):
        row = start + i
        vals = [i + 1, r["title"], r["topic"], CAT_NAME[r["cat"]], r["where"], r["src"], r["kind"], r["date"], r["dup"], r["note"], "פתיחה", r["name"], r.get("newpath", ""), r.get("state", "")]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=c, value=v); cell.font = B; cell.alignment = RTL; cell.border = BOX
        ws.cell(row=row, column=1).alignment = CEN
        d = ws.cell(row=row, column=8)
        if r["date"]: d.number_format = "dd/mm/yyyy"; d.alignment = CEN
        lk = ws.cell(row=row, column=11); lk.hyperlink = r["url"]; lk.font = LINK; lk.alignment = CEN
        if r["dup"] and "עותקים" in r["dup"]: ws.cell(row=row, column=9).fill = GOLD
        if r["note"]: ws.cell(row=row, column=10).fill = GOLD
    return start + len(items) - 1

# 1. summary
ws = sheet("סיכום", first=True)
ws["A1"] = "קטלוג חומרי ההלכה – שני קישורי ה-Drive יחד"; ws["A1"].font = TITLE
ws["A2"] = f"נכון ל-{TODAY:%d/%m/%Y}. הנתונים נאספו מהתיקיות הציבוריות; המספרים בטבלה מחושבים מגיליון 'כל הקבצים'."; ws["A2"].font = Font(name=F, size=10, color="566377")
header(ws, 4, ["קטגוריה מוצעת", SRC_MAIN, SRC_NEW, "סה״כ", "PDF", "Word", "אחר", "עם כפילות", "לבדיקה"], [26, 22, 22, 10, 9, 9, 9, 12, 10])
ALL = "'כל הקבצים'"
n = len(rows); rng = lambda col: f"{ALL}!${col}$2:${col}${n+1}"
for i, (k, name, *_ ) in enumerate(CATS):
    r = 5 + i
    ws.cell(row=r, column=1, value=name)
    ws.cell(row=r, column=2, value=f'=COUNTIFS({rng("D")},$A{r},{rng("F")},B$4)')
    ws.cell(row=r, column=3, value=f'=COUNTIFS({rng("D")},$A{r},{rng("F")},C$4)')
    ws.cell(row=r, column=4, value=f"=B{r}+C{r}")
    ws.cell(row=r, column=5, value=f'=COUNTIFS({rng("D")},$A{r},{rng("G")},"PDF")')
    ws.cell(row=r, column=6, value=f'=COUNTIFS({rng("D")},$A{r},{rng("G")},"Word")')
    ws.cell(row=r, column=7, value=f"=D{r}-E{r}-F{r}")
    ws.cell(row=r, column=8, value=f'=COUNTIFS({rng("D")},$A{r},{rng("I")},"*עותקים*")')
    ws.cell(row=r, column=9, value=f'=COUNTIFS({rng("D")},$A{r},{rng("J")},"?*")')
tot = 5 + len(CATS)
ws.cell(row=tot, column=1, value="סה״כ")
for c in range(2, 10):
    L = get_column_letter(c); ws.cell(row=tot, column=c, value=f"=SUM({L}5:{L}{tot-1})")
for r in range(5, tot + 1):
    for c in range(1, 10):
        cell = ws.cell(row=r, column=c); cell.border = BOX; cell.font = BB if (c == 1 or r == tot) else B
        cell.alignment = RTL if c == 1 else CEN
        if r == tot: cell.fill = ZEBRA
ws.cell(row=tot + 2, column=1, value="איך לקרוא: 'עם כפילות' = קובץ שיש לו עוד עותק באותו סוג (לפי שם); 'לבדיקה' = קבצים עם הערה בעמודת 'הערה לבדיקה'.").font = Font(name=F, size=9, color="566377")
ws.freeze_panes = "A5"

# 2. proposed arrangement
ws = sheet("הצעת סידור")
ws["A1"] = "הצעה לסידור משותף של שתי התיקיות"; ws["A1"].font = TITLE
ws["A2"] = "תיקייה ראשית אחת עם 15 תיקיות ממוספרות. המספר בשם התיקייה שומר על הסדר ב-Drive."; ws["A2"].font = Font(name=F, size=10, color="566377")
header(ws, 4, ["תיקייה מוצעת", "מה נכנס בה", "חלוקה פנימית מוצעת", "קבצים"], [30, 60, 60, 10])
for i, (k, name, desc, subs) in enumerate(CATS):
    r = 5 + i
    vals = [f"{i+1:02d} {name}", desc, subs, f"=סיכום!D{5+i}"]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v); cell.border = BOX; cell.font = BB if c == 1 else B
        cell.alignment = CEN if c == 4 else RTL
    ws.row_dimensions[r].height = 32
rr = 5 + len(CATS) + 1
rules = ["כללים מומלצים:",
 "1. מקור אחד לכל קובץ: לפני העברה, למחוק עותקים כפולים (עמודת 'כפילות' בגיליונות). להשאיר את הגרסה המעודכנת.",
 "2. שמות קבצים אחידים: '[מספר] - [כותרת] - [שנה].pdf', למשל '357 - שניים מקרא ואחד תרגום - תשפ״ז.pdf'. תמיד עם סיומת.",
 "3. PDF ו-Word באותה תיקייה, באותו שם, במקום תיקיות PDF ו-Word נפרדות.",
 "4. 'חדש' נשארת תיקייה זמנית: מעבירים אליה רק לתקופה, ואחר כך לתיקייה הקבועה.",
 "5. 'ארכיון' בתוך כל קטגוריה ולא תיקייה כללית, כדי שקל למצוא גרסה קודמת.",
 "6. חומר פנימי (השתלמויות, נהלים, 'לא מענף הלכה') – בתיקייה נפרדת שאינה משותפת לציבור.",
 "7. צילומי עמודים (JPG) – לאחד ל-PDF אחד לכל פרשה או חוברת."]
for i, t in enumerate(rules):
    c = ws.cell(row=rr + i, column=1, value=t); c.font = BB if i == 0 else B; c.alignment = Alignment(horizontal="right", readingOrder=2)
    ws.merge_cells(start_row=rr + i, start_column=1, end_row=rr + i, end_column=3)

# 3. one sheet per category
for k, name, *_ in CATS:
    items = [r for r in rows if r["cat"] == k]
    if not items: continue
    ws = sheet(name[:31])
    header(ws, 1, COLS, WID)
    last = file_rows(ws, items, 2)
    ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{last}"

# 4. everything, 5. duplicates, 6. to review
ws = sheet("כל הקבצים"); header(ws, 1, COLS, WID); last = file_rows(ws, rows, 2)
ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:N{last}"
dups = sorted([r for r in rows if "עותקים" in r["dup"]], key=lambda r: (dupkey(r["name"]), r["src"]))
ws = sheet("כפילויות"); header(ws, 1, COLS, WID); last = file_rows(ws, dups, 2); ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:N{max(last,2)}"
rev = [r for r in rows if r["note"]]
ws = sheet("לבדיקה"); header(ws, 1, COLS, WID); last = file_rows(ws, rev, 2); ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:N{max(last,2)}"

wb.save(OUT)
c = collections.Counter(r["cat"] for r in rows)
print(len(rows), "files;", {CAT_NAME[k]: c[k] for k, *_ in CATS})
print("duplicates rows:", len(dups), "review rows:", len(rev))
