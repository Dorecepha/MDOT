"""Map every =IMAGE("url") formula in the workbooks to what it illustrates.

Most artwork in the guides is not embedded — it is referenced by URL through
Google Sheets' IMAGE() function, so those cells read as empty and the picture
never reaches an .xlsx export. This recovers the URLs and, where the cell sits
in a floor block's pack-label column, ties each one to its pack.

Usage: python -I tools/imageurls.py <workbook.xlsx> [more.xlsx ...]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook, index_to_col
import extract as X

IMAGE_RE = re.compile(r'image\s*\(\s*"([^"]+)"', re.I)


def main():
    by_pack = {}
    other = collections.Counter()
    total = 0

    for path in sys.argv[1:]:
        wb = Workbook(path)
        for tab in wb.sheets:
            if tab in X.SHARED_TABS:
                continue
            forms = wb.formulas(tab)
            urls = {pos: m.group(1) for pos, f in forms.items()
                    if (m := IMAGE_RE.search(f))}
            if not urls:
                continue
            total += len(urls)

            cells = wb.cells(tab)
            secs = X.section_rows(cells)
            band = None
            for i, (r, h) in enumerate(secs):
                if 'FLOORS TO PICK' in h.upper():
                    band = (r, secs[i + 1][0] if i + 1 < len(secs)
                            else max(rr for rr, _ in cells) + 1)
                    break
            if not band:
                other[tab] += len(urls)
                continue

            # a pack's art sits in the label column; its name is the first
            # text below it in that same column
            floors = X.parse_floors(cells, wb.images(tab), band[0], band[1],
                                    {}, wb)
            starts = sorted((f, s) for f, s in
                            ((fl.get('packSlug'), fl.get('pack'))
                             for fl in floors) if f)
            for (r, c), url in sorted(urls.items()):
                if not (band[0] <= r < band[1]) or c != X.PACK_ART_COL:
                    other[tab] += 1
                    continue
                name = None
                for dr in range(1, 12):
                    v = X.clean(cells.get((r + dr, c), ''))
                    if v and not X.FLOOR_RE.match(v):
                        name = v
                        break
                if name:
                    by_pack.setdefault(X.slugify(name),
                                       (X.name_case(name), url))

    print('IMAGE() formulas found: %d' % total)
    print('resolved to a pack: %d\n' % len(by_pack))
    for slug, (name, url) in sorted(by_pack.items()):
        print('%-44s %s' % (slug, url))
    if other:
        print('\nIMAGE() cells not in a pack-label position:')
        for tab, n in other.most_common(8):
            print('  %-38s %d' % (tab, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
