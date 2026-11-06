"""Report the fonts and fill colours the source workbooks actually use.

Weighted by how many cells reference each style, so the result reflects what
a reader sees rather than what merely exists in the style table. Used to keep
the site's typography and palette tied to the original sheets.

Usage: python -I tools/sheetstyle.py <workbook.xlsx> [more.xlsx ...]
"""
import collections
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def parse_styles(z):
    root = ET.fromstring(z.read('xl/styles.xml'))

    fonts = []
    for f in root.find('m:fonts', NS) or []:
        name = f.find('m:name', NS)
        sz = f.find('m:sz', NS)
        col = f.find('m:color', NS)
        fonts.append({
            'name': name.get('val') if name is not None else '(default)',
            'size': sz.get('val') if sz is not None else None,
            'bold': f.find('m:b', NS) is not None,
            'colour': (col.get('rgb') if col is not None else None),
        })

    fills = []
    for fl in root.find('m:fills', NS) or []:
        pf = fl.find('m:patternFill', NS)
        rgb = None
        if pf is not None:
            fg = pf.find('m:fgColor', NS)
            if fg is not None:
                rgb = fg.get('rgb')
        fills.append(rgb)

    xfs = []
    cx = root.find('m:cellXfs', NS)
    for xf in (cx if cx is not None else []):
        xfs.append((int(xf.get('fontId', 0)), int(xf.get('fillId', 0))))
    return fonts, fills, xfs


def main():
    font_use = collections.Counter()
    fill_use = collections.Counter()
    colour_use = collections.Counter()

    for path in sys.argv[1:]:
        z = zipfile.ZipFile(path)
        fonts, fills, xfs = parse_styles(z)
        for name in z.namelist():
            if not name.startswith('xl/worksheets/sheet'):
                continue
            root = ET.fromstring(z.read(name))
            for c in root.iter('{%s}c' % NS['m']):
                s = c.get('s')
                if s is None:
                    continue
                i = int(s)
                if i >= len(xfs):
                    continue
                fid, flid = xfs[i]
                if fid < len(fonts):
                    f = fonts[fid]
                    font_use['%s%s' % (f['name'], ' bold' if f['bold'] else '')] += 1
                    if f['colour']:
                        colour_use[f['colour']] += 1
                if flid < len(fills) and fills[flid]:
                    fill_use[fills[flid]] += 1

    def show(title, ctr, n=12):
        total = sum(ctr.values()) or 1
        print('\n%s (%d styled cells)' % (title, total))
        for k, v in ctr.most_common(n):
            print('   %-28s %7d  %5.1f%%' % (k, v, 100 * v / total))

    show('FONTS', font_use)
    show('FILL COLOURS', fill_use)
    show('TEXT COLOURS', colour_use)
    return 0


if __name__ == '__main__':
    sys.exit(main())
