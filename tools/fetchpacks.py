"""Download pack art from the URLs recovered by packurls.py.

The workbooks reference pack art through IMAGE() formulas, so the pictures
are not in the .xlsx and have to be fetched. By default only the packs the
guides actually reference are downloaded; pass --all for the whole
catalogue.

Existing files are left alone, so a pack whose art was embedded in the
sheet (or replaced by hand) is never overwritten.

Usage: python -I tools/fetchpacks.py <site_dir> [--all] [workbook.xlsx ...]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook
import extract as X

UA = 'MDOT-pack-art-fetch/1.0 (static site build; one-off asset fetch)'
DELAY = 0.4


def packs_used(paths):
    used = set()
    for p in paths:
        wb = Workbook(p)
        for tab in wb.sheets:
            if tab in X.SHARED_TABS:
                continue
            cells = wb.cells(tab)
            secs = X.section_rows(cells)
            band = None
            for i, (r, h) in enumerate(secs):
                if 'FLOORS TO PICK' in h.upper():
                    band = (r, secs[i + 1][0] if i + 1 < len(secs)
                            else max(rr for rr, _ in cells) + 1)
                    break
            if not band:
                continue
            for f in X.parse_floors(cells, wb.images(tab), band[0], band[1],
                                    {}, wb):
                if f.get('packSlug'):
                    used.add(f['packSlug'])
    return used


def main():
    args = sys.argv[1:]
    site = args.pop(0)
    want_all = '--all' in args
    books = [a for a in args if a.endswith('.xlsx')]

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'pack_art_urls.json'), encoding='utf-8') as fh:
        catalogue = json.load(fh)['packs']

    targets = set(catalogue) if want_all else (packs_used(books) & set(catalogue))
    outdir = os.path.join(site, 'assets', 'packs')
    os.makedirs(outdir, exist_ok=True)

    got = skipped = failed = 0
    for slug in sorted(targets):
        png = os.path.join(outdir, slug + '.png')
        webp = os.path.join(outdir, slug + '.webp')
        if os.path.exists(png) or os.path.exists(webp):
            skipped += 1
            continue
        url = catalogue[slug]['url']
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if not data.startswith(b'\x89PNG'):
                print('  NOT PNG  %-42s %d bytes' % (slug, len(data)))
                failed += 1
                continue
            with open(png, 'wb') as fh:
                fh.write(data)
            print('  ok       %-42s %6.1f KB' % (slug, len(data) / 1024))
            got += 1
        except (urllib.error.URLError, OSError) as exc:
            print('  FAILED   %-42s %s' % (slug, exc))
            failed += 1
        time.sleep(DELAY)

    print('\ndownloaded %d, already present %d, failed %d (of %d targets)'
          % (got, skipped, failed, len(targets)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
