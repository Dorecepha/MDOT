"""Dump the gift slots of one pack band with their computed roles.

Usage: python -I tools/debugpack.py <workbook.xlsx> <TabName> <row_from> <row_to>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook, index_to_col
import extract as X


def main():
    path, tab = sys.argv[1], sys.argv[2]
    r0, r1 = int(sys.argv[3]) - 1, int(sys.argv[4])
    wb = Workbook(path)
    cells = wb.cells(tab)
    imgs = wb.images(tab)

    print('%-5s %-4s %-12s %-5s %-6s %-9s %s'
          % ('row', 'col', 'image', 'tier', 'trows', 'role', 'label-below'))
    for im in sorted(imgs, key=lambda i: (i['row'], i['col'])):
        if not (r0 <= im['row'] < r1):
            continue
        tier, label, trows = X.probe(cells, im['row'], im['col'])
        role = '-' if tier is None else (
            'RESULT' if X.is_result(tier, label, trows) else 'ingredient')
        print('%-5d %-4s %-12s %-5s %-6d %-9s %s'
              % (im['row'] + 1, index_to_col(im['col']),
                 im['member'].split('/')[-1], tier, trows, role,
                 (label or '')[:38]))

    print('\ntext in band:')
    for (r, c), v in sorted(cells.items()):
        if r0 <= r < r1:
            print('  R%-4d %-4s %s' % (r + 1, index_to_col(c), X.clean(v)[:60]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
