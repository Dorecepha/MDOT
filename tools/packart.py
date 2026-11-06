"""Sweep every team tab for booster-pack art and build the pack asset library.

`extract.py` only sees the one tab it is porting, so pack art belonging to
other teams' packs never gets written. This walks all tabs in both workbooks,
resolves each floor block's art to its pack name, and writes the lot — so a
pack's art is already present whenever that team is ported.

Also reports which packs have no art in the source, since those need images
from elsewhere.

Usage: python -I tools/packart.py <site_dir> <workbook.xlsx> [more.xlsx ...]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook
import extract as X


def main():
    site = sys.argv[1]
    outdir = os.path.join(site, 'assets', 'packs')
    os.makedirs(outdir, exist_ok=True)

    found = {}                       # slug -> (name, wb, member)
    allpacks = collections.defaultdict(set)   # slug -> {name}
    tabs_seen = 0

    for path in sys.argv[2:]:
        wb = Workbook(path)
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
            tabs_seen += 1
            imgs = wb.images(tab)
            floors = X.parse_floors(cells, imgs, band[0], band[1], {}, wb)
            for f in floors:
                slug, name = f.get('packSlug'), f.get('pack')
                if not slug:
                    continue
                allpacks[slug].add(name)
                sha = f.get('artSha')
                if not sha or slug in found:
                    continue
                for im in imgs:
                    if im['sha256'] == sha:
                        found[slug] = (name, wb, im['member'])
                        break

    for slug, (name, wb, member) in sorted(found.items()):
        dest = os.path.join(outdir, slug + '.png')
        if not os.path.exists(dest) and not os.path.exists(dest[:-4] + '.webp'):
            with open(dest, 'wb') as fh:
                fh.write(wb.read_member(member))
        print('  art  %-42s %s' % (slug, name))

    missing = sorted(set(allpacks) - set(found))
    print('\nscanned %d team tabs' % tabs_seen)
    print('distinct packs: %d   with art in the sheet: %d   without: %d'
          % (len(allpacks), len(found), len(missing)))
    if missing:
        print('\nno art in the source (needs an image dropped at '
              'site/assets/packs/<slug>.webp):')
        for slug in missing:
            print('  %-42s %s' % (slug, ' / '.join(sorted(allpacks[slug]))[:46]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
