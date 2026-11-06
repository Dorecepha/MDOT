"""Build the pack-art catalogue from the reference sheet's floor_picture row.

Pack art is not embedded in the workbooks — it is referenced through Google
Sheets' IMAGE() function, so the pictures never reach an .xlsx export and the
cells read as empty. `New Reference Sheet` holds the authoritative catalogue
as a named-range pair: `floor_picture` (IMAGE formulas) over `floor_name`
(the pack names), the same shape as the identity lookup.

Writes tools/pack_art_urls.json mapping pack slug -> {name, url}. That also
gives one canonical display name per pack, which the team tabs disagree on.

Usage: python -I tools/packurls.py [--width N] <workbook.xlsx> [more.xlsx ...]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook
import extract as X

REF_TAB = 'New Reference Sheet'
IMAGE_RE = re.compile(r'image\s*\(\s*"([^"]+)"', re.I)
# wiki.gg thumbnails embed their width twice: /thumb/Name.png/190px-Name.png
THUMB_RE = re.compile(r'/(\d+)px-')


def upscale(url, width):
    """Ask the wiki for a larger rendering of the same thumbnail."""
    if not width or '/thumb/' not in url:
        return url
    return THUMB_RE.sub('/%dpx-' % width, url, count=1)


def main():
    args = sys.argv[1:]
    width = None
    if args and args[0] == '--width':
        width = int(args[1])
        args = args[2:]

    out = {}
    for path in args:
        wb = Workbook(path)
        if REF_TAB not in wb.sheets:
            continue
        cells = wb.cells(wb.sheets and REF_TAB)
        forms = wb.formulas(REF_TAB)

        labels = {r: X.clean(v).lower() for (r, c), v in cells.items() if c == 0}
        pic_row = next((r for r, v in labels.items() if v == 'floor_picture'), None)
        name_row = next((r for r, v in labels.items() if v == 'floor_name'), None)
        if pic_row is None or name_row is None:
            continue

        for (r, c), f in forms.items():
            if r != pic_row:
                continue
            m = IMAGE_RE.search(f)
            if not m:
                continue
            name = X.clean(cells.get((name_row, c), ''))
            if not name:
                continue
            slug = X.slugify(name)
            out.setdefault(slug, {'name': X.name_case(name),
                                  'url': upscale(m.group(1), width)})

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'pack_art_urls.json')
    with open(dest, 'w', encoding='utf-8') as fh:
        json.dump({'_comment': 'Pack art URLs recovered from the reference '
                               'sheet\'s floor_picture / floor_name rows. The '
                               'workbooks reference these through IMAGE() '
                               'formulas, so the images are not in the .xlsx. '
                               'Regenerate with tools/packurls.py.',
                   'packs': dict(sorted(out.items()))}, fh,
                  indent=2, ensure_ascii=False)
    print('packs in catalogue: %d' % len(out))
    print('wrote %s' % dest)
    return 0


if __name__ == '__main__':
    sys.exit(main())
