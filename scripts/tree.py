import json, re, sys
items = json.load(open(sys.argv[1]))
ROOT = "1GNB_nxa9GEel6ThtYqLgL0yHyt8_EMz4"
nodes = {(): {"n": "בית המדרש להלכה", "id": ROOT, "k": [], "f": []}}
clean = lambda s: re.sub(r'[‎‏‪-‮]', '', s).strip()
for it in sorted(items, key=lambda x: len(x['path'])):
    if it['folder']:
        if ROOT in it['url']: continue  # shortcut back to the root
        node = {"n": clean(it['name']), "id": it['id'], "k": [], "f": []}
        nodes[tuple(it['path']) + (it['name'],)] = node
        nodes[tuple(it['path'])]['k'].append(node)
    else:
        if it['name'].lower().endswith(('.txt', '.lnk')): continue
        fid = re.search(r'/d/([^/]+)', it['url']).group(1)
        nodes[tuple(it['path'])]['f'].append([clean(it['name']), fid])
def prune(n):
    n['k'] = [c for c in n['k'] if prune(c)]
    n['k'].sort(key=lambda c: c['n'])
    n['f'].sort(key=lambda f: f[0])
    if not n['k']: del n['k']
    if not n['f']: del n['f']
    return 'k' in n or 'f' in n
prune(nodes[()])
json.dump(nodes[()], open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
