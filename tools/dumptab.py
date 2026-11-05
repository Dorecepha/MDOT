"""Dump one tab with text and image anchors aligned on the true row axis.

Usage: python -I tools/dumptab.py <workbook.xlsx> <TabName> [from_row] [to_row]
"""
import os
import sys

# python -I drops the script's own directory from sys.path. Add just that
# directory back (not the cwd), so tools/ modules can import each other while
# keeping -I's isolation from site-packages, env vars and the data directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The sheet carries CJK and typographic punctuation; the Windows console
# defaults to cp1252. -I ignores PYTHONIOENCODING, so set it here.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook, index_to_col


def main():
    path, tab = sys.argv[1], sys.argv[2]
    r0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    r1 = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9

    wb = Workbook(path)
    if tab not in wb.sheets:
        print("tabs: %s" % list(wb.sheets))
        return 1

    cells = wb.cells(tab)
    imgs = wb.images(tab)

    by_row = {}
    for (r, c), v in cells.items():
        by_row.setdefault(r, {})[c] = v
    img_row = {}
    for im in imgs:
        img_row.setdefault(im['row'], []).append(im)

    maxrow = max(list(by_row) + list(img_row)) if (by_row or img_row) else 0
    print("%s :: %s  rows=%d  text_cells=%d  images=%d  merges=%d"
          % (path.split('/')[-1], tab, maxrow + 1, len(cells), len(imgs), len(wb.merges(tab))))
    print()

    for r in range(maxrow + 1):
        if not (r0 - 1 <= r <= r1 - 1):
            continue
        txt = by_row.get(r, {})
        ims = img_row.get(r, [])
        if not txt and not ims:
            continue
        print("R%-4d" % (r + 1))
        if txt:
            for c in sorted(txt):
                val = txt[c].replace('\n', ' / ')
                print("      T %-4s %s" % (index_to_col(c), val[:108]))
        if ims:
            for im in sorted(ims, key=lambda x: x['col']):
                print("      I %-4s %-16s %6dKB  %s"
                      % (index_to_col(im['col']), im['member'].split('/')[-1],
                         im['size'] // 1024, im['sha256'][:10]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
