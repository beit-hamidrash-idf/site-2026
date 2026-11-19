# Sorting the two Drive folders into one organized folder

Tools used to catalog and organize the library's materials. Not part of the website build.

Sources (public folders):
- main library: `1GNB_nxa9GEel6ThtYqLgL0yHyt8_EMz4`
- second folder: `1VwIDx6z-uTHhziml0wp1LBzu1LR9RleG`

Steps:
1. `python crawl_meta.py <folder-id> out.json` for each folder: names, paths, types, dates.
2. `python catalog.py new.json main.json catalog.xlsx [report.csv]`: the Excel catalog, every file
   sorted into one of 15 suggested categories (the `CATS` list), with duplicates and items to review.
3. `python organize.py new.json main.json catalog.py OUTDIR`: downloads everything into the
   suggested layout (`NN category/subfolder/file`), keeps byte-identical copies once, and writes
   `דוח סידור הקבצים.csv` (where every original file went).

Google Docs files cannot be downloaded through drive.usercontent.google.com; they were exported
through the Google Drive connector instead.

Next step planned: build the same layout inside Google Drive, in a separate account, with the
Google Drive connector (create the 15 folders, then copy each file into its place, skipping the
byte-identical duplicates listed in the report as "הוסר").
