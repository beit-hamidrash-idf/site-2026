"""Fill the page template with the crawled data and logos, and write a standalone index.html."""
import json, sys
src, data, tree, out = sys.argv[1:5]
t = open(f'{src}/template.html', encoding='utf-8').read()
logos = json.load(open(f'{src}/logos.json'))
js = lambda p: open(p, encoding='utf-8').read().replace('</', '<\\/')
page = t.replace('__DATA__', js(data)).replace('__TREE__', js(tree))
for k, v in logos.items():
    page = page.replace(f'__L_{k}__', v)
title, rest = page.split('\n', 1)
head, body = rest.split('<a class="skip"', 1)
open(out, 'w', encoding='utf-8').write(f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{title}
{head}</head>
<body style="margin:0">
<a class="skip"{body}
</body>
</html>
""")
