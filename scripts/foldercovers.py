"""Give every folder in the tree a picture: the first page of a file that represents it.

Usage: python scripts/foldercovers.py data-tree.json data-docs.json _site/fcovers
Prefers designed covers (booklets, calendars, books) over single sheets, takes the newest sheet
otherwise, and avoids giving two sibling folders the same picture. Adds "img" to each folder that
got one and rewrites data-tree.json. A folder whose files cannot be rendered keeps the plain icon."""
import json, os, re, subprocess, sys, tempfile, urllib.request
import concurrent.futures as cf

tree_path, docs_path, out_dir = sys.argv[1:4]
tree = json.load(open(tree_path, encoding='utf-8'))
docs = json.load(open(docs_path, encoding='utf-8'))
os.makedirs(out_dir, exist_ok=True)
URL = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'

# a Word file is pictured by the PDF of the same document, when there is one
word_to_pdf = {d['f']['word']: d['f']['pdf'] for d in docs if 'word' in d['f'] and 'pdf' in d['f']}
is_pdf = lambda name: name.lower().endswith('.pdf') or name.lower().endswith('pdf')

def candidates(node, path):
    """(score, pdf id) for every file under node."""
    out = []
    here = path + [node['n']]
    for name, fid in node.get('f', []):
        pid = fid if is_pdf(name) else word_to_pdf.get(fid)
        if not pid: continue
        where = ' '.join(here) + ' ' + name
        s = 0.0
        if 'חוברת' in name: s += 6          # a booklet has a real cover page
        if re.search(r'לוח דינים|תורת המחנה|הלכה כסדרה|הלכ.?.?ס', where): s += 5
        if 'כריכה' in name: s -= 8          # a bare cover sheet with nothing on it
        m = re.search(r'(\d{1,3})', name)
        if m: s += int(m.group(1)) / 1000   # newer sheets have a nicer layout
        out.append((s, pid))
    for k in node.get('k', []):
        out += [(s - 0.05, p) for s, p in candidates(k, here)]
    return out

picks = {}
def assign(node, path):
    used = set()
    for k in node.get('k', []):
        cands = sorted(set(candidates(k, path + [node['n']])), key=lambda c: -c[0])
        if cands:
            fresh = [c for c in cands if c[1] not in used] or cands
            picks[k['id']] = fresh[0][1]; used.add(fresh[0][1])
        assign(k, path + [node['n']])
assign(tree, [])

def render(pid):
    dest = os.path.join(out_dir, pid)
    if os.path.exists(dest + '.jpg'): return True
    for _ in range(3):
        try:
            data = urllib.request.urlopen(URL.format(pid), timeout=180).read(); break
        except Exception as e:
            err = e
    else:
        print('download failed', pid, err, file=sys.stderr); return False
    if data[:4] != b'%PDF': return False
    with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
        f.write(data); f.flush()
        r = subprocess.run(['pdftoppm', '-f', '1', '-l', '1', '-singlefile', '-jpeg', '-jpegopt', 'quality=72',
                            '-scale-to-x', '420', '-scale-to-y', '-1', f.name, dest], capture_output=True, timeout=180)
    if r.returncode != 0 or not os.path.exists(dest + '.jpg'): return False
    trim(dest + '.jpg')
    return True

def trim(path):
    """Cut white margins and printer's crop marks, so the picture starts at the page's design."""
    from PIL import Image, ImageFilter
    im = Image.open(path).convert('RGB')
    ink = im.convert('L').point(lambda v: 255 if v < 235 else 0)
    solid = ink.filter(ImageFilter.MinFilter(5))   # thin lines (crop marks, hairlines) drop out
    box = solid.getbbox()
    if box and (box[2] - box[0]) > im.width * 0.4:
        pad = 4
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
    im.save(path, quality=72, optimize=True)

unique = sorted(set(picks.values()))
with cf.ThreadPoolExecutor(8) as ex:
    ok = dict(zip(unique, ex.map(render, unique)))

def mark(node):
    pid = picks.get(node['id'])
    if pid and ok.get(pid): node['img'] = f'fcovers/{pid}.jpg'
    for k in node.get('k', []): mark(k)
mark(tree)
print(f'{len(picks)} folders, {sum(ok.values())} pictures rendered', file=sys.stderr)
json.dump(tree, open(tree_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
