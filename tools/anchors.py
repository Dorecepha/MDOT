"""Map embedded images in an .xlsx tab to their anchor cells.

Usage: python -I tools/anchors.py <workbook.xlsx> <TabName> [maxrows]

Reads only stdlib zipfile + ElementTree, so it needs no third-party deps.
Zip member paths are always POSIX, so posixpath is used throughout.
"""
import os
import posixpath
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {
    'm': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}


def colname(n):
    """0-based column index -> A1 letters."""
    s = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def relpath(base_part, target):
    """Resolve a relationship Target against the part that declared it."""
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def rels_for(part):
    return posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')


def main():
    path = sys.argv[1]
    target = sys.argv[2]
    maxrows = int(sys.argv[3]) if len(sys.argv) > 3 else 18

    z = zipfile.ZipFile(path)
    names = set(z.namelist())

    wb = ET.fromstring(z.read('xl/workbook.xml'))
    wbrels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in wbrels}

    sheets = {}
    for s in wb.findall('.//m:sheet', NS):
        rid = s.get('{%s}id' % NS['r'])
        sheets[s.get('name')] = relpath('xl/workbook.xml', relmap[rid])

    print("sheet tabs: %d" % len(sheets))
    if target not in sheets:
        print("NOT FOUND. available:")
        for k in sheets:
            print("   %s" % k)
        return 1

    sp = sheets[target]
    print("\n=== %s -> %s ===" % (target, sp))
    sx = ET.fromstring(z.read(sp))

    merges = [m.get('ref') for m in sx.findall('.//m:mergeCell', NS)]
    print("merged ranges: %d" % len(merges))
    print("  sample: %s" % merges[:12])

    dr = sx.find('.//m:drawing', NS)
    if dr is None:
        print("no drawing part on this tab")
        return 0

    srels = ET.fromstring(z.read(rels_for(sp)))
    smap = {r.get('Id'): r.get('Target') for r in srels}
    dpath = relpath(sp, smap[dr.get('{%s}id' % NS['r'])])
    print("drawing part: %s" % dpath)

    drels = ET.fromstring(z.read(rels_for(dpath)))
    dmap = {r.get('Id'): relpath(dpath, r.get('Target')) for r in drels}
    dx = ET.fromstring(z.read(dpath))

    rows = {}
    total = 0
    for tag in ('twoCellAnchor', 'oneCellAnchor', 'absoluteAnchor'):
        for a in dx.findall('xdr:' + tag, NS):
            frm = a.find('xdr:from', NS)
            blip = a.find('.//a:blip', NS)
            if frm is None or blip is None:
                continue
            c = int(frm.find('xdr:col', NS).text)
            rw = int(frm.find('xdr:row', NS).text)
            media = dmap.get(blip.get('{%s}embed' % NS['r']), '?')
            size = z.getinfo(media).file_size if media in names else 0
            rows.setdefault(rw + 1, []).append((colname(c), posixpath.basename(media), size))
            total += 1

    print("anchored images: %d\n" % total)
    for rw in sorted(rows)[:maxrows]:
        cells = ", ".join(
            "%s:%s(%dKB)" % (c, m, s // 1024) for c, m, s in sorted(rows[rw])
        )
        print("  R%-4d %s" % (rw, cells))
    return 0


if __name__ == '__main__':
    sys.exit(main())
